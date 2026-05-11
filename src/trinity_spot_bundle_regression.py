from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.services.ops_db_service import upsert_run_rows
from backend.services.run_state_service import create_run_record
from src.trinity_spot_bundle import export_trinity_spot_training_bundles


class TrinitySpotBundleRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runs_dir = Path(self.temp_dir.name) / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_export_trinity_spot_bundle_writes_train_compatible_payload(self) -> None:
        run_id = "spot-run-1"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(run_path / "input.xlsx"),
            output_path=str(run_path / "output.xlsx"),
            upload_id=None,
            language="de",
            review_mode="partial",
        )
        upsert_run_rows(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=None,
            attempt_id=None,
            rows=[
                {
                    "row_index": 42,
                    "item_number": "42",
                    "post_text": "Example negative row",
                    "assigned_category": "Not Antisemitic",
                    "confidence_score": 0.76,
                    "explanation": "No antisemitic content detected.",
                    "flags": ["REVIEW_REQUIRED"],
                    "fallback_events": [],
                    "soft_signal_score": 0.02,
                    "soft_signal_flags": [],
                    "soft_signal_evidence": [],
                    "review_required": True,
                    "review_state": "reviewed",
                    "review_decision": "confirm",
                    "reviewer_note": "Reviewed and confirmed.",
                }
            ],
        )

        output_dir = self.runs_dir / "exports"
        summary = export_trinity_spot_training_bundles(
            runs_dir=self.runs_dir,
            run_id=run_id,
            company_id="company-1",
            output_dir=output_dir,
        )

        self.assertEqual(summary.exported_count, 1)
        bundle_path = Path(summary.files[0])
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))["bundle"]
        self.assertEqual(payload["bundle_type"], "spot-review-policy-learning")
        self.assertEqual(payload["contract_version"], "trinity.spot.v1alpha1")
        self.assertEqual(payload["spot_reasoning_request"]["company_id"], "company-1")
        self.assertEqual(payload["spot_reasoning_result"]["confidence_bundle"]["combined_confidence"], 0.76)
        self.assertEqual(payload["spot_review_outcome"]["disposition"], "CONFIRMED_NEGATIVE")
        self.assertEqual(payload["spot_review_outcome"]["final_label"], "Not Antisemitic")


if __name__ == "__main__":
    unittest.main()
