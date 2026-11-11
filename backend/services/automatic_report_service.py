"""Automatic, explicitly unconfirmed PDFs for the user's any-positive-score reporting rule."""
from __future__ import annotations
import hashlib
import json
import math
import os
import time
import uuid
from pathlib import Path
from src.models import CANONICAL_CATEGORIES
from src.failure_policy import ANALYSIS_FAILURE_FLAGS

RULE_ID = 'any-current-positive-0.30-v1'
POSITIVE_CATEGORIES = CANONICAL_CATEGORIES - {'Not Antisemitic'}


def reporting_policy(runs_dir: Path, run_id: str) -> dict | None:
    path=runs_dir/run_id/'automatic_reporting_policy.json'
    if not path.exists(): return None
    policy=json.loads(path.read_text())
    if not policy.get('enabled'): return None
    if policy.get('rule_id')!=RULE_ID or policy.get('minimum_positive_confidence') != .30:
        raise ValueError('Unsupported automatic reporting policy')
    return policy


def enable_reporting_policy(*, runs_dir: Path, run_id: str, ssot_path: Path) -> bool:
    raw=json.loads(ssot_path.read_text()).get('automatic_reporting') or {}
    if not raw.get('enabled'): return False
    if raw.get('minimum_positive_confidence',.30) != .30:
        raise ValueError('Automatic reporting threshold must match the approved 0.30 policy')
    policy={'enabled':True,'rule_id':RULE_ID,'minimum_positive_confidence':.30,'trigger':'any_current_positive_analysis_including_retries','human_review_required':False,'report_status':'AI-generated, unconfirmed','created_at':int(time.time())}
    path=runs_dir/run_id/'automatic_reporting_policy.json'
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(policy,indent=2));path.chmod(0o600)
    return True


def positive_findings(row: dict, threshold: float=.30) -> list[dict]:
    if not str(row.get('post_text') or '').strip(): return []
    source=' '.join(str(row['post_text']).split()).lower()
    candidates=[]
    def add(value,stage,model):
        if not isinstance(value,dict):return
        category=value.get('category') or value.get('assigned_category')
        score=value.get('confidence') if 'confidence' in value else value.get('confidence_score')
        if category not in POSITIVE_CATEGORIES or isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not threshold <= score <= 1:
            return
        flags=value.get('flags') or []
        flags=flags if isinstance(flags,list) else ['INVALID_MODEL_METADATA']
        if set(str(f) for f in flags)&ANALYSIS_FAILURE_FLAGS:return
        evidence=value.get('soft_signal_evidence') or []
        evidence=evidence if isinstance(evidence,list) else []
        exact=[str(q) for q in evidence if str(q).strip() and ' '.join(str(q).split()).lower() in source]
        candidates.append({'stage':stage,'model':str(value.get('model') or value.get('resolved_model_version') or model),'category':category,'confidence':float(score),'source_quotes':exact,'warnings':list(flags)})
    trace=row.get('audit_trace') or {}
    add(row,'Final classification','Recorded final classification')
    for key,label in [('initial','Primary analysis'),('alternate','Independent analysis')]:
        branch=trace.get(key) or {}
        add(branch,label,branch.get('model') or label)
        attempts=branch.get('attempts') or {}
        for field,name in [('initial_response','response before structural retry'),('retry_response','structural retry response')]:
            add(attempts.get(field),label+' / '+name,branch.get('model') or label)
    for field,name in [('initial_response','Primary response before structural retry'),('retry_response','Primary structural retry response')]:
        add(trace.get(field),name,'Primary classifier')
    # Keep genuinely distinct model/stage evidence; avoid repeating the same canonical result.
    seen=set();findings=[]
    for f in candidates:
        key=(f['stage'],f['model'],f['category'],f['confidence'])
        if key not in seen:findings.append(f);seen.add(key)
    return findings


def report_evidence_hash(row: dict) -> str:
    from backend.services.case_report_service import _digest,_evidence
    return _digest({'case':_evidence(row),'soft_signal_score':row.get('soft_signal_score'),'soft_signal_flags':row.get('soft_signal_flags'),'soft_signal_evidence':row.get('soft_signal_evidence'),'judge_score':row.get('judge_score'),'judge_verdict':row.get('judge_verdict')})


