"""Bounded, resumable rechecks with complete revision history and human-decision precedence."""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from backend.services.ops_db_service import _connect, _decode_run_row
from backend.services.case_report_service import _digest, _evidence
from src.classifier import classify_row, _adjudicate_targeted_row
from src.models import InputRow
from src.pipeline import _serialize_result
from src.ssot_loader import load_ssot
from src.failure_policy import validated_auto_consensus


def recheck_status(runs_dir: Path, run_id: str):
    path = runs_dir / run_id / 'automatic_recheck.json'
    try:
        data = json.loads(path.read_text())
        return {k:data[k] for k in ('state','total','processed','resolved','remaining') if k in data}
    except (OSError,ValueError):
        return None


def _save(path, data):
    staging = path.with_suffix('.tmp')
    staging.write_text(json.dumps(data,ensure_ascii=False,indent=2));staging.chmod(0o600);staging.replace(path)


def apply_recheck(*, runs_dir, run_id, before, result, policy_id):
    """Commit only if the evidence is unchanged and no human acted during inference."""
    with _connect(runs_dir) as conn:
        conn.execute('BEGIN IMMEDIATE')
        raw=conn.execute('SELECT * FROM run_rows WHERE run_id=? AND row_index=?',(run_id,before['row_index'])).fetchone()
        if raw is None: return 'skipped'
        current=_decode_run_row(raw)
        if conn.execute('SELECT 1 FROM case_decisions WHERE run_id=? AND row_index=?',(run_id,before['row_index'])).fetchone() or current.get('review_decision') in {'confirm','adjust'}:
            return 'human_preserved'
        if _digest(_evidence(current)) != _digest(_evidence(before)):
            return 'changed'
        # A previously uncertain case cannot become automatic on one fresh model's assertion.
        if result.row_index != before['row_index'] or ' '.join(str(result.drafted_text or '').split()) != ' '.join(str(before.get('post_text') or '').split()):
            return 'changed'
        automatic=validated_auto_consensus(result)
        flags=sorted(set(result.flags) | (set() if automatic else {'REVIEW_REQUIRED'}))
        payload=_serialize_result(result);payload['flags']=flags
        revision_id=str(uuid.uuid4());now=int(time.time())
        conn.execute('INSERT INTO analysis_revisions VALUES (?,?,?,?,?,?)',(revision_id,run_id,before['row_index'],json.dumps({'policy_id':policy_id,'row':dict(raw)},ensure_ascii=False),json.dumps(payload,ensure_ascii=False),now))
        conn.execute('''UPDATE run_rows SET assigned_category=?,confidence_score=?,explanation=?,flags_json=?,fallback_events_json=?,
            soft_signal_score=?,soft_signal_flags_json=?,soft_signal_evidence_json=?,judge_score=?,judge_verdict=?,model_votes_json=?,
            drafted_text=?,analysis_trace_json=?,review_required=?,updated_at=? WHERE run_id=? AND row_index=?''',
            (result.category,result.confidence,result.explanation,json.dumps(flags),json.dumps(result.fallback_events or []),
             result.soft_signal_score,json.dumps(result.soft_signal_flags or []),json.dumps(result.soft_signal_evidence or []),result.judge_score,result.judge_verdict,json.dumps(result.model_votes or {}),
             result.drafted_text,json.dumps(result.audit_trace,ensure_ascii=False),int(not automatic),now,run_id,before['row_index']))
        from backend.services.automatic_report_service import refresh_automatic_report
        refresh_automatic_report(conn,runs_dir=runs_dir,run_id=run_id,row_index=before['row_index'])
        conn.execute('INSERT INTO events(entity_type,entity_id,event_type,payload_json,created_at) VALUES (?,?,?,?,?)',
            ('run',run_id,'automatic_recheck_recorded',json.dumps({'row_index':before['row_index'],'revision_id':revision_id,'automatic':automatic,'policy_id':policy_id}),now))
        return 'automatic' if automatic else 'review'


def run_planned_rechecks(*, runs_dir: Path, run_id: str, ssot_path: Path, should_stop=lambda: False, on_progress=lambda _: None):
    path=runs_dir/run_id/'automatic_recheck.json'
    if not path.exists(): return
    plan=json.loads(path.read_text())
    if plan.get('state')=='completed': return
    policy=load_ssot(ssot_path)
    done=set(plan.get('done_rows') or [])
    plan['state']='running';_save(path,plan)
    for index in plan['row_indices']:
        if should_stop(): raise KeyboardInterrupt('suspend requested during automatic recheck')
        if index in done: continue
        with _connect(runs_dir) as conn:
            raw=conn.execute('SELECT * FROM run_rows WHERE run_id=? AND row_index=?',(run_id,index)).fetchone()
            human=conn.execute('SELECT 1 FROM case_decisions WHERE run_id=? AND row_index=?',(run_id,index)).fetchone()
            already=conn.execute('SELECT previous_json,replacement_json FROM analysis_revisions WHERE run_id=? AND row_index=? ORDER BY created_at DESC LIMIT 1',(run_id,index)).fetchone()
        if raw is None or human:
            status='skipped'
        elif already and json.loads(already['previous_json']).get('policy_id')==plan['policy_id']:
            status='automatic' if validated_auto_consensus(json.loads(already['replacement_json'])) else 'review'
        else:
            before=_decode_run_row(raw)
            initial=classify_row(InputRow(index,before['item_number'],before['post_text']),policy,'partial')
            initial.flags=sorted(set(initial.flags+['REASSESSMENT_REQUESTED']))
            result=_adjudicate_targeted_row(InputRow(index,before['item_number'],before['post_text']),initial,policy,'partial')
            if should_stop(): raise KeyboardInterrupt('suspend requested during automatic recheck')
            status=apply_recheck(runs_dir=runs_dir,run_id=run_id,before=before,result=result,policy_id=plan['policy_id'])
        done.add(index);plan['done_rows']=sorted(done);plan['processed']=len(done)
        plan['resolved']=plan.get('resolved',0)+int(status=='automatic')
        plan['remaining']=plan['total']-len(done)
        _save(path,plan);on_progress(plan)
    plan['state']='completed';_save(path,plan);on_progress(plan)
