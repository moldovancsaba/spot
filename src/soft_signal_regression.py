from __future__ import annotations

import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.classifier import _apply_review_mode, _heuristic_soft_signals
from src.models import ClassificationResult
from src.ssot_loader import load_ssot


SSOT = load_ssot(PROJECT_ROOT / "ssot" / "ssot.json")


class SoftSignalRegressionTests(unittest.TestCase):
    def test_dual_loyalty_signal_is_detected(self) -> None:
        flags, evidence = _heuristic_soft_signals(
            "He is clearly more loyal to Israel than to our country.",
            SSOT,
        )
        self.assertIn("SOFT_SIGNAL_DUAL_LOYALTY", flags)
        self.assertTrue(evidence)

    def test_partial_review_mode_escalates_soft_signal_rows(self) -> None:
        result = ClassificationResult(
            row_index=2,
            raw_category="Anti-Israel",
            category="Anti-Israel",
            confidence=0.91,
            explanation="Borderline example with coded implication.",
            flags=[],
            soft_signal_score=0.6,
            soft_signal_flags=["SOFT_SIGNAL_CODED_CONSPIRACY"],
            soft_signal_evidence=["jewish lobby"],
        )
        applied = _apply_review_mode(result, SSOT, "partial")
        self.assertIn("SOFT_SIGNAL_REVIEW", applied.flags)
        self.assertIn("REVIEW_REQUIRED", applied.flags)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SoftSignalRegressionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
