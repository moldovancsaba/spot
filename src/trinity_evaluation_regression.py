from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.classifier import _adjudicate_trinity
from src.failure_policy import enforce_result_safety
from src.models import ClassificationResult, InputRow
from src.ssot_loader import load_ssot

SSOT = load_ssot(Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")

CLEAR_ENV = {"SPOT_REVIEW_POLICY": "suspicious", "SPOT_AUDIT_SAMPLE_PCT": "0", "SPOT_AUDIT_UNANIMOUS_PCT": "0"}


def _result(category: str, version: str, confidence: float = 0.95) -> ClassificationResult:
    return ClassificationResult(
        row_index=1,
        raw_category=category,
        category=category,
        confidence=confidence,
        explanation=f"Synthetic {category} assessment.",
        flags=[],
        soft_signal_score=0.0,
        soft_signal_flags=[],
        soft_signal_evidence=[],
        resolved_model_version=version,
        drafted_text="Synthetic source post text.",
    )


class TrinityEvaluationRegressionTests(unittest.TestCase):
    def _row(self) -> InputRow:
        return InputRow(row_index=1, item_number="1", post_text="Synthetic source post text.")

    def test_unanimous_trinity_closes_without_review(self):
        """Deck p.4: three agreeing evaluators close the row."""
        primary = _result("Not Antisemitic", "mlx:model-a")
        with patch.dict(os.environ, CLEAR_ENV), \
                patch("src.classifier._classify_with_backend", side_effect=[
                    _result("Not Antisemitic", "ollama:qwen2.5:7b"),
                    _result("Not Antisemitic", "ollama:gemma2:9b"),
                ]), \
                patch("src.classifier.run_judge", return_value=(0.95, "PASS", [])):
            out = _adjudicate_trinity(self._row(), primary, SSOT, "trinity", model_name="mlx://model-a")

        self.assertIn("TRINITY_EVALUATED", out.flags)
        self.assertIn("TRINITY_UNANIMOUS", out.flags)
        self.assertNotIn("REVIEW_REQUIRED", out.flags)
        self.assertNotIn("TRINITY_DISAGREEMENT", out.flags)
        self.assertEqual(out.consensus_tier, "TRINITY_UNANIMOUS")
        self.assertEqual(out.audit_trace["trinity"]["lanes"], 3)
        self.assertTrue(out.audit_trace["trinity"]["unanimous"])

    def test_disagreement_followed_by_unanimous_revote_closes(self):
        """The justification round converts a split into agreement."""
        primary = _result("Not Antisemitic", "mlx:model-a")
        with patch.dict(os.environ, CLEAR_ENV), \
                patch("src.classifier._classify_with_backend", side_effect=[
                    _result("Anti-Israel", "ollama:qwen2.5:7b"),
                    _result("Anti-Israel", "ollama:gemma2:9b"),
                ]), \
                patch("src.classifier._classify_deliberation", side_effect=[
                    _result("Anti-Israel", "mlx:model-a"),
                    _result("Anti-Israel", "ollama:qwen2.5:7b"),
                    _result("Anti-Israel", "ollama:gemma2:9b"),
                ]), \
                patch("src.classifier.run_judge", return_value=(0.95, "PASS", [])):
            out = _adjudicate_trinity(self._row(), primary, SSOT, "trinity", model_name="mlx://model-a")

        self.assertIn("TRINITY_REVOTE_UNANIMOUS", out.flags)
        self.assertEqual(out.category, "Anti-Israel")
        self.assertNotIn("REVIEW_REQUIRED", out.flags)
        self.assertEqual([vote["category"] for vote in out.audit_trace["trinity"]["re_votes"]],
                         ["Anti-Israel", "Anti-Israel", "Anti-Israel"])

    def test_persistent_disagreement_requires_review(self):
        """Deck p.4: a split that survives the round goes to expert review."""
        primary = _result("Not Antisemitic", "mlx:model-a")
        with patch.dict(os.environ, CLEAR_ENV), \
                patch("src.classifier._classify_with_backend", side_effect=[
                    _result("Anti-Israel", "ollama:qwen2.5:7b"),
                    _result("Conspiracy Theories", "ollama:gemma2:9b"),
                ]), \
                patch("src.classifier._classify_deliberation", side_effect=[
                    _result("Not Antisemitic", "mlx:model-a"),
                    _result("Anti-Israel", "ollama:qwen2.5:7b"),
                    _result("Conspiracy Theories", "ollama:gemma2:9b"),
                ]), \
                patch("src.classifier.run_judge", return_value=(0.6, "REVIEW", [])):
            out = _adjudicate_trinity(self._row(), primary, SSOT, "trinity", model_name="mlx://model-a")

        self.assertIn("TRINITY_DISAGREEMENT", out.flags)
        self.assertIn("REVIEW_REQUIRED", out.flags)
        self.assertEqual(out.consensus_tier, "TRINITY_DISAGREEMENT")

    def test_unanimous_positive_closes_under_trinity_routing(self):
        """The deck reviews disagreements, not findings: a unanimous positive is a closed finding."""
        row = _result("Anti-Israel", "mlx:model-a")
        row.flags = ["TRINITY_EVALUATED", "TRINITY_UNANIMOUS"]
        row.audit_trace = {"source_sha256": "a" * 64}
        with patch.dict(os.environ, CLEAR_ENV):
            out = enforce_result_safety(row)
        self.assertNotIn("REVIEW_REQUIRED", out.flags)
        self.assertEqual(out.category, "Anti-Israel")

    def test_disagreement_reviews_regardless_of_env_policy(self):
        row = _result("Not Antisemitic", "mlx:model-a")
        row.flags = ["TRINITY_EVALUATED", "TRINITY_DISAGREEMENT"]
        row.audit_trace = {"source_sha256": "b" * 64}
        with patch.dict(os.environ, {"SPOT_REVIEW_POLICY": "suspicious", "SPOT_AUDIT_SAMPLE_PCT": "0"}):
            out = enforce_result_safety(row)
        self.assertIn("REVIEW_REQUIRED", out.flags)

    def test_unanimous_audit_stratum_sampled_independently(self):
        """Even unanimous proposals can be wrong (deck p.6): the stratum has its own sample rate."""
        row = _result("Not Antisemitic", "mlx:model-a")
        row.flags = ["TRINITY_EVALUATED", "TRINITY_UNANIMOUS"]
        row.audit_trace = {"source_sha256": "c" * 64}
        with patch.dict(os.environ, {"SPOT_REVIEW_POLICY": "suspicious", "SPOT_AUDIT_SAMPLE_PCT": "0",
                                     "SPOT_AUDIT_UNANIMOUS_PCT": "100"}):
            out = enforce_result_safety(row)
        self.assertIn("AUDIT_SAMPLE", out.flags)
        self.assertIn("AUDIT_STRATUM_UNANIMOUS", out.flags)
        self.assertIn("REVIEW_REQUIRED", out.flags)


if __name__ == "__main__":
    unittest.main()
