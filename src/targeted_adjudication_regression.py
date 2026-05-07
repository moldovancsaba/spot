from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import _adjudicate_targeted_row
from src.models import ClassificationResult, InputRow
from src.ssot_loader import load_ssot


SSOT = load_ssot(PROJECT_ROOT / "ssot" / "ssot.json")


class TargetedAdjudicationRegressionTests(unittest.TestCase):
    def test_second_pass_confirms_same_category_and_sets_judge(self) -> None:
        row = InputRow(row_index=2, item_number="1", post_text="Example borderline content")
        initial = ClassificationResult(
            row_index=2,
            raw_category="Anti-Israel",
            category="Anti-Israel",
            confidence=0.58,
            explanation="Initial low-confidence classification.",
            flags=["LOW_CONFIDENCE", "REVIEW_REQUIRED"],
            soft_signal_score=0.0,
            soft_signal_flags=[],
            soft_signal_evidence=[],
            resolved_model_version="mlx://primary",
            drafted_text="Example borderline content",
            fallback_events=[],
        )
        alternate = ClassificationResult(
            row_index=-1,
            raw_category="Anti-Israel",
            category="Anti-Israel",
            confidence=0.81,
            explanation="Alternate route confirmed the same category.",
            flags=[],
            soft_signal_score=0.0,
            soft_signal_flags=[],
            soft_signal_evidence=[],
            resolved_model_version="ollama://fallback",
            fallback_events=[],
        )
        with (
            patch("src.classifier._classify_with_backend", return_value=alternate),
            patch("src.classifier.run_judge", return_value=(0.82, "PASS", [])),
        ):
            adjudicated = _adjudicate_targeted_row(row, initial, SSOT, "partial")
        self.assertEqual(adjudicated.category, "Anti-Israel")
        self.assertEqual(adjudicated.judge_verdict, "PASS")
        self.assertGreaterEqual(adjudicated.confidence, 0.81)
        self.assertIn("SECOND_PASS_CONFIRMED", adjudicated.flags)

    def test_second_pass_can_override_category_when_judge_favors_alternate(self) -> None:
        row = InputRow(row_index=2, item_number="1", post_text="Problematic coded conspiracy content")
        initial = ClassificationResult(
            row_index=2,
            raw_category="Not Antisemitic",
            category="Not Antisemitic",
            confidence=0.52,
            explanation="Initial uncertain classification.",
            flags=["LOW_CONFIDENCE", "REVIEW_REQUIRED"],
            soft_signal_score=0.6,
            soft_signal_flags=["SOFT_SIGNAL_CODED_CONSPIRACY"],
            soft_signal_evidence=["coded conspiracy"],
            resolved_model_version="mlx://primary",
            drafted_text="Problematic coded conspiracy content",
            fallback_events=[],
        )
        alternate = ClassificationResult(
            row_index=-1,
            raw_category="Conspiracy Theories",
            category="Conspiracy Theories",
            confidence=0.77,
            explanation="Alternate route found conspiracy framing.",
            flags=[],
            soft_signal_score=0.6,
            soft_signal_flags=["SOFT_SIGNAL_CODED_CONSPIRACY"],
            soft_signal_evidence=["coded conspiracy"],
            resolved_model_version="ollama://fallback",
            fallback_events=[],
        )
        judge_results = [
            (0.34, "FAIL", []),
            (0.88, "PASS", []),
        ]
        with (
            patch("src.classifier._classify_with_backend", return_value=alternate),
            patch("src.classifier.run_judge", side_effect=judge_results),
        ):
            adjudicated = _adjudicate_targeted_row(row, initial, SSOT, "partial")
        self.assertEqual(adjudicated.category, "Conspiracy Theories")
        self.assertEqual(adjudicated.judge_verdict, "PASS")
        self.assertIn("SECOND_PASS_DISAGREEMENT", adjudicated.flags)
        self.assertIn("SECOND_PASS_CATEGORY_OVERRIDDEN", adjudicated.flags)
        self.assertIn("REVIEW_REQUIRED", adjudicated.flags)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TargetedAdjudicationRegressionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
