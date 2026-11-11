"""Audited conversion of a suspended full-review run to exception-only review."""
from __future__ import annotations
import json
import os
import sqlite3
import time
from pathlib import Path
from backend.services.ops_db_service import _connect, _decode_run_row, db_path
from backend.services.run_state_service import read_run_record, write_run_record
from backend.services.case_report_service import _evidence, _digest
from src.review_routing import exception_reasons, recovered_drafter_rejection
from src.ssot_loader import load_ssot


def reconcile_exception_review(*, runs_dir: Path, run_id: str, ssot_path: Path) -> dict:
    record = read_run_record(runs_dir=runs_dir, run_id=run_id)
    if not record:
        raise LookupError('Run not found')
    control_path = runs_dir / run_id / 'control.json'
    control = json.loads(control_path.read_text()) if control_path.exists() else {}
    pid = control.get('pid')
    if pid:
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Suspend the run and close the cockpit before changing its review policy')
    policy = load_ssot(ssot_path).policy
    stamp = time.time_ns()
    folder = runs_dir / run_id / 'review_policy_history'
    folder.mkdir(mode=0o700, exist_ok=True)
    backup = folder / f'operations-before-{stamp}.sqlite3'
    with sqlite3.connect(db_path(runs_dir)) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    os.chmod(backup, 0o600)
    old_record = folder / f'run-record-before-{stamp}.json'
    old_record.write_text(json.dumps(record, ensure_ascii=False, indent=2));os.chmod(old_record, 0o600)
    with _connect(runs_dir) as conn:
        conn.execute('BEGIN IMMEDIATE')
        decisions_before = [tuple(r) for r in conn.execute('SELECT * FROM case_decisions WHERE run_id=? ORDER BY row_index', (run_id,))]
        rows = conn.execute('SELECT * FROM run_rows WHERE run_id=? ORDER BY row_index', (run_id,)).fetchall()
        report = {'run_id': run_id, 'policy': 'exception-only-v1', 'previous_mode': record.get('review_mode'), 'mode': 'partial', 'created_at': int(time.time()), 'preserved_decisions': len(decisions_before), 'rows': [], 'requires_review': 0, 'automatic': 0, 'verified_drafter_recoveries': 0}
        evidence_before = [_digest(_evidence(_decode_run_row(r))) for r in rows]
        for row in rows:
            decoded = _decode_run_row(row)
            reasons = exception_reasons(decoded, policy)
            required = bool(reasons)
            report['requires_review' if required else 'automatic'] += 1
            report['verified_drafter_recoveries'] += int(recovered_drafter_rejection(decoded))
            conn.execute('UPDATE run_rows SET review_required=? WHERE run_id=? AND row_index=?', (int(required), run_id, row['row_index']))
            report['rows'].append({'row_index': row['row_index'], 'requires_review': required, 'reasons': reasons, 'evidence_hash': evidence_before[len(report['rows'])]})
        after = conn.execute('SELECT * FROM run_rows WHERE run_id=? ORDER BY row_index', (run_id,)).fetchall()
        assert evidence_before == [_digest(_evidence(_decode_run_row(r))) for r in after], 'Classification evidence changed'
        assert decisions_before == [tuple(r) for r in conn.execute('SELECT * FROM case_decisions WHERE run_id=? ORDER BY row_index', (run_id,))], 'Human decisions changed'
        conn.execute('UPDATE runs SET review_mode=? WHERE run_id=?', ('partial', run_id))
        conn.execute('INSERT INTO events(entity_type,entity_id,event_type,payload_json,created_at) VALUES (?,?,?,?,?)', ('run',run_id,'review_policy_changed',json.dumps({k:v for k,v in report.items() if k != 'rows'}),int(time.time())))
    record['review_mode'] = 'partial'
    record.setdefault('start_payload', {})['review_mode'] = 'partial'
    write_run_record(runs_dir=runs_dir, run_id=run_id, record=record)
    target = folder / f'exception-routing-{stamp}.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)); os.chmod(target,0o600)
    return {k:v for k,v in report.items() if k != 'rows'} | {'audit_report': str(target), 'backup': str(backup)}
