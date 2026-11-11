"""Human case decisions and bounded official report exports from canonical evidence."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from backend.services.ops_db_service import _connect, _decode_run_row
from src.failure_policy import ANALYSIS_FAILURE_FLAGS
from src.models import CANONICAL_CATEGORIES
from backend.services.recheck_queue_service import pending_recheck_rows


class CaseConflict(RuntimeError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _evidence(row: dict) -> dict:
    fields = ('row_index', 'item_number', 'post_text', 'row_hash', 'source_row_index', 'source_row_hash', 'assigned_category', 'confidence_score', 'flags', 'fallback_events', 'explanation', 'model_votes', 'drafted_text')
    evidence = {key: row.get(key) for key in fields}
    # Preserve tokens of pre-existing human decisions when no new analysis trace exists.
    if row.get('audit_trace'):
        evidence['audit_trace'] = row['audit_trace']
    return evidence


from functools import lru_cache

@lru_cache(maxsize=1)
def _review_policy():
    from src.defaults import DEFAULT_SSOT_PATH
    from src.ssot_loader import load_ssot
    return load_ssot(Path(DEFAULT_SSOT_PATH)).policy


def _review_reasons(row):
    from src.review_routing import exception_reasons
    return exception_reasons(row, _review_policy()) or ['REVIEW_MODE_REQUESTED']


def _automatic_checks(row):
    trace=row.get('audit_trace') or {}
    checks=[]
    if trace.get('initial') and trace.get('alternate'):
        for key in ('initial','alternate'):
            branch=trace[key]
            checks.append(f"{branch.get('model')}: {branch.get('category')} ({float(branch.get('confidence') or 0):.2f})")
        checks.append(f"Independent quality check ({trace.get('judge_model') or 'historical route'}): {trace.get('judge_verdict') or 'unavailable'} ({float(trace.get('judge_score') or 0):.2f})")
    from src.failure_policy import validated_auto_consensus
    if validated_auto_consensus(row):
        checks.append('Independent automatic checks passed: two distinct models agreed at confidence 0.85 or above; a third model passed the quality check at 0.85 or above. Saved human decisions take precedence.')
    elif trace.get('retry_response'):
        checks.append('The model response was retried once to repair its structure. Both attempts are retained in the analysis trace.')
    return checks


def _case(row: dict, decision, *, automatic_pending: bool = False, automatic_report: dict | None = None) -> dict:
    evidence_hash = _digest(_evidence(row))
    saved = dict(decision) if decision else {}
    current = bool(saved) and saved['evidence_hash'] == evidence_hash
    automatic_report = automatic_report if not current else None
    automatic_pending = automatic_pending and not current and not automatic_report
    outcome = saved.get('outcome', 'unresolved') if current else ('ai_reported' if automatic_report else ('automatic_pending' if automatic_pending else ('unresolved' if row.get('review_required') else 'automatic')))
    token_payload = {'evidence_hash': evidence_hash, 'decision_id': saved.get('decision_id')}
    if automatic_pending: token_payload['automatic_checks_pending'] = True
    if automatic_report: token_payload['automatic_report_id'] = automatic_report.get('report_id')
    return {
        **row, 'evidence_hash': evidence_hash, 'post_text_sha256': hashlib.sha256(str(row.get('post_text') or '').encode('utf-8')).hexdigest(),
        'case_token': _digest(token_payload),
        'workflow_bucket': (('reporting' if automatic_report else ('automatic_pending' if automatic_pending else ('waiting' if row.get('review_required') else 'automatic'))) if not current else ('follow_up' if outcome == 'unresolved' else outcome)),
        'review_reasons': _review_reasons(row) if row.get('review_required') and not automatic_pending and not automatic_report else [],
        'automatic_report': automatic_report,
        'human_review_required': (outcome == 'unresolved' and not automatic_pending and not automatic_report),
        'automatic_checks': _automatic_checks(row),
        'outcome': outcome, 'decision_stale': bool(saved) and not current,
        'decision_id': saved.get('decision_id'), 'human_category': saved.get('human_category') if current else None,
        'reviewer': saved.get('reviewer') if current else None,
        'reviewed_at': saved.get('reviewed_at') if current else None,
        'decision_note': saved.get('note', '') if current else '',
        'can_export': current and outcome == 'confirmed_threat' and saved.get('human_category') in CANONICAL_CATEGORIES - {'Not Antisemitic'},
    }


def _report_info(record):
    if record is None:return None
    value=dict(record)
    return {'report_id':value.get('report_id'),'state':value['state'],'last_error':value.get('last_error'),'findings':json.loads(value['findings_json']),'generated_at':value['updated_at']}


def _load_case(conn, run_id, row_index, *, runs_dir: Path):
    row = conn.execute('SELECT * FROM run_rows WHERE run_id=? AND row_index=?', (run_id, row_index)).fetchone()
    if row is None:
        return None
    decision = conn.execute('SELECT * FROM case_decisions WHERE run_id=? AND row_index=?', (run_id, row_index)).fetchone()
    status = conn.execute('SELECT * FROM automatic_report_status WHERE run_id=? AND row_index=?',(run_id,row_index)).fetchone()
    case = _case(_decode_run_row(row), decision, automatic_pending=row_index in pending_recheck_rows(runs_dir,run_id),automatic_report=_report_info(status))
    history=[]
    for entry in conn.execute('SELECT revision_id,previous_json,replacement_json,created_at FROM analysis_revisions WHERE run_id=? AND row_index=? ORDER BY created_at DESC LIMIT 10',(run_id,row_index)):
        before=json.loads(entry['previous_json']).get('row',{});after=json.loads(entry['replacement_json'])
        history.append({'revision_id':entry['revision_id'],'created_at':entry['created_at'],'previous_category':before.get('assigned_category',''),'new_category':after.get('category',''),'previous_flags':json.loads(before.get('flags_json') or '[]'),'new_flags':after.get('flags') or []})
    case['analysis_history']=history
    return case


def get_case(*, runs_dir: Path, run_id: str, row_index: int) -> dict | None:
    with _connect(runs_dir) as conn:
        return _load_case(conn, run_id, row_index, runs_dir=runs_dir)


def case_page(*, runs_dir: Path, run_id: str, offset: int = 0, limit: int = 100, bucket: str = 'all') -> dict:
    buckets = ('waiting','automatic_pending','automatic','follow_up','confirmed_threat','false_alarm','reporting')
    if bucket not in ('all', *buckets):
        raise ValueError('Unknown review bucket')
    pending = pending_recheck_rows(runs_dir,run_id)
    with _connect(runs_dir) as conn:
        conn.execute('BEGIN')
        # Partition the complete run before pagination. A saved human decision always takes precedence.
        cte = """WITH queued AS (SELECT r.*,
            CASE WHEN d.outcome='unresolved' THEN 'follow_up'
                 WHEN d.decision_id IS NOT NULL THEN d.outcome
                 WHEN a.run_id IS NOT NULL THEN 'reporting'
                 WHEN r.row_index IN (SELECT value FROM json_each(?)) THEN 'automatic_pending'
                 WHEN r.review_required=1 THEN 'waiting' ELSE 'automatic' END AS queue_bucket
            FROM run_rows r LEFT JOIN case_decisions d ON d.run_id=r.run_id AND d.row_index=r.row_index
            LEFT JOIN automatic_report_status a ON a.run_id=r.run_id AND a.row_index=r.row_index
            WHERE r.run_id=?) """
        args = (json.dumps(sorted(pending)),run_id)
        sums = ','.join(f"COALESCE(SUM(queue_bucket='{key}'),0) AS {key}" for key in buckets)
        counts = dict(conn.execute(cte + 'SELECT COUNT(*) AS total,' + sums + ' FROM queued',args).fetchone())
        total = counts['total'] if bucket == 'all' else counts[bucket]
        if bucket != 'all':
            offset = min(max(0, offset), ((max(total, 1) - 1) // limit) * limit)
        where, filter_args = ('1=1',()) if bucket == 'all' else ('queue_bucket=?',(bucket,))
        rows = conn.execute(cte + 'SELECT * FROM queued WHERE ' + where + ' ORDER BY created_at,row_index LIMIT ? OFFSET ?', (*args,*filter_args,limit,offset)).fetchall()
        indices = [row['row_index'] for row in rows]
        decisions = {r['row_index']: r for r in conn.execute('SELECT * FROM case_decisions WHERE run_id=? AND row_index IN (' + ','.join('?' for _ in indices) + ')', (run_id, *indices))} if indices else {}
        reports = {r['row_index']:_report_info(r) for r in conn.execute('SELECT * FROM automatic_report_status WHERE run_id=? AND row_index IN (' + ','.join('?' for _ in indices) + ')',(run_id,*indices))} if indices else {}
        from backend.services.automatic_recheck_service import recheck_status
        return {'run_id':run_id,'total':total,'offset':offset,'limit':limit,'bucket':bucket,'counts':counts,'recheck':recheck_status(runs_dir,run_id),
                'rows':[_case(_decode_run_row(row),decisions.get(row['row_index']),automatic_pending=row['row_index'] in pending,automatic_report=reports.get(row['row_index'])) for row in rows]}


def record_decision(*, runs_dir: Path, run_id: str, row_index: int, outcome: str, category: str | None, note: str, actor: str, case_token: str) -> dict:
    if outcome not in {'confirmed_threat', 'false_alarm', 'unresolved'}:
        raise ValueError('Choose confirmed_threat, false_alarm, or unresolved')
    if outcome == 'confirmed_threat' and category not in CANONICAL_CATEGORIES - {'Not Antisemitic'}:
        raise ValueError('Choose a threat category before confirming')
    if len(note) > 10000:
        raise ValueError('Reviewer note is too long')
    now = int(time.time())
    with _connect(runs_dir) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = _load_case(conn, run_id, row_index, runs_dir=runs_dir)
        if row is None:
            raise LookupError('Classified row not found')
        if row['outcome'] == 'automatic_pending':
            raise CaseConflict('Automatic checks are still pending. This case will enter your review queue only if those checks cannot resolve it.')
        if not case_token or row['case_token'] != case_token:
            raise CaseConflict('This case changed. Refresh and review it before saving.')
        if outcome == 'confirmed_threat' and not str(row.get('post_text') or '').strip():
            raise ValueError('An empty post cannot be confirmed as a threat.')
        human_category = category if outcome == 'confirmed_threat' else ('Not Antisemitic' if outcome == 'false_alarm' else None)
        decision_id = str(uuid.uuid4())
        payload = {'decision_id': decision_id, 'run_id': run_id, 'row_index': row_index, 'outcome': outcome, 'human_category': human_category, 'note': note, 'reviewer': actor, 'reviewed_at': now, 'evidence_hash': row['evidence_hash']}
        conn.execute('DELETE FROM automatic_report_status WHERE run_id=? AND row_index=?',(run_id,row_index))
        conn.execute('INSERT OR REPLACE INTO case_decisions VALUES (?,?,?,?,?,?,?,?,?)', (run_id, row_index, decision_id, outcome, human_category, note, actor, now, row['evidence_hash']))
        conn.execute('INSERT INTO case_decision_history VALUES (?,?,?,?,?)', (decision_id, run_id, row_index, json.dumps(payload, ensure_ascii=False), now))
        legacy_decision = None if outcome == 'unresolved' else ('confirm' if human_category == row['assigned_category'] else 'adjust')
        conn.execute('UPDATE run_rows SET review_state=?,review_decision=?,reviewer_note=?,updated_at=? WHERE run_id=? AND row_index=?', ('pending' if outcome == 'unresolved' else 'reviewed', legacy_decision, note, now, run_id, row_index))
        conn.execute('INSERT INTO events(entity_type,entity_id,event_type,payload_json,created_at) VALUES (?,?,?,?,?)', ('run', run_id, 'case_decision_recorded', json.dumps({key: payload[key] for key in ('decision_id','row_index','outcome','human_category','reviewer','evidence_hash')}), now))
        return _load_case(conn, run_id, row_index, runs_dir=runs_dir)


def run_reports(*, runs_dir: Path, run_id: str) -> dict:
    buckets = case_page(runs_dir=runs_dir,run_id=run_id,limit=1)['counts']
    counts = {'total':buckets['total'],'confirmed_threats':buckets['confirmed_threat'],'false_alarms':buckets['false_alarm'],
              'unresolved':buckets['waiting']+buckets['follow_up'],'automatic':buckets['automatic'],'automatic_pending':buckets['automatic_pending'],'reporting':buckets['reporting']}
    with _connect(runs_dir) as conn:
        counts['failed_analysis'] = conn.execute("SELECT COUNT(*) FROM run_rows WHERE run_id=? AND flags_json LIKE '%\"ANALYSIS_FAILED\"%'",(run_id,)).fetchone()[0]
    evaluation = None
    path = runs_dir / run_id / 'evaluation_report.json'
    if path.exists():
        try:
            evaluation = json.loads(path.read_text())
        except (OSError, ValueError):
            pass
    with _connect(runs_dir) as conn:
        exports = [dict(row) for row in conn.execute('''SELECT e.report_id,e.row_index,e.created_at,e.actor,e.pdf_sha256,
            CASE WHEN d.decision_id=e.decision_id AND d.outcome='confirmed_threat' THEN 1 ELSE 0 END AS is_current
            FROM threat_report_exports e LEFT JOIN case_decisions d ON d.run_id=e.run_id AND d.row_index=e.row_index
            WHERE e.run_id=? ORDER BY e.created_at DESC,e.report_id DESC LIMIT 100''', (run_id,))]
    with _connect(runs_dir) as conn:
        automatic_exports=[dict(r) for r in conn.execute('SELECT e.report_id,e.row_index,e.created_at,CASE WHEN s.report_id=e.report_id THEN 1 ELSE 0 END AS is_current FROM automatic_report_exports e LEFT JOIN automatic_report_status s ON s.report_id=e.report_id WHERE e.run_id=? ORDER BY e.created_at DESC,e.rowid DESC LIMIT 100',(run_id,))]
    return {'run_id': run_id, 'summary': counts, 'evaluation': evaluation, 'exports': exports, 'automatic_exports':automatic_exports}


def export_threat_pdf(*, runs_dir: Path, run_id: str, row_index: int, actor: str) -> Path:
    from backend.services.threat_pdf_service import render_threat_pdf

    with _connect(runs_dir) as conn:
        conn.execute('BEGIN IMMEDIATE')
        case = _load_case(conn, run_id, row_index, runs_dir=runs_dir)
        if case is None:
            raise LookupError('Classified row not found')
        if not case['can_export']:
            raise CaseConflict('Only a current human-confirmed threat can be exported. Confirm this case first.')
        report_id = str(uuid.uuid4())
        now = int(time.time())
        record = conn.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
        snapshot = {'report_id': report_id, 'created_at': now, 'exported_by': actor, 'run_id': run_id, 'language': record['language'] if record else '', 'case': case}
        snapshot['snapshot_hash_scheme'] = 'sha256-canonical-json-without-snapshot_sha256'
        snapshot['snapshot_sha256'] = _digest(snapshot)
        folder = runs_dir / run_id / 'threat_reports'
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = folder / f'spot-threat-{report_id}.pdf'
        json_path = path.with_suffix('.json')
        try:
            render_threat_pdf(snapshot, path)
            os.chmod(path, 0o600)
            json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
            os.chmod(json_path, 0o600)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            conn.execute('INSERT INTO threat_report_exports VALUES (?,?,?,?,?,?,?,?,?)', (report_id, run_id, row_index, case['decision_id'], case['evidence_hash'], str(path), digest, now, actor))
            conn.execute('INSERT INTO events(entity_type,entity_id,event_type,payload_json,created_at) VALUES (?,?,?,?,?)', ('run', run_id, 'threat_report_exported', json.dumps({'report_id': report_id, 'row_index': row_index, 'decision_id': case['decision_id'], 'pdf_sha256': digest}), now))
        except Exception:
            path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)
            raise
    return path


def existing_threat_pdf(*, runs_dir: Path, run_id: str, report_id: str) -> Path:
    with _connect(runs_dir) as conn:
        record = conn.execute('SELECT * FROM threat_report_exports WHERE run_id=? AND report_id=?', (run_id, report_id)).fetchone()
        if record is None:
            raise LookupError('Threat report not found')
        case = _load_case(conn, run_id, record['row_index'], runs_dir=runs_dir)
        if not case or not case['can_export'] or case['decision_id'] != record['decision_id'] or case['evidence_hash'] != record['evidence_hash']:
            raise CaseConflict('This report was superseded by a later review or evidence change. Review the current case.')
        path = Path(record['pdf_path'])
        if not path.resolve().is_relative_to((runs_dir / run_id / 'threat_reports').resolve()) or not path.is_file():
            raise LookupError('Threat report file not found')
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['pdf_sha256']:
            raise CaseConflict('Report integrity verification failed. Generate a new report from the saved confirmation.')
        return path
