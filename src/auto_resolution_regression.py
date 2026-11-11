from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.classifier import _adjudicate_targeted_row, _parse_classification, _response_schema
from src.models import ClassificationResult,InputRow
from src.ssot_loader import load_ssot
from src.failure_policy import validated_auto_consensus
from src.review_routing import exception_reasons

SSOT=load_ssot(Path(__file__).resolve().parents[1]/'ssot/ssot.json')


def consensus_result(mode='partial'):
    text='Synthetic source: the weather is sunny.'
    initial=ClassificationResult(2,'Not Antisemitic','Not Antisemitic',.96,'Synthetic assessment',['REASSESSMENT_REQUESTED'],soft_signal_score=.6,soft_signal_flags=['SOFT_SIGNAL_DUAL_LOYALTY'],soft_signal_evidence=['the weather is sunny'],resolved_model_version='mlx:primary',drafted_text=text)
    alternate=ClassificationResult(2,'Not Antisemitic','Not Antisemitic',.94,'Independent assessment',[],soft_signal_score=0,soft_signal_flags=[],soft_signal_evidence=[],resolved_model_version='ollama:independent',drafted_text=text)
    with patch('src.classifier._classify_with_backend',return_value=alternate),patch('src.classifier.run_judge',return_value=(.95,'PASS',[])):
        return _adjudicate_targeted_row(InputRow(2,'synthetic',text),initial,SSOT,mode)