def refresh_automatic_report(conn, *, runs_dir: Path, run_id: str, row_index: int) -> dict | None:
    """Called inside the evidence write transaction, before any case reaches the UI."""
    if not reporting_policy(runs_dir,run_id):return None
    from backend.services.ops_db_service import _decode_run_row
    from backend.services.case_report_service import _digest,_evidence
    from backend.services.threat_pdf_service import render_threat_pdf
    raw=conn.execute('SELECT * FROM run_rows WHERE run_id=? AND row_index=?',(run_id,row_index)).fetchone()
    if raw is None:return None
    row=_decode_run_row(raw)
    human=conn.execute('SELECT 1 FROM case_decisions WHERE run_id=? AND row_index=?',(run_id,row_index)).fetchone()
    findings=positive_findings(row)
    if human or row.get('review_decision') in {'confirm','adjust'} or not findings:
        conn.execute('DELETE FROM automatic_report_status WHERE run_id=? AND row_index=?',(run_id,row_index))
        return None
    evidence_hash=report_evidence_hash(row);now=int(time.time())
    old=conn.execute('SELECT * FROM automatic_report_exports WHERE run_id=? AND row_index=? AND evidence_hash=? AND rule_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(run_id,row_index,evidence_hash,RULE_ID)).fetchone()
    if old and Path(old['pdf_path']).is_file() and hashlib.sha256(Path(old['pdf_path']).read_bytes()).hexdigest()==old['pdf_sha256']:
        conn.execute('INSERT OR REPLACE INTO automatic_report_status VALUES (?,?,?,?,?,?,?,?)',(run_id,row_index,evidence_hash,json.dumps(findings,ensure_ascii=False),old['report_id'],'generated',None,now))
        return dict(old)
    report_id=str(uuid.uuid4())
    conn.execute('INSERT OR REPLACE INTO automatic_report_status VALUES (?,?,?,?,?,?,?,?)',(run_id,row_index,evidence_hash,json.dumps(findings,ensure_ascii=False),None,'pending',None,now))
    folder=runs_dir/run_id/'automatic_reports';folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=folder/f'spot-ai-finding-{report_id}.pdf';snapshot_path=path.with_suffix('.json')
    record=conn.execute('SELECT language FROM runs WHERE run_id=?',(run_id,)).fetchone()
    case={**row,'evidence_hash':_digest(_evidence(row)),'post_text_sha256':hashlib.sha256(row['post_text'].encode()).hexdigest()}
    snapshot={'report_id':report_id,'report_kind':'ai_unconfirmed','created_at':now,'exported_by':'{spot} automatic reporting','run_id':run_id,'language':record['language'] if record else '', 'case':case,'findings':findings,'rule_id':RULE_ID,'minimum_positive_confidence':.30,'report_evidence_sha256':evidence_hash,'human_confirmed':False,'snapshot_hash_scheme':'sha256-canonical-json-without-snapshot_sha256'}
    snapshot['snapshot_sha256']=_digest(snapshot)
    try:
        render_threat_pdf(snapshot,path);path.chmod(0o600)
        snapshot_path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2));snapshot_path.chmod(0o600)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        # An integrity-failed old export stays in audit history; only one active pointer is used.
        conn.execute('INSERT INTO automatic_report_exports VALUES (?,?,?,?,?,?,?,?,?,?)',(report_id,run_id,row_index,evidence_hash,RULE_ID,str(path),digest,str(snapshot_path),json.dumps(findings,ensure_ascii=False),now))
        conn.execute('UPDATE automatic_report_status SET report_id=?,state=?,last_error=NULL WHERE run_id=? AND row_index=?',(report_id,'generated',run_id,row_index))
        conn.execute('INSERT INTO events(entity_type,entity_id,event_type,payload_json,created_at) VALUES (?,?,?,?,?)',('run',run_id,'automatic_ai_report_generated',json.dumps({'report_id':report_id,'row_index':row_index,'rule_id':RULE_ID,'report_evidence_sha256':evidence_hash,'human_confirmed':False}),now))
        return {'report_id':report_id,'pdf_path':str(path)}
    except Exception as exc:
        path.unlink(missing_ok=True);snapshot_path.unlink(missing_ok=True)
        conn.execute('UPDATE automatic_report_status SET state=?,last_error=? WHERE run_id=? AND row_index=?',('failed',type(exc).__name__,run_id,row_index))
        return {'state':'failed','error':type(exc).__name__}


def download_automatic_report(*, runs_dir: Path, run_id: str, report_id: str) -> Path:
    from backend.services.ops_db_service import _connect,_decode_run_row
    from backend.services.case_report_service import CaseConflict
    with _connect(runs_dir) as conn:
        record=conn.execute('SELECT e.* FROM automatic_report_exports e JOIN automatic_report_status s ON s.report_id=e.report_id WHERE e.run_id=? AND e.report_id=?',(run_id,report_id)).fetchone()
        if record is None:raise CaseConflict('This AI report is superseded or no longer current. Inspect the current case.')
        raw=conn.execute('SELECT * FROM run_rows WHERE run_id=? AND row_index=?',(run_id,record['row_index'])).fetchone()
        if raw is None or report_evidence_hash(_decode_run_row(raw))!=record['evidence_hash'] or conn.execute('SELECT 1 FROM case_decisions WHERE run_id=? AND row_index=?',(run_id,record['row_index'])).fetchone():
            raise CaseConflict('This AI report was superseded by a later analysis or human decision.')
        path=Path(record['pdf_path'])
        if not path.resolve().is_relative_to((runs_dir/run_id/'automatic_reports').resolve()) or not path.is_file():raise LookupError('AI report file not found')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['pdf_sha256']:raise CaseConflict('AI report integrity check failed. Regenerate the report.')
        return path
