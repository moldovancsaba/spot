from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from src.classifier import _apply_review_mode, _classify_with_backend, _extract_last_json_object, _mlx_generate_json, classify_row
from src.models import ClassificationResult, InputRow
from src.failure_policy import enforce_result_safety, any_positive_analysis
from src.preflight import _inference_smoke_checks
from src.ssot_loader import load_ssot

SSOT = load_ssot(Path(__file__).resolve().parent.parent / 'ssot/ssot.json')


class FailureContractRegressionTests(unittest.TestCase):
    def test_any_positive_analysis_forces_review_over_a_negative_aggregate(self):
        """A negative aggregate must not clear a row that some analysis called antisemitic."""
        def result(**overrides):
            base = dict(row_index=2, raw_category='Not Antisemitic', category='Not Antisemitic',
                        confidence=.99, explanation='synthetic', flags=[])
            base.update(overrides)
            return ClassificationResult(**base)

        positive_trace = {'initial': {'model': 'mock-a', 'category': 'Anti-Israel', 'confidence': .31, 'flags': []},
                          'alternate': {'model': 'mock-b', 'category': 'Not Antisemitic', 'confidence': .99, 'flags': []}}
        flagged = enforce_result_safety(result(audit_trace=positive_trace))
        self.assertIn('REVIEW_REQUIRED', flagged.flags)
        self.assertIn('ANY_POSITIVE_ANALYSIS', flagged.flags)

        weak_trace = {'initial': {'model': 'mock-a', 'category': 'Anti-Israel', 'confidence': .29, 'flags': []},
                      'alternate': {'model': 'mock-b', 'category': 'Not Antisemitic', 'confidence': .99, 'flags': []}}
        clean = enforce_result_safety(result(audit_trace=weak_trace))
        self.assertNotIn('REVIEW_REQUIRED', clean.flags)

        negative_only = {'initial': {'model': 'mock-a', 'category': 'Not Antisemitic', 'confidence': .99, 'flags': []},
                         'alternate': {'model': 'mock-b', 'category': 'Not Antisemitic', 'confidence': .99, 'flags': []}}
        self.assertNotIn('REVIEW_REQUIRED', enforce_result_safety(result(audit_trace=negative_only)).flags)

    def test_any_positive_analysis_reads_structured_retry_branches(self):
        from src.models import ClassificationResult

        retry_trace = {'initial': {'model': 'mock-a', 'category': 'Not Antisemitic', 'confidence': .99,
                                   'flags': [], 'attempts': {'retry_response': {'category': 'Conspiracy Theories', 'confidence': .30}}}}
        res = ClassificationResult(row_index=2, raw_category='Not Antisemitic', category='Not Antisemitic',
                                   confidence=.99, explanation='synthetic', flags=[], audit_trace=retry_trace)
        self.assertTrue(any_positive_analysis(res))

    def test_missing_invalid_and_null_categories_cannot_become_unreviewed_negatives(self):
        for category in ('missing', None, '', 'invalid-label', [], {}):
            for mode in ('full', 'partial', 'none'):
                with self.subTest(category=category, mode=mode):
                    payload = {'confidence': .99, 'explanation': 'Synthetic response'}
                    if category != 'missing':
                        payload['category'] = category
                    with patch('src.classifier._generate_json', return_value=payload):
                        result = _apply_review_mode(_classify_with_backend('Sunny weather.', SSOT, 'ollama', 'mock'), SSOT, mode)
                    self.assertEqual(result.category, 'Not Antisemitic')
                    self.assertEqual(result.confidence, 0)
                    self.assertIn('ANALYSIS_FAILED', result.flags)
                    self.assertIn('REVIEW_REQUIRED', result.flags)
                    self.assertEqual(result.raw_category, 'invalid-label' if category == 'invalid-label' else '')

    def test_total_backend_failure_requires_review_even_in_none_mode(self):
        with patch('src.classifier.run_drafter', return_value=('Sunny weather.', [])), patch('src.classifier._generate_json', side_effect=TimeoutError):
            result = classify_row(InputRow(2, '1', 'Sunny weather.'), SSOT, 'none')
        self.assertEqual(result.confidence, 0)
        self.assertEqual(result.raw_category, '')
        self.assertIn('CLASSIFIER_FALLBACK_FAILED', result.flags)
        self.assertIn('REVIEW_REQUIRED', result.flags)

    def test_unstructured_result_requires_review(self):
        with patch('src.classifier._generate_json', return_value={'raw_text': 'Not antisemitic, confidence 0.99'}):
            result = _apply_review_mode(_classify_with_backend('Sunny weather.', SSOT, 'mlx', 'mock'), SSOT, 'none')
        self.assertIn('UNSTRUCTURED_MODEL_OUTPUT', result.flags)
        self.assertIn('REVIEW_REQUIRED', result.flags)

    def test_json_with_fences_trailing_metrics_and_nested_objects(self):
        self.assertEqual(_extract_last_json_object('```json\n{"category":"Not Antisemitic","nested":{"ok":true}}\n```\nGeneration: 10 tokens'), {'category': 'Not Antisemitic', 'nested': {'ok': True}})
        self.assertEqual(_extract_last_json_object('[{"category":"Not Antisemitic"}]'), {})

    def test_mlx_uses_response_only_stdout_and_keeps_valid_json(self):
        import subprocess
        with patch('src.classifier.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{"category":"Not Antisemitic"}', 'diagnostic')) as run:
            self.assertEqual(_mlx_generate_json('mock', 'synthetic'), {'category': 'Not Antisemitic'})
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index('--verbose') + 1], 'false')

    def test_mlx_timeout_does_not_expose_prompt(self):
        import subprocess
        with patch('src.classifier.subprocess.run', side_effect=subprocess.TimeoutExpired(['command', 'private source text'], 1)):
            with self.assertRaises(TimeoutError) as caught:
                _mlx_generate_json('mock', 'private source text')
        self.assertNotIn('private source text', str(caught.exception))

    def test_drafter_cannot_drop_or_translate_source_text(self):
        from src.classifier import run_drafter
        original = 'Dies ist der vollständige Originaltext mit wichtigem Kontext.'
        for changed in ('Short summary.', original[:15], 'This is the full original text.'):
            with patch('src.classifier._generate_json', side_effect=AssertionError('Preparation must not call a model')):
                drafted, flags = run_drafter(original)
            self.assertEqual(drafted, original)
            self.assertEqual(flags, [])

    def test_drafter_may_only_normalize_whitespace(self):
        from src.classifier import run_drafter
        with patch('src.classifier._generate_json', return_value={'normalized_text': 'Das Wetter ist sonnig.'}):
            drafted, flags = run_drafter('Das  Wetter\nist sonnig.')
        self.assertEqual(drafted, 'Das Wetter ist sonnig.')
        self.assertEqual(flags, [])

    def test_string_metadata_does_not_become_individual_character_flags(self):
        with patch('src.classifier._generate_json', return_value={'category': 'Not Antisemitic', 'confidence': .99, 'explanation': 'Synthetic', 'flags': 'EMPTY_TEXT', 'soft_signal_flags': 'SOFT_SIGNAL_DUAL_LOYALTY'}):
            result = _apply_review_mode(_classify_with_backend('Synthetic text', SSOT, 'mlx', 'mock'), SSOT, 'none')
        self.assertIn('INVALID_MODEL_METADATA', result.flags)
        self.assertIn('REVIEW_REQUIRED', result.flags)
        self.assertNotIn('E', result.flags)
        self.assertEqual(result.soft_signal_flags, [])

    def test_listener_check_rejects_wildcard_binding(self):
        import subprocess
        from src.preflight import _ollama_listener_check
        for address, expected in (('127.0.0.1', True), ('[::1]', True), ('*', False), ('0.0.0.0', False)):
            with patch('src.preflight.shutil.which', return_value='/usr/sbin/lsof'), patch('src.preflight.subprocess.run', return_value=subprocess.CompletedProcess([], 0, f'p123\nn{address}:11434\n', '')):
                self.assertEqual(_ollama_listener_check('http://127.0.0.1:11434/api/generate')[0], expected)

    def test_workbook_safety_matches_canonical_failure_policy(self):
        import tempfile
        from openpyxl import Workbook, load_workbook
        from src.excel_io import write_output
        from src.models import ClassificationResult
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'input.xlsx', Path(directory) / 'output.xlsx'
            workbook = Workbook()
            workbook.active.append(['Item number', 'Post text', 'Category'])
            workbook.active.append(['1', 'Synthetic text', ''])
            workbook.save(source)
            workbook.close()
            result = ClassificationResult(2, 'invalid-label', 'Not Antisemitic', .99, 'Synthetic response', ['TAXONOMY_VIOLATION'])
            write_output(source, target, SSOT, 'audit', 'de', 'none', 'test', [result], ['hash'])
            workbook = load_workbook(target)
            rows = list(workbook.active.values)
            output = dict(zip(rows[0], rows[1]))
            self.assertEqual(output['Review Required'], 'YES')
            self.assertEqual(output['Confidence Score'], 0)
            self.assertIn('ANALYSIS_FAILED', output['Flags'])
            workbook.close()

    def test_smoke_rejects_missing_output_and_reports_only_error_type(self):
        with patch('src.classifier._generate_json', return_value={'confidence': .99}):
            self.assertTrue(all(not check['ok'] for check in _inference_smoke_checks(SSOT)))
        with patch('src.classifier._classify_with_backend', side_effect=RuntimeError('private data')):
            checks = _inference_smoke_checks(SSOT)
        self.assertNotIn('private data', str(checks))

    def test_partial_mode_completes_confident_clean_analysis_without_drafter_calls(self):
        response = {'category':'Not Antisemitic','confidence':.99,'explanation':'Synthetic clear analysis','flags':[], 'soft_signal_score':0,'soft_signal_flags':[],'soft_signal_evidence':[]}
        with patch('src.classifier._generate_json',return_value=response) as generate:
            result = classify_row(InputRow(2,'synthetic','Das  Wetter ist sonnig.'),SSOT,'partial')
        self.assertEqual(generate.call_count,1)
        self.assertNotIn('REVIEW_REQUIRED',result.flags)
        self.assertNotIn('DRAFTER_CONTENT_CHANGED',result.flags)
        self.assertEqual(result.drafted_text,'Das Wetter ist sonnig.')

    def test_high_numeric_confidence_cannot_hide_other_uncertainty(self):
        from src.models import ClassificationResult
        for kwargs in [dict(flags=['INVALID_MODEL_METADATA']),dict(flags=[],judge_verdict='REVIEW'),dict(flags=['SECOND_PASS_DISAGREEMENT']),dict(flags=[],soft_signal_flags=['SOFT_SIGNAL_DUAL_LOYALTY'])]:
            result = ClassificationResult(2,'Not Antisemitic','Not Antisemitic',.99,'Synthetic analysis',**kwargs)
            self.assertIn('REVIEW_REQUIRED',_apply_review_mode(result,SSOT,'partial').flags)

    def test_canonical_review_override_does_not_hide_failure_and_keeps_historical_flags(self):
        import tempfile
        from openpyxl import Workbook,load_workbook
        from src.models import ClassificationResult
        from src.excel_io import write_output
        with tempfile.TemporaryDirectory() as directory:
            source,target=Path(directory)/'input.xlsx',Path(directory)/'output.xlsx'
            wb=Workbook();ws=wb.active;ws.append(['Item number','Post text','Category'])
            ws.append(['1','Synthetic clear post','']);ws.append(['2','','']);wb.save(source);wb.close()
            results=[ClassificationResult(2,'Not Antisemitic','Not Antisemitic',.99,'Synthetic preserved analysis',['DRAFTER_CONTENT_CHANGED','REVIEW_REQUIRED']),ClassificationResult(3,'','Not Antisemitic',0,'Failed',['ANALYSIS_FAILED','REVIEW_REQUIRED'])]
            write_output(source,target,SSOT,'synthetic','de','partial','test',results,['a','b'],review_required_overrides={2:False,3:False})
            wb=load_workbook(target,read_only=True);rows=list(wb.active.values);headers=list(rows[0])
            self.assertEqual(rows[1][headers.index('Review Required')],'NO')
            self.assertIn('DRAFTER_CONTENT_CHANGED',rows[1][headers.index('Flags')])
            self.assertEqual(rows[2][headers.index('Review Required')],'YES');wb.close()


if __name__ == '__main__':
    unittest.main()