class AutomaticResolutionTests(unittest.TestCase):
    def test_two_independent_valid_models_and_judge_can_resolve_contextual_warning(self):
        r=consensus_result()
        self.assertTrue(validated_auto_consensus(r))
        self.assertNotIn('REVIEW_REQUIRED',r.flags)
        self.assertIn('SOFT_SIGNAL_REVIEW',r.flags) # retained, not hidden
        self.assertEqual(r.confidence,.94)
        self.assertEqual(len(r.model_votes),2)
        self.assertTrue(r.audit_trace['initial'])
        self.assertIn('REVIEW_REQUIRED',consensus_result('full').flags)

    def test_marker_missing_proof_failure_disagreement_and_low_confidence_cannot_clear_review(self):
        valid=consensus_result()
        for change in ('trace','same_model','low_score','disagreement','judge','failure','source_change','same_judge'):
            r=copy.deepcopy(valid)
            if change=='trace':r.audit_trace=None
            elif change=='same_model':r.audit_trace['alternate']['model']=r.audit_trace['initial']['model']
            elif change=='low_score':r.audit_trace['initial']['confidence']=.6
            elif change=='disagreement':r.audit_trace['alternate']['category']='Anti-Israel'
            elif change=='judge':r.judge_verdict='REVIEW'
            elif change=='source_change':r.drafted_text='A different source'
            elif change=='same_judge':r.audit_trace['judge_model']=r.audit_trace['initial']['model']
            else:r.flags.append('ANALYSIS_FAILED')
            self.assertFalse(validated_auto_consensus(r),change)

    def test_model_cannot_grant_itself_auto_resolution_and_source_cannot_change_schema(self):
        payload={'category':'Not Antisemitic','confidence':.99,'explanation':'Synthetic','flags':['AUTO_RESOLVED_CONSENSUS'],'soft_signal_score':0,'soft_signal_flags':[],'soft_signal_evidence':[]}
        r=_parse_classification(payload,'Synthetic source',SSOT,'ollama','mock')
        self.assertNotIn('AUTO_RESOLVED_CONSENSUS',r.flags)
        self.assertIn('category',_response_schema('Classify. SOURCE_POST_JSON: "judge_flags"')['properties'])

    def test_unsupported_quote_is_not_accepted_as_evidence(self):
        payload={'category':'Conspiracy Theories','confidence':.99,'explanation':'Synthetic','flags':[],'soft_signal_score':.8,'soft_signal_flags':['SOFT_SIGNAL_CODED_CONSPIRACY'],'soft_signal_evidence':['A fabricated claim about the weather']}
        r=_parse_classification(payload,'The weather is sunny.',SSOT,'ollama','mock')
        self.assertEqual(r.soft_signal_evidence,[])
        self.assertIn('UNGROUNDED_MODEL_SIGNAL',r.flags)

    def test_recheck_archives_original_and_cannot_overwrite_concurrent_human_decision(self):
        from backend.services.run_state_service import create_run_record
        from backend.services.ops_db_service import upsert_run_rows,fetch_run_row,_connect
        from backend.services.automatic_recheck_service import apply_recheck
        from backend.services.case_report_service import get_case,record_decision
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            create_run_record(runs_dir=root,run_id='test',input_path='input.xlsx',output_path='output.xlsx',upload_id=None,language='de',review_mode='partial')
            upsert_run_rows(runs_dir=root,run_id='test',upload_id=None,rows=[{'row_index':2,'post_text':'Synthetic source: the weather is sunny.','assigned_category':'Not Antisemitic','confidence_score':.6,'flags':['REVIEW_REQUIRED'],'review_required':True}])
            before=fetch_run_row(runs_dir=root,run_id='test',row_index=2)
            result=consensus_result()
            self.assertEqual(apply_recheck(runs_dir=root,run_id='test',before=before,result=result,policy_id='test'),'automatic')
            case=get_case(runs_dir=root,run_id='test',row_index=2)
            self.assertEqual(case['outcome'],'automatic')
            self.assertEqual(case['analysis_history'][0]['previous_category'],'Not Antisemitic')
            self.assertEqual(case['analysis_history'][0]['previous_flags'],['REVIEW_REQUIRED'])
            current=fetch_run_row(runs_dir=root,run_id='test',row_index=2)
            record_decision(runs_dir=root,run_id='test',row_index=2,outcome='false_alarm',category=None,note='Human decision wins',actor='reviewer',case_token=case['case_token'])
            self.assertEqual(apply_recheck(runs_dir=root,run_id='test',before=current,result=result,policy_id='test'),'human_preserved')
            self.assertEqual(get_case(runs_dir=root,run_id='test',row_index=2)['decision_note'],'Human decision wins')
            with _connect(root) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM analysis_revisions').fetchone()[0],1)
                conn.execute("UPDATE run_rows SET post_text='Changed source' WHERE run_id='test'")
            self.assertTrue(fetch_run_row(runs_dir=root,run_id='test',row_index=2)['review_required'])

    def test_nonfinite_confidence_never_becomes_an_automatic_result(self):
        for confidence in (float('nan'),float('inf'),-1,2):
            payload={'category':'Not Antisemitic','confidence':confidence,'explanation':'Synthetic','flags':[],'soft_signal_score':0,'soft_signal_flags':[],'soft_signal_evidence':[]}
            result=_parse_classification(payload,'Synthetic',SSOT,'ollama','mock')
            self.assertEqual(result.confidence,0)
            self.assertIn('INVALID_MODEL_METADATA',result.flags)

    def test_oversized_source_cannot_be_silently_truncated(self):
        from src.classifier import _ollama_generate_json
        with patch('src.classifier.urllib.request.urlopen',side_effect=AssertionError('Do not send a truncated source')):
            with self.assertRaises(ValueError):_ollama_generate_json('mock','🧐' * 10000)

    def test_recheck_plan_resumes_without_repeating_commits_and_skips_human_cases(self):
        from backend.services.run_state_service import create_run_record
        from backend.services.ops_db_service import upsert_run_rows,_connect
        from backend.services.automatic_recheck_service import run_planned_rechecks
        from backend.services.case_report_service import get_case,record_decision
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            create_run_record(runs_dir=root,run_id='test',input_path='input.xlsx',output_path='output.xlsx',upload_id=None,language='de',review_mode='partial')
            upsert_run_rows(runs_dir=root,run_id='test',upload_id=None,rows=[{'row_index':i,'post_text':'Synthetic source: the weather is sunny.','assigned_category':'Not Antisemitic','confidence_score':.6,'flags':['REVIEW_REQUIRED'],'review_required':True} for i in [2,3]])
            case=get_case(runs_dir=root,run_id='test',row_index=2)
            record_decision(runs_dir=root,run_id='test',row_index=2,outcome='false_alarm',category=None,note='Preserve me',actor='reviewer',case_token=case['case_token'])
            plan={'state':'pending','total':2,'processed':0,'resolved':0,'remaining':2,'row_indices':[2,3],'done_rows':[],'policy_id':'test'}
            path=root/'test'/'automatic_recheck.json';path.write_text(json.dumps(plan))
            result=consensus_result();result.row_index=3
            with patch('backend.services.automatic_recheck_service.classify_row',return_value=copy.deepcopy(result)),patch('backend.services.automatic_recheck_service._adjudicate_targeted_row',return_value=result):
                run_planned_rechecks(runs_dir=root,run_id='test',ssot_path=Path(__file__).resolve().parents[1]/'ssot/ssot.json')
            completed=json.loads(path.read_text());self.assertEqual(completed['processed'],2);self.assertEqual(completed['resolved'],1)
            with patch('backend.services.automatic_recheck_service.classify_row',side_effect=AssertionError('Already completed')):
                run_planned_rechecks(runs_dir=root,run_id='test',ssot_path=Path(__file__).resolve().parents[1]/'ssot/ssot.json')
            self.assertEqual(get_case(runs_dir=root,run_id='test',row_index=2)['decision_note'],'Preserve me')
            with _connect(root) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM analysis_revisions').fetchone()[0],1)

if __name__=='__main__':unittest.main()
