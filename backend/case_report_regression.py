from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader
import backend.main as main
from backend.services import auth_service
from backend.services.ops_db_service import _connect, upsert_run_rows, fetch_run_row, update_run_row_review
from backend.services.run_state_service import create_run_record
from backend.services.case_report_service import get_case, record_decision, export_threat_pdf, CaseConflict, run_reports


class CaseReportRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runs = Path(self.temp.name)
        self.previous = main.RUNS_DIR
        main.RUNS_DIR = self.runs
        auth_service._SESSIONS.clear()
        self.client = TestClient(main.app)
        create_run_record(runs_dir=self.runs, run_id='case-test', input_path='input.xlsx', output_path='output.xlsx', upload_id=None, language='de', review_mode='partial')
        upsert_run_rows(runs_dir=self.runs, run_id='case-test', upload_id=None, rows=[{'row_index': 2, 'item_number': 'synthetic-1', 'post_text': 'Synthetic evidence only: őű Ж <script>not markup</script> 🧐', 'assigned_category': 'Not Antisemitic', 'confidence_score': .99, 'flags': [], 'review_required': True, 'explanation': 'Synthetic model proposal.'}])

    def tearDown(self):
        main.RUNS_DIR = self.previous
        auth_service._SESSIONS.clear()
        self.temp.cleanup()

    def login(self, role):
        response = self.client.post('/auth/login', json={'role': role, 'actor_name': 'synthetic-reviewer', 'access_code': 'spot-local'})
        self.assertEqual(response.status_code, 200)

    def decide(self, outcome='confirmed_threat', category='Conspiracy Theories'):
        current = get_case(runs_dir=self.runs, run_id='case-test', row_index=2)
        return record_decision(runs_dir=self.runs, run_id='case-test', row_index=2, outcome=outcome, category=category, note='Synthetic test finding; not a real threat.', actor='synthetic-reviewer', case_token=current['case_token'])

    def test_nonflagged_posts_are_reviewable_without_changing_model_category(self):
        self.login('reviewer')
        with _connect(self.runs) as conn:
            conn.execute("UPDATE run_rows SET review_required=0 WHERE run_id='case-test'")
        self.assertEqual(self.client.get('/runs/case-test/cases?bucket=waiting').json()['rows'], [])
        page = self.client.get('/runs/case-test/cases').json()
        self.assertEqual(page['total'], 1)
        self.assertEqual(page['rows'][0]['outcome'], 'automatic')
        response = self.client.post('/runs/case-test/cases/2/decision', json={'outcome': 'confirmed_threat', 'category': 'Conspiracy Theories', 'note': 'Synthetic confirmation', 'case_token': page['rows'][0]['case_token']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['can_export'])
        self.assertEqual(fetch_run_row(runs_dir=self.runs, run_id='case-test', row_index=2)['assigned_category'], 'Not Antisemitic')
        summary = self.client.get('/runs/case-test/reports').json()['summary']
        self.assertEqual(summary['confirmed_threats'], 1)
        self.assertEqual(summary['unresolved'], 0)

    def test_export_requires_confirmation_and_reviewer_export_permission(self):
        self.assertEqual(self.client.post('/runs/case-test/cases/2/report.pdf').status_code, 401)
        self.login('operator')
        self.assertEqual(self.client.post('/runs/case-test/cases/2/report.pdf').status_code, 403)
        self.assertEqual(self.client.post('/runs/case-test/cases/2/decision', json={}).status_code, 403)
        self.login('reviewer')
        self.assertEqual(self.client.post('/runs/case-test/cases/2/report.pdf').status_code, 409)
        decision = self.decide()
        response = self.client.post('/runs/case-test/cases/2/report.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/pdf')
        text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
        self.assertIn('{spot}', text)
        self.assertIn('CONFIRMED THREAT REPORT', text)
        self.assertIn('Conspiracy Theories', text)
        self.assertIn('Not Antisemitic', text)
        self.assertIn('synthetic-reviewer', text)
        self.assertIn(decision['decision_id'], text)
        self.assertTrue('őű Ж' in text or ('U+0151' in text and 'U+0171' in text))
        self.assertNotIn('/OpenAction', str(PdfReader(io.BytesIO(response.content)).trailer['/Root']))
        with _connect(self.runs) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM threat_report_exports').fetchone()[0], 1)
            saved_path = Path(conn.execute('SELECT pdf_path FROM threat_report_exports').fetchone()[0])
        snapshot = json.loads(saved_path.with_suffix('.json').read_text())
        from backend.services.case_report_service import _digest
        digest = snapshot.pop('snapshot_sha256')
        self.assertEqual(_digest(snapshot), digest)
        self.assertEqual(snapshot['case']['post_text'], 'Synthetic evidence only: őű Ж <script>not markup</script> 🧐')

    def test_false_alarm_or_changed_evidence_revokes_export_and_retains_history(self):
        confirmed = self.decide()
        self.decide('false_alarm', None)
        with self.assertRaises(CaseConflict):
            export_threat_pdf(runs_dir=self.runs, run_id='case-test', row_index=2, actor='test')
        self.assertEqual(run_reports(runs_dir=self.runs, run_id='case-test')['summary']['false_alarms'], 1)
        self.decide()
        with _connect(self.runs) as conn:
            conn.execute('UPDATE run_rows SET post_text=? WHERE run_id=? AND row_index=?', ('New source evidence', 'case-test', 2))
        self.assertFalse(get_case(runs_dir=self.runs, run_id='case-test', row_index=2)['can_export'])
        self.assertEqual(run_reports(runs_dir=self.runs, run_id='case-test')['summary']['unresolved'], 1)
        with _connect(self.runs) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM case_decision_history').fetchone()[0], 3)
        with self.assertRaises(CaseConflict):
            record_decision(runs_dir=self.runs, run_id='case-test', row_index=2, outcome='confirmed_threat', category='Anti-Israel', note='', actor='test', case_token=confirmed['case_token'])

    def test_legacy_review_edit_revokes_confirmation(self):
        self.decide()
        update_run_row_review(runs_dir=self.runs, run_id='case-test', row_index=2, review_state='escalated', review_decision=None, reviewer_note='Reopened')
        self.assertFalse(get_case(runs_dir=self.runs, run_id='case-test', row_index=2)['can_export'])

    def test_concurrent_review_token_cannot_overwrite_saved_decision(self):
        current = get_case(runs_dir=self.runs, run_id='case-test', row_index=2)
        self.decide()
        with self.assertRaises(CaseConflict):
            record_decision(runs_dir=self.runs, run_id='case-test', row_index=2, outcome='false_alarm', category=None, note='', actor='second reviewer', case_token=current['case_token'])

    def test_invalid_or_empty_threat_cannot_be_confirmed(self):
        with self.assertRaises(ValueError): self.decide(category='Not Antisemitic')
        with _connect(self.runs) as conn:
            conn.execute('UPDATE run_rows SET post_text=? WHERE run_id=? AND row_index=?', ('', 'case-test', 2))
        with self.assertRaises(ValueError): self.decide()

    def test_long_unicode_post_generates_multiple_valid_pages(self):
        with _connect(self.runs) as conn:
            conn.execute('UPDATE run_rows SET post_text=? WHERE run_id=? AND row_index=?', (('Synthetic post őű Ж & <evidence>\n' * 450), 'case-test', 2))
        self.decide()
        path = export_threat_pdf(runs_dir=self.runs, run_id='case-test', row_index=2, actor='test')
        reader = PdfReader(path)
        self.assertGreater(len(reader.pages), 1)
        for index, page in enumerate(reader.pages, 1):
            self.assertIn(f'Page {index}', page.extract_text())
            self.assertEqual(round(float(page.mediabox.width)), 595)

    def test_saved_pdf_download_is_revoked_when_superseded_and_checked_for_tampering(self):
        self.login('reviewer')
        self.decide()
        response = self.client.post('/runs/case-test/cases/2/report.pdf')
        self.assertEqual(response.status_code, 200)
        report = self.client.get('/runs/case-test/reports').json()['exports'][0]
        url = f"/runs/case-test/threat-reports/{report['report_id']}.pdf"
        self.assertEqual(self.client.get(url).content, response.content)
        with _connect(self.runs) as conn:
            path = Path(conn.execute('SELECT pdf_path FROM threat_report_exports WHERE report_id=?', (report['report_id'],)).fetchone()[0])
        original = path.read_bytes()
        path.write_bytes(original + b'changed')
        self.assertEqual(self.client.get(url).status_code, 409)
        path.write_bytes(original)
        self.decide('false_alarm', None)
        self.assertEqual(self.client.get(url).status_code, 409)
        self.assertEqual(self.client.get('/runs/case-test/reports').json()['exports'][0]['is_current'], 0)

    def test_case_paging_and_report_attachment(self):
        self.login('reviewer')
        self.assertEqual(self.client.get('/runs/case-test/cases?limit=201').status_code, 422)
        self.assertEqual(self.client.get('/runs/case-test/cases?offset=100').json()['rows'], [])
        (self.runs/'case-test'/'evaluation_report.json').write_text(json.dumps({'sample_rows': 30, 'matches_reference': 8, 'reference_agreement_percent': 26.67}))
        self.assertEqual(self.client.get('/runs/case-test/reports').json()['evaluation']['matches_reference'], 8)

    def test_review_workflow_moves_cases_between_exclusive_buckets(self):
        self.login('reviewer')
        def page(bucket): return self.client.get('/runs/case-test/cases?bucket=' + bucket).json()
        self.assertEqual(page('waiting')['counts'], {'total': 1, 'waiting': 1, 'follow_up': 0, 'confirmed_threat': 0, 'false_alarm': 0, 'automatic': 0, 'automatic_pending': 0, 'reporting': 0})
        self.decide('unresolved', None)
        self.assertEqual(page('waiting')['rows'], [])
        self.assertEqual(page('follow_up')['rows'][0]['workflow_bucket'], 'follow_up')
        self.decide()
        self.assertEqual(page('follow_up')['rows'], [])
        self.assertTrue(page('confirmed_threat')['rows'][0]['can_export'])
        self.decide('false_alarm', None)
        self.assertEqual(page('confirmed_threat')['rows'], [])
        self.assertFalse(page('false_alarm')['rows'][0]['can_export'])
        with _connect(self.runs) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM case_decision_history').fetchone()[0], 3)
            conn.execute("UPDATE run_rows SET post_text='Changed evidence' WHERE run_id='case-test'")
        self.assertEqual(page('false_alarm')['rows'], [])
        self.assertEqual(page('waiting')['total'], 1)

    def test_oldest_ready_order_is_stable_and_global_across_pages(self):
        self.login('reviewer')
        upsert_run_rows(runs_dir=self.runs, run_id='case-test', upload_id=None, rows=[
            {'row_index': i, 'post_text': 'Synthetic workflow case', 'review_required': True, 'assigned_category': 'Not Antisemitic', 'flags': []}
            for i in range(3, 208)])
        with _connect(self.runs) as conn:
            conn.execute("UPDATE run_rows SET created_at=100 WHERE run_id='case-test'")
            conn.execute("UPDATE run_rows SET created_at=1 WHERE run_id='case-test' AND row_index=207")
        page = self.client.get('/runs/case-test/cases?bucket=waiting&limit=100').json()
        self.assertEqual([r['row_index'] for r in page['rows'][:3]], [207, 2, 3])
        self.decide('false_alarm', None)
        page = self.client.get('/runs/case-test/cases?bucket=waiting&offset=100&limit=100').json()
        self.assertEqual(page['total'], 205)
        self.assertNotIn(2, [r['row_index'] for r in page['rows']])
        cleared = self.client.get('/runs/case-test/cases?bucket=false_alarm&offset=100').json()
        self.assertEqual(cleared['offset'], 0)
        self.assertEqual([r['row_index'] for r in cleared['rows']], [2])
        self.assertEqual(sum(cleared['counts'][k] for k in ['waiting','follow_up','confirmed_threat','false_alarm']), 206)
        self.assertEqual(self.client.get('/runs/case-test/cases?bucket=unknown').status_code, 422)

    def test_next_oldest_waiting_after_each_decision_and_arriving_results(self):
        self.login('reviewer')
        upsert_run_rows(runs_dir=self.runs, run_id='case-test', upload_id=None, rows=[
            {'row_index': i, 'post_text': 'Synthetic workflow case', 'review_required': True, 'assigned_category': 'Not Antisemitic', 'flags': []}
            for i in [3, 4]])
        def waiting(): return self.client.get('/runs/case-test/cases?bucket=waiting').json()
        self.assertEqual(waiting()['rows'][0]['row_index'], 2)
        self.decide('unresolved', None)
        self.assertEqual(waiting()['rows'][0]['row_index'], 3)
        for row in waiting()['rows']:
            record_decision(runs_dir=self.runs, run_id='case-test', row_index=row['row_index'], outcome='false_alarm', category=None, note='', actor='synthetic-reviewer', case_token=row['case_token'])
        self.assertEqual(waiting()['rows'], [])
        upsert_run_rows(runs_dir=self.runs, run_id='case-test', upload_id=None, rows=[
            {'row_index': 5, 'post_text': 'Newly classified synthetic post', 'review_required': True, 'assigned_category': 'Not Antisemitic', 'flags': []}])
        self.assertEqual(waiting()['rows'][0]['row_index'], 5)
        self.assertEqual(waiting()['counts']['follow_up'], 1)

    def test_confident_results_are_automatic_and_not_pending_human_confirmation(self):
        self.login('reviewer')
        with _connect(self.runs) as conn:
            conn.execute("UPDATE run_rows SET review_required=0 WHERE run_id='case-test'")
        waiting = self.client.get('/runs/case-test/cases?bucket=waiting').json()
        self.assertEqual(waiting['total'], 0)
        automatic = self.client.get('/runs/case-test/cases?bucket=automatic').json()
        self.assertEqual(automatic['counts']['automatic'], 1)
        self.assertEqual(automatic['rows'][0]['outcome'], 'automatic')
        self.assertFalse(automatic['rows'][0]['can_export'])
        summary = self.client.get('/runs/case-test/reports').json()['summary']
        self.assertEqual(summary['unresolved'], 0)
        self.assertEqual(summary['automatic'], 1)
        # Optional review remains possible; it is a real human decision, not automatic confirmation.
        self.decide()
        self.assertEqual(self.client.get('/runs/case-test/cases?bucket=automatic').json()['total'], 0)
        self.assertEqual(self.client.get('/runs/case-test/cases?bucket=confirmed_threat').json()['total'], 1)

    def test_exception_policy_reconciliation_preserves_evidence_decisions_and_resume_payload(self):
        from src.excel_io import stable_row_hash
        from backend.services.review_routing_service import reconcile_exception_review
        from backend.services.run_state_service import read_run_record, write_run_record
        source = get_case(runs_dir=self.runs, run_id='case-test', row_index=2)['post_text']
        with _connect(self.runs) as conn:
            conn.execute("UPDATE run_rows SET source_row_hash=?,drafted_text=?,flags_json=?,fallback_events_json=? WHERE run_id='case-test'", (
                stable_row_hash('synthetic-1', source), source, json.dumps(['DRAFTER_CONTENT_CHANGED','REVIEW_REQUIRED']), json.dumps(['DRAFTER_OUTPUT_REJECTED'])))
        decision = self.decide('false_alarm', None)
        upsert_run_rows(runs_dir=self.runs, run_id='case-test', upload_id=None, rows=[
            {'row_index': 3, 'item_number': 'safe', 'post_text': 'Synthetic safe source', 'source_row_hash': stable_row_hash('safe','Synthetic safe source'), 'drafted_text': 'Synthetic safe source', 'assigned_category': 'Not Antisemitic', 'confidence_score': .99, 'flags': ['REVIEW_REQUIRED','DRAFTER_CONTENT_CHANGED'], 'fallback_events': ['DRAFTER_OUTPUT_REJECTED'], 'review_required': True},
            {'row_index': 4, 'post_text': 'Synthetic uncertain source', 'assigned_category': 'Not Antisemitic', 'confidence_score': .2, 'flags': ['REVIEW_REQUIRED'], 'review_required': True},
            {'row_index': 5, 'post_text': 'Unverified source', 'drafted_text': 'Unverified source', 'assigned_category': 'Not Antisemitic', 'confidence_score': .99, 'flags': ['REVIEW_REQUIRED','DRAFTER_CONTENT_CHANGED'], 'fallback_events': ['DRAFTER_OUTPUT_REJECTED'], 'review_required': True}])
        record = read_run_record(runs_dir=self.runs, run_id='case-test')
        record['review_mode']='full';record['start_payload']={'review_mode':'full'}
        write_run_record(runs_dir=self.runs, run_id='case-test', record=record)
        report = reconcile_exception_review(runs_dir=self.runs, run_id='case-test', ssot_path=Path(__file__).resolve().parents[1]/'ssot/ssot.json')
        self.assertEqual(report['verified_drafter_recoveries'], 2)
        self.assertTrue(Path(report['backup']).is_file())
        self.assertEqual(get_case(runs_dir=self.runs, run_id='case-test', row_index=2)['decision_id'],decision['decision_id'])
        self.assertEqual(get_case(runs_dir=self.runs, run_id='case-test', row_index=2)['case_token'],decision['case_token'])
        self.assertEqual(get_case(runs_dir=self.runs, run_id='case-test', row_index=3)['outcome'],'automatic')
        self.assertEqual(get_case(runs_dir=self.runs, run_id='case-test', row_index=4)['workflow_bucket'],'waiting')
        self.assertEqual(get_case(runs_dir=self.runs, run_id='case-test', row_index=5)['workflow_bucket'],'waiting')
        self.assertEqual(read_run_record(runs_dir=self.runs,run_id='case-test')['start_payload']['review_mode'],'partial')
        # Reading an empty exception queue must not backfill historical full-review flags.
        from backend.services.run_state_service import _review_state_from_canonical
        with _connect(self.runs) as conn:
            conn.execute("UPDATE run_rows SET review_required=0 WHERE run_id='case-test'")
        from unittest.mock import patch
        with patch('backend.services.run_state_service.migrate_run_rows_to_canonical', side_effect=AssertionError('Canonical rows already exist')):
            self.assertEqual(_review_state_from_canonical(runs_dir=self.runs,run_id='case-test')['rows'],{})

    def test_unfinished_machine_checks_are_separate_from_human_work_and_completed_results(self):
        self.login('reviewer')
        self.decide('false_alarm',None)
        upsert_run_rows(runs_dir=self.runs,run_id='case-test',upload_id=None,rows=[
            {'row_index':3,'post_text':'Synthetic unresolved','assigned_category':'Not Antisemitic','confidence_score':.7,'flags':['REVIEW_REQUIRED'],'review_required':True},
            {'row_index':4,'post_text':'Synthetic previously automatic','assigned_category':'Not Antisemitic','confidence_score':.99,'flags':[],'review_required':False}])
        path=self.runs/'case-test'/'automatic_recheck.json'
        plan={'state':'running','total':3,'processed':0,'resolved':0,'remaining':3,'row_indices':[2,3,4],'done_rows':[]}
        path.write_text(json.dumps(plan))
        def page(bucket):return self.client.get('/runs/case-test/cases?bucket='+bucket).json()
        self.assertEqual(page('waiting')['rows'],[])
        self.assertEqual(page('automatic')['rows'],[])
        self.assertEqual([r['row_index'] for r in page('automatic_pending')['rows']],[3,4])
        self.assertEqual(page('false_alarm')['rows'][0]['row_index'],2)
        counts=page('automatic_pending')['counts']
        self.assertEqual(sum(counts[k] for k in ['waiting','automatic_pending','automatic','follow_up','confirmed_threat','false_alarm','reporting']),counts['total'])
        summary=self.client.get('/runs/case-test/reports').json()['summary']
        self.assertEqual(summary['unresolved'],0)
        self.assertEqual(summary['automatic_pending'],2)
        from backend.services.run_state_service import _project_review_state_from_run_rows,refresh_run_record
        from backend.services.ops_db_service import summarize_run_rows
        self.assertEqual(list(_project_review_state_from_run_rows(runs_dir=self.runs,run_id='case-test')['rows']),['2'])
        self.assertEqual(summarize_run_rows(runs_dir=self.runs,run_id='case-test')['review_required_rows_detected'],1)
        self.assertEqual(refresh_run_record(runs_dir=self.runs,run_id='case-test')['review_summary']['pending_rows'],0)
        case=get_case(runs_dir=self.runs,run_id='case-test',row_index=3)
        self.assertEqual(case['outcome'],'automatic_pending')
        self.assertEqual(case['review_reasons'],[])
        response=self.client.post('/runs/case-test/cases/3/decision',json={'outcome':'false_alarm','case_token':case['case_token']})
        self.assertEqual(response.status_code,409)
        # Checks complete, but could not resolve row 3. Only now does it enter the human queue.
        plan['done_rows']=[3];plan['processed']=1;path.write_text(json.dumps(plan))
        self.assertEqual([r['row_index'] for r in page('waiting')['rows']],[3])
        ready=get_case(runs_dir=self.runs,run_id='case-test',row_index=3)
        self.assertNotEqual(case['case_token'],ready['case_token'])
        self.assertEqual(self.client.post('/runs/case-test/cases/3/decision',json={'outcome':'false_alarm','case_token':case['case_token']}).status_code,409)
        self.assertEqual(self.client.post('/runs/case-test/cases/3/decision',json={'outcome':'false_alarm','case_token':ready['case_token']}).status_code,200)
        # Finished successful checks go straight to Automatic, never through the human queue.
        plan['done_rows']=[3,4];plan['processed']=2;path.write_text(json.dumps(plan))
        self.assertEqual(page('waiting')['total'],0)
        self.assertEqual(page('automatic_pending')['total'],0)
        self.assertEqual([r['row_index'] for r in page('automatic')['rows']],[4])
        self.assertEqual(page('false_alarm')['total'],2)

    def test_pending_filtering_is_global_and_survives_paused_or_inconsistent_plan_state(self):
        self.login('reviewer')
        upsert_run_rows(runs_dir=self.runs,run_id='case-test',upload_id=None,rows=[
            {'row_index':i,'post_text':'Synthetic pending case','assigned_category':'Not Antisemitic','flags':['REVIEW_REQUIRED'],'review_required':True}
            for i in range(3,208)])
        path=self.runs/'case-test'/'automatic_recheck.json'
        plan={'state':'paused','row_indices':list(range(2,208)),'done_rows':[]}
        path.write_text(json.dumps(plan))
        self.assertEqual(self.client.get('/runs/case-test/cases?bucket=waiting').json()['total'],0)
        pending=self.client.get('/runs/case-test/cases?bucket=automatic_pending&offset=100').json()
        self.assertEqual(pending['total'],206);self.assertEqual(pending['rows'][0]['row_index'],102)
        plan['state']='completed';path.write_text(json.dumps(plan))
        self.assertEqual(self.client.get('/runs/case-test/cases?bucket=waiting').json()['total'],0)
        # A broken plan must not silently turn its unfinished cases into human work.
        path.write_text('invalid JSON')
        from backend.services.recheck_queue_service import pending_recheck_rows
        with self.assertRaises(RuntimeError):pending_recheck_rows(self.runs,'case-test')


if __name__ == '__main__':
    unittest.main()
