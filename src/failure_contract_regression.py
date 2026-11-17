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
    def test_jev_judge_disagreement_guard_routes_opposite_splits_to_review(self):
        """JEV decides, llama3.1 corroborates; an opposite PASS/FAIL split goes to a human."""
        import os
        from unittest.mock import patch as _patch

        from src.classifier import run_judge

        with _patch.dict(os.environ, {"SPOT_JEV_URL": "http://127.0.0.1:8770"}), \
                _patch("src.classifier._jev_judge", return_value=(0.87, "PASS", ["JEV_JUDGE"])), \
                _patch("src.classifier._ollama_judge", return_value=(0.31, "FAIL", [])):
            score, verdict, judge_flags = run_judge("text", "Conspiracy Theories", [])
        self.assertEqual(verdict, "REVIEW")
        self.assertIn("JEV_JUDGE_DISAGREEMENT", judge_flags)

        with _patch.dict(os.environ, {"SPOT_JEV_URL": "http://127.0.0.1:8770"}), \
                _patch("src.classifier._jev_judge", return_value=(0.87, "PASS", ["JEV_JUDGE"])), \
                _patch("src.classifier._ollama_judge", return_value=(0.82, "PASS", [])):
            score, verdict, judge_flags = run_judge("text", "Conspiracy Theories", [])
        self.assertEqual(verdict, "PASS")
        self.assertIn("JEV_LLAMA_CORROBORATED", judge_flags)

        with _patch.dict(os.environ, {"SPOT_JEV_URL": ""}), \
                _patch("src.classifier._ollama_judge", return_value=(0.82, "PASS", ["X"])):
            score, verdict, judge_flags = run_judge("text", "Conspiracy Theories", [])
        self.assertEqual((score, verdict), (0.82, "PASS"))

    def test_jev_judge_lane_maps_verdicts_and_abstention(self):
        """The local JEV service answers the judge task; the Ollama judge remains the fallback."""
        import json
        import os
        from unittest.mock import patch as _patch

        from src.classifier import _jev_judge

        captured = {}

        class FakeResponse:
            def __init__(self, body):
                self._body = body

            def read(self):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=None):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse(json.dumps({
                "selected_id": "PASS", "max_probability": 0.87, "abstained": False,
                "uncalibrated": False, "latency_ms": 120,
            }).encode())

        with _patch.dict(os.environ, {"SPOT_JEV_URL": "http://127.0.0.1:8770"}), \
                _patch("src.classifier.urllib.request.urlopen", fake_urlopen):
            score, verdict, judge_flags = _jev_judge("text", "Conspiracy Theories", [])
        self.assertEqual((score, verdict), (0.87, "PASS"))
        self.assertIn("JEV_JUDGE", judge_flags)
        self.assertIn("JEV_CALIBRATED", judge_flags)
        self.assertIn("PROPOSED_CATEGORY: Conspiracy Theories", captured["payload"]["context"])

        def abstaining_urlopen(req, timeout=None):
            return FakeResponse(json.dumps({
                "selected_id": None, "max_probability": 0.42, "abstained": True,
                "uncalibrated": True, "latency_ms": 120,
            }).encode())

        with _patch.dict(os.environ, {"SPOT_JEV_URL": "http://127.0.0.1:8770"}), \
                _patch("src.classifier.urllib.request.urlopen", abstaining_urlopen):
            score, verdict, judge_flags = _jev_judge("text", "Conspiracy Theories", [])
        self.assertEqual(verdict, "REVIEW")
        self.assertIn("JUDGE_ABSTAINED", judge_flags)

        def failing_urlopen(req, timeout=None):
            raise OSError("connection refused")

        with _patch.dict(os.environ, {"SPOT_JEV_URL": "http://127.0.0.1:8770"}), \
                _patch("src.classifier.urllib.request.urlopen", failing_urlopen):
            self.assertIsNone(_jev_judge("text", "Conspiracy Theories", []))

        with _patch.dict(os.environ, {"SPOT_JEV_URL": ""}):
            self.assertIsNone(_jev_judge("text", "Conspiracy Theories", []))

    def test_ollama_payload_releases_models_after_use(self):
        """Metal OOM in segment children was caused by two resident Ollama lanes plus the MLX model."""
        import json
        import os
        from unittest.mock import patch as _patch

        captured = {}

        class FakeResponse:
            def __init__(self, body):
                self._body = body

            def read(self):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=None):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse(json.dumps({"response": '{"category":"Not Antisemitic"}'}).encode())

        from src.classifier import _ollama_generate_json

        with _patch.dict(os.environ, {"SPOT_OLLAMA_KEEP_ALIVE": "120"}), \
                _patch("src.classifier.urllib.request.urlopen", fake_urlopen):
            result = _ollama_generate_json("qwen2.5:7b", "synthetic prompt")
        self.assertEqual(result["category"], "Not Antisemitic")
        self.assertEqual(captured["payload"]["keep_alive"], "120")

        with _patch.dict(os.environ, {"SPOT_OLLAMA_KEEP_ALIVE": "0"}), \
                _patch("src.classifier.urllib.request.urlopen", fake_urlopen):
            _ollama_generate_json("qwen2.5:7b", "synthetic prompt")
        self.assertEqual(captured["payload"]["keep_alive"], "0")

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

    def test_mlx_adapter_path_is_forwarded_in_cli_mode(self):
        """The CLI fallback must still honour a configured adapter."""
        import os
        from unittest.mock import patch as _patch

        completed = type("Done", (), {"stdout": '{"category": "Not Antisemitic", "confidence": 0.9}'})()
        with _patch("src.classifier.subprocess.run", return_value=completed) as run, \
                _patch.dict(os.environ, {"SPOT_MLX_ADAPTER_PATH": "/tmp/adapter-dir", "SPOT_MLX_CLI": "1"}):
            _mlx_generate_json("mlx-community/synthetic", "prompt text")
        command = run.call_args.args[0]
        self.assertIn("--adapter-path", command)
        self.assertEqual(command[command.index("--adapter-path") + 1], "/tmp/adapter-dir")

        with _patch("src.classifier.subprocess.run", return_value=completed) as run, \
                _patch.dict(os.environ, {"SPOT_MLX_ADAPTER_PATH": "", "SPOT_MLX_CLI": "1"}):
            _mlx_generate_json("mlx-community/synthetic", "prompt text")
        self.assertNotIn("--adapter-path", run.call_args.args[0])

    def test_mlx_in_process_loads_the_model_once_per_process(self):
        """Per-row process spawn reloaded the model every row; the in-process path must load once."""
        import os
        import sys
        import types
        from unittest.mock import patch as _patch

        from src.classifier import clear_mlx_cache

        loads = []
        generations = []

        class FakeTokenizer:
            chat_template = "{{ messages }}"

            def apply_chat_template(self, messages, add_generation_prompt=True, tokenize=False):
                return "PROMPT:" + messages[0]["content"]

        def fake_load(model, adapter_path=None):
            loads.append((model, adapter_path))
            return ("MODEL", FakeTokenizer())

        def fake_generate(model, tokenizer, prompt, max_tokens=0, sampler=None, verbose=False):
            generations.append((model, prompt))
            return '{"category": "Anti-Israel", "confidence": 0.9}'

        fake_sample_utils = types.SimpleNamespace(make_sampler=lambda temp=0.0: "SAMPLER")
        fake_module = types.SimpleNamespace(load=fake_load, generate=fake_generate, sample_utils=fake_sample_utils)
        with _patch.dict(sys.modules, {"mlx_lm": fake_module, "mlx_lm.sample_utils": fake_sample_utils}), \
                _patch.dict(os.environ, {"SPOT_MLX_ADAPTER_PATH": "/tmp/adapter-x", "SPOT_MLX_CLI": "0"}):
            clear_mlx_cache()
            first = _mlx_generate_json("mlx-community/synthetic", "first prompt")
            second = _mlx_generate_json("mlx-community/synthetic", "second prompt")
            clear_mlx_cache()

        self.assertEqual(first["category"], "Anti-Israel")
        self.assertEqual(second["category"], "Anti-Israel")
        self.assertEqual(len(loads), 1, "the model must load once per process, not once per row")
        self.assertEqual(loads[0][1], "/tmp/adapter-x")
        self.assertEqual(len(generations), 2)
        self.assertTrue(generations[0][1].startswith("PROMPT:first prompt"))

    def test_training_record_can_mirror_the_live_pipeline_prompt(self):
        """Training data must be able to match what the classifier actually sends, or an adapter is undeployable."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_training_set",
            Path(__file__).resolve().parents[1] / "script" / "build_training_set.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        piped = module.chat_record("Synthetic post text.", "Not Antisemitic", pipeline_prompt=True)
        self.assertEqual([message["role"] for message in piped["messages"]], ["user", "assistant"])
        self.assertTrue(piped["messages"][0]["content"].startswith("Classify the author's expressed position"))
        standalone = module.chat_record("Synthetic post text.", "Not Antisemitic", pipeline_prompt=False)
        self.assertEqual([message["role"] for message in standalone["messages"]], ["system", "user", "assistant"])

    def test_review_policy_modes_control_workload(self):
        """The operator must be able to trade recall against review volume, explicitly and reversibly."""
        import os
        from unittest.mock import patch as _patch

        from src.failure_policy import enforce_result_safety
        from src.models import ClassificationResult

        def clean_result():
            return ClassificationResult(row_index=2, raw_category='Not Antisemitic', category='Not Antisemitic',
                                        confidence=.96, explanation='clean', flags=[],
                                        audit_trace={'source_sha256': 'a' * 64})

        with _patch.dict(os.environ, {'SPOT_REVIEW_POLICY': 'all', 'SPOT_AUDIT_SAMPLE_PCT': '0'}):
            self.assertIn('REVIEW_REQUIRED', enforce_result_safety(clean_result()).flags)

        with _patch.dict(os.environ, {'SPOT_REVIEW_POLICY': 'suspicious', 'SPOT_AUDIT_SAMPLE_PCT': '0'}):
            self.assertNotIn('REVIEW_REQUIRED', enforce_result_safety(clean_result()).flags)

        # A complete certificate with no suspicion may clear in certificate mode.
        with _patch.dict(os.environ, {'SPOT_REVIEW_POLICY': 'certificate', 'SPOT_AUDIT_SAMPLE_PCT': '0'}):
            self.assertIn('REVIEW_REQUIRED', enforce_result_safety(clean_result()).flags)

        # SPOT_DISABLE_AUTO_CLEAR always wins, so the safest posture is one switch away.
        with _patch.dict(os.environ, {'SPOT_REVIEW_POLICY': 'suspicious', 'SPOT_DISABLE_AUTO_CLEAR': '1',
                                      'SPOT_AUDIT_SAMPLE_PCT': '0'}):
            self.assertIn('REVIEW_REQUIRED', enforce_result_safety(clean_result()).flags)

    def test_audit_sample_routes_a_deterministic_share_of_cleared_rows(self):
        """Cleared rows are invisible; a stable sample keeps the miss rate measurable."""
        import os
        from unittest.mock import patch as _patch

        from src.failure_policy import enforce_result_safety
        from src.models import ClassificationResult

        def clean_result():
            return ClassificationResult(row_index=2, raw_category='Not Antisemitic', category='Not Antisemitic',
                                        confidence=.96, explanation='clean', flags=[],
                                        audit_trace={'source_sha256': 'b' * 64})

        with _patch.dict(os.environ, {'SPOT_REVIEW_POLICY': 'suspicious', 'SPOT_AUDIT_SAMPLE_PCT': '100'}):
            flags = enforce_result_safety(clean_result()).flags
            self.assertIn('REVIEW_REQUIRED', flags)
            self.assertIn('AUDIT_SAMPLE', flags)

        with _patch.dict(os.environ, {'SPOT_REVIEW_POLICY': 'suspicious', 'SPOT_AUDIT_SAMPLE_PCT': '0'}):
            self.assertNotIn('AUDIT_SAMPLE', enforce_result_safety(clean_result()).flags)

    def test_seven_category_taxonomy_and_six_to_seven_migration(self):
        """TEV taxonomy v0.2: Holocaust Denial is first-class and the six-category mapping is lossless."""
        from pathlib import Path as _Path

        from src.models import CANONICAL_CATEGORIES
        from src.ssot_loader import load_ssot

        ssot = load_ssot(_Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")
        self.assertEqual(sorted(CANONICAL_CATEGORIES), sorted([
            "Anti-Israel", "Anti-Judaism", "Holocaust Denial",
            "Classical Antisemitism", "Structural Antisemitism",
            "Conspiracy Theories", "Not Antisemitic",
        ]))
        self.assertEqual(ssot.taxonomy.version, "taxonomy-v0.2")
        self.assertIn("Holocaust Denial", ssot.taxonomy.categories)
        self.assertEqual(ssot.taxonomy.fallback_category, "Not Antisemitic")

        # Identity mapping for all shared six-category labels; only new classifications may use the new one.
        shared = ["Anti-Israel", "Anti-Judaism", "Classical Antisemitism",
                  "Structural Antisemitism", "Conspiracy Theories", "Not Antisemitic"]
        for label in shared:
            self.assertIn(label, ssot.taxonomy.categories)

    def test_secondary_category_normalization_keeps_only_distinct_canonical_values(self):
        """secondary_category must be canonical, differ from primary, and otherwise be dropped."""
        import json

        from src.classifier import _parse_classification
        from src.models import InputRow

        ssot = load_ssot(Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")
        text = "Synthetic source post."

        def parsed(obj):
            return _parse_classification(obj, text, ssot, "ollama", "mock")

        good = parsed({"category": "Conspiracy Theories", "secondary_category": "Anti-Israel",
                       "confidence": 0.9, "explanation": "x", "flags": [],
                       "soft_signal_score": 0.0, "soft_signal_flags": [], "soft_signal_evidence": []})
        self.assertEqual(good.category, "Conspiracy Theories")
        self.assertEqual(good.secondary_category, "Anti-Israel")

        same = parsed({"category": "Conspiracy Theories", "secondary_category": "Conspiracy Theories",
                       "confidence": 0.9, "explanation": "x", "flags": [],
                       "soft_signal_score": 0.0, "soft_signal_flags": [], "soft_signal_evidence": []})
        self.assertIsNone(same.secondary_category)

        junk = parsed({"category": "Conspiracy Theories", "secondary_category": "not a category",
                       "confidence": 0.9, "explanation": "x", "flags": [],
                       "soft_signal_score": 0.0, "soft_signal_flags": [], "soft_signal_evidence": []})
        self.assertIsNone(junk.secondary_category)

    def test_calibrated_confidence_replaces_self_reported_prior(self):
        """Thresholds need real confidence; the calibration table supplies measured per-lane precision."""
        import json
        import os
        import tempfile
        from unittest.mock import patch as _patch

        from src.calibration import calibrated_confidence, load_calibration
        from src.classifier import _parse_classification

        table = {"schema": "spot.calibration.v1", "lanes": {"ollama:mock": {"Anti-Israel": 0.62, "Not Antisemitic": 0.88}}}
        with tempfile.TemporaryDirectory() as td:
            path = td + "/cal.json"
            with open(path, "w") as fh:
                json.dump(table, fh)
            with _patch.dict(os.environ, {"SPOT_CALIBRATION_PATH": path}):
                loaded = load_calibration()
                value, applied = calibrated_confidence("ollama:mock", "Anti-Israel", 0.9, loaded)
                self.assertEqual(value, 0.62)
                self.assertTrue(applied)
                value, applied = calibrated_confidence("ollama:mock", "Conspiracy Theories", 0.9, loaded)
                self.assertEqual(value, 0.9)
                self.assertFalse(applied)

                result = _parse_classification(
                    {"category": "Anti-Israel", "confidence": 0.9, "explanation": "x", "flags": [],
                     "soft_signal_score": 0.0, "soft_signal_flags": [], "soft_signal_evidence": []},
                    "Synthetic post.", SSOT, "ollama", "mock")
                self.assertEqual(result.confidence, 0.62)
                self.assertIn("CALIBRATED_CONFIDENCE", result.flags)

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
        import os
        import subprocess
        with patch.dict(os.environ, {'SPOT_MLX_CLI': '1'}), \
                patch('src.classifier.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{"category":"Not Antisemitic"}', 'diagnostic')) as run:
            self.assertEqual(_mlx_generate_json('mock', 'synthetic'), {'category': 'Not Antisemitic'})
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index('--verbose') + 1], 'false')

    def test_mlx_timeout_does_not_expose_prompt(self):
        import os
        import subprocess
        with patch.dict(os.environ, {'SPOT_MLX_CLI': '1'}), \
                patch('src.classifier.subprocess.run', side_effect=subprocess.TimeoutExpired(['command', 'private source text'], 1)):
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
        import os
        response = {'category':'Not Antisemitic','confidence':.99,'explanation':'Synthetic clear analysis','flags':[], 'soft_signal_score':0,'soft_signal_flags':[],'soft_signal_evidence':[]}
        with patch.dict(os.environ, {'SPOT_CALIBRATION_PATH': '/nonexistent/calibration.json'}), \
                patch('src.classifier._generate_json',return_value=response) as generate:
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
