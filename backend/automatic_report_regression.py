from __future__ import annotations
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from pypdf import PdfReader
import backend.main as main
from backend.services import auth_service
from backend.services.ops_db_service import _connect,upsert_run_rows
from backend.services.run_state_service import create_run_record,refresh_run_record
from backend.services.automatic_report_service import enable_reporting_policy,positive_findings,refresh_automatic_report
from backend.services.case_report_service import get_case,record_decision,case_page

class AutomaticReportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.runs=Path(self.temp.name);self.previous=main.RUNS_DIR;main.RUNS_DIR=self.runs
        auth_service._SESSIONS.clear();self.client=TestClient(main.app)
        create_run_record(runs_dir=self.runs,run_id='ai-test',input_path='input.xlsx',output_path='output.xlsx',upload_id=None,language='de',review_mode='partial')
        policy=self.runs/'policy.json';policy.write_text(json.dumps({'automatic_reporting':{'enabled':True,'minimum_positive_confidence':.30}}))
        enable_reporting_policy(runs_dir=self.runs,run_id='ai-test',ssot_path=policy)
    def tearDown(self):
        main.RUNS_DIR=self.previous;auth_service._SESSIONS.clear();self.temp.cleanup()
    def row(self,category='Not Antisemitic',score=.99,trace=None,flags=None):
        return {'row_index':2,'item_number':'synthetic','post_text':'Synthetic QA evidence only: őű Ж. No real person or real threat is represented.','assigned_category':category,'confidence_score':score,'explanation':'Synthetic model analysis.','flags':flags or [],'fallback_events':[],'review_required':True,'audit_trace':trace or {}}
    def store(self,row):
        upsert_run_rows(runs_dir=self.runs,run_id='ai-test',upload_id=None,rows=[row])
        return get_case(runs_dir=self.runs,run_id='ai-test',row_index=2)
    def login(self,role='operator'):
        self.assertEqual(self.client.post('/auth/login',json={'role':role,'actor_name':'synthetic-actor','access_code':'spot-local'}).status_code,200)
    def test_threshold_is_inclusive_and_never_inverts_negative_confidence(self):
        for score,eligible in [(.29999,False),(.30,True),(1,True),(float('nan'),False),(float('inf'),False),(-1,False),(True,False)]:
            self.assertEqual(bool(positive_findings(self.row('Anti-Israel',score))),eligible)
        self.assertEqual(positive_findings(self.row('Not Antisemitic',.99)),[])
        self.assertEqual(positive_findings(self.row('unknown harm label',.99)),[])
        self.assertEqual(positive_findings(self.row('Anti-Israel',.99,flags=['ANALYSIS_FAILED'])),[])
    def test_any_positive_model_or_retry_triggers_even_if_final_result_is_negative(self):
        for trace in [{'initial':{'model':'mock-primary','category':'Anti-Israel','confidence':.3,'flags':[]}}, {'alternate':{'model':'mock-independent','category':'Conspiracy Theories','confidence':.3,'flags':[]}}, {'initial':{'model':'mock-primary','category':'Not Antisemitic','confidence':.99,'flags':[],'attempts':{'initial_response':{'category':'Anti-Judaism','confidence':.3,'flags':'malformed metadata'}}}}]:
            with self.subTest(trace=trace):self.assertTrue(positive_findings(self.row(trace=trace)))
    def test_pdf_is_generated_without_human_review_and_pending_checks_route_to_reporting(self):
        (self.runs/'ai-test'/'automatic_recheck.json').write_text(json.dumps({'state':'running','row_indices':[2],'done_rows':[]}))
        case=self.store(self.row(trace={'initial':{'model':'mock-positive','category':'Anti-Israel','confidence':.3,'flags':[]},'alternate':{'model':'mock-negative','category':'Not Antisemitic','confidence':.99,'flags':[]},'judge_score':.4,'judge_verdict':'REVIEW'}))
        self.assertEqual(case['outcome'],'ai_reported');self.assertEqual(case['workflow_bucket'],'reporting');self.assertFalse(case['can_export'])
        self.assertEqual(case['automatic_report']['state'],'generated')
        self.assertFalse(case['human_review_required'])
        from src.pipeline import _canonical_review_overrides
        self.assertFalse(_canonical_review_overrides(self.runs,'ai-test')[2])
        from src.pipeline import _canonical_automatic_report_rows
        self.assertEqual(_canonical_automatic_report_rows(self.runs,'ai-test'),{2})
        self.assertEqual(case_page(runs_dir=self.runs,run_id='ai-test',bucket='waiting')['total'],0)
        self.assertEqual(case_page(runs_dir=self.runs,run_id='ai-test',bucket='automatic_pending')['total'],0)
        self.assertEqual(refresh_run_record(runs_dir=self.runs,run_id='ai-test')['review_summary']['pending_rows'],0)
        report_id=case['automatic_report']['report_id'];url=f'/runs/ai-test/automatic-reports/{report_id}.pdf'
        self.assertEqual(self.client.get(url).status_code,401)
        self.login()  # operator: read-permission alone is no longer enough to export a branded PDF
        self.assertEqual(self.client.get(url).status_code,403)
        self.login('reviewer');response=self.client.get(url);self.assertEqual(response.status_code,200)
        text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
        for value in ['{spot}','AI-GENERATED','UNCONFIRMED','30.0%','Not Antisemitic','mock-positive','mock-negative']:
            self.assertIn(value,text)
        self.assertNotIn('CONFIRMED THREAT REPORT',text)
        self.assertIn('No human decision is recorded in this AI report',text)
        self.login()  # operator again: human-confirmed export is denied for this role
        self.assertEqual(self.client.post('/runs/ai-test/cases/2/report.pdf').status_code,403)
        with _connect(self.runs) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM case_decisions').fetchone()[0],0)
            record=conn.execute('SELECT snapshot_path FROM automatic_report_exports').fetchone()
        snapshot=json.loads(Path(record['snapshot_path']).read_text());self.assertFalse(snapshot['human_confirmed'])
        self.assertEqual(snapshot['case']['assigned_category'],'Not Antisemitic')
    def test_ai_report_endpoints_require_report_export_permission(self):
        case=self.store(self.row('Anti-Israel',.3));report_id=case['automatic_report']['report_id']
        download=f'/runs/ai-test/automatic-reports/{report_id}.pdf';generate='/runs/ai-test/cases/2/automatic-report.pdf'
        self.assertEqual(self.client.get(download).status_code,401)
        self.login()  # operator can upload and start runs but must not export reports
        self.assertEqual(self.client.get(download).status_code,403)
        self.assertEqual(self.client.post(generate).status_code,403)
        for role in ('reviewer','acceptance_lead','admin'):
            self.login(role)
            self.assertEqual(self.client.get(download).status_code,200,role)
            self.assertEqual(self.client.post(generate).status_code,200,role)

    def test_repeated_generation_is_idempotent_and_tampering_requires_regeneration(self):
        row=self.row('Classical Antisemitism',.3);case=self.store(row);first=case['automatic_report']['report_id'];self.store(row)
        with _connect(self.runs) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM automatic_report_exports').fetchone()[0],1)
            path=Path(conn.execute('SELECT pdf_path FROM automatic_report_exports').fetchone()[0])
        self.login('reviewer');path.write_bytes(path.read_bytes()+b'tampered')
        self.assertEqual(self.client.get(f'/runs/ai-test/automatic-reports/{first}.pdf').status_code,409)
        self.assertEqual(self.client.post('/runs/ai-test/cases/2/automatic-report.pdf').status_code,200)
        second=get_case(runs_dir=self.runs,run_id='ai-test',row_index=2)['automatic_report']['report_id'];self.assertNotEqual(first,second)
        self.assertEqual(self.client.get(f'/runs/ai-test/automatic-reports/{first}.pdf').status_code,409)
    def test_human_false_alarm_is_preserved_and_suppresses_automatic_reports(self):
        row=self.row('Anti-Israel',.9);case=self.store(row);report_id=case['automatic_report']['report_id']
        saved=record_decision(runs_dir=self.runs,run_id='ai-test',row_index=2,outcome='false_alarm',category=None,note='Human decision must win',actor='human-reviewer',case_token=case['case_token'])
        self.store(row);current=get_case(runs_dir=self.runs,run_id='ai-test',row_index=2)
        self.assertEqual(current['decision_id'],saved['decision_id']);self.assertEqual(current['decision_note'],'Human decision must win');self.assertIsNone(current['automatic_report'])
        self.login('reviewer');self.assertEqual(self.client.get(f'/runs/ai-test/automatic-reports/{report_id}.pdf').status_code,409)
    def test_new_negative_analysis_supersedes_ai_pdf_but_retains_immutable_export_history(self):
        case=self.store(self.row('Anti-Israel',.3));old=case['automatic_report']['report_id'];new=self.store(self.row('Not Antisemitic',.99))
        self.assertIsNone(new['automatic_report']);self.login('reviewer')
        self.assertEqual(self.client.get(f'/runs/ai-test/automatic-reports/{old}.pdf').status_code,409)
        with _connect(self.runs) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM automatic_report_exports').fetchone()[0],1)
    def test_pdf_failure_remains_in_reporting_and_can_retry_without_human_decision(self):
        with patch('backend.services.threat_pdf_service.render_threat_pdf',side_effect=OSError('Synthetic renderer failure')):
            case=self.store(self.row('Anti-Israel',.3))
        self.assertEqual(case['workflow_bucket'],'reporting');self.assertEqual(case['automatic_report']['state'],'failed')
        self.assertEqual(case_page(runs_dir=self.runs,run_id='ai-test',bucket='waiting')['total'],0)
        self.login('reviewer');self.assertEqual(self.client.post('/runs/ai-test/cases/2/automatic-report.pdf').status_code,200)

if __name__=='__main__':unittest.main()
