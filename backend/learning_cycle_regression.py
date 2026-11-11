from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main
from backend.services import auth_service
from backend.services.learning_cycle_service import (
    drift_measurement,
    feedback_summary,
    list_cycles,
    run_learning_cycle,
)
from backend.services.ops_db_service import upsert_run_rows
from backend.services.run_state_service import create_run_record


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class LearningCycleRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runs = Path(self.temp.name)
        self.previous = main.RUNS_DIR
        main.RUNS_DIR = self.runs
        auth_service._SESSIONS.clear()
        self.client = TestClient(main.app)
        create_run_record(
            runs_dir=self.runs,
            run_id="learn-run",
            input_path="input.xlsx",
            output_path="output.xlsx",
            upload_id=None,
            language="de",
            review_mode="partial",
        )

    def tearDown(self):
        main.RUNS_DIR = self.previous
        auth_service._SESSIONS.clear()
        self.temp.cleanup()

    def _reference(self) -> Path:
        path = self.runs / "reference.jsonl"
        rows = [
            {"sample_id": "S1", "text_sha256": _sha("Text alpha."), "label": "Anti-Israel"},
            {"sample_id": "S2", "text_sha256": _sha("Text beta."), "label": "Not Antisemitic"},
        ]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        return path

    def _row(self, index, text, category, **overrides):
        row = {
            "row_index": index,
            "item_number": str(index),
            "post_text": text,
            "assigned_category": category,
            "confidence_score": 0.9,
            "flags": [],
            "fallback_events": [],
            "review_required": True,
        }
        row.update(overrides)
        return row

    def test_drift_measurement_scores_only_reference_overlap(self):
        rows = [self._row(2, "Text alpha.", "Anti-Israel"), self._row(3, "Unrelated text.", "Anti-Judaism")]
        reference = {_sha("Text alpha."): "Anti-Israel"}
        result = drift_measurement(rows=rows, reference=reference)
        self.assertEqual(result["rows_scored"], 1)
        self.assertEqual(result["agreement_pct"], 100.0)
        self.assertEqual(result["macro_f1"], 1.0)

    def test_feedback_summary_excludes_failed_rows_from_training_evidence(self):
        rows = [
            self._row(2, "a", "Anti-Israel", review_state="reviewed", review_decision="confirm"),
            self._row(3, "b", "Anti-Israel", review_state="reviewed", review_decision="adjust"),
            self._row(4, "c", "Not Antisemitic", review_state="reviewed", review_decision="confirm",
                      flags=["ANALYSIS_FAILED"]),
            self._row(5, "d", "Not Antisemitic"),
        ]
        summary = feedback_summary(run_id="learn-run", rows=rows)
        self.assertEqual(summary["decisions"]["confirm"], 2)
        self.assertEqual(summary["decisions"]["adjust"], 1)
        self.assertEqual(summary["decisions"]["unreviewed"], 1)
        self.assertEqual(summary["training_eligible_row_indices"], [2, 3])

    def test_cycle_records_drift_bundles_and_registry_without_mutating_state(self):
        upsert_run_rows(
            runs_dir=self.runs,
            run_id="learn-run",
            upload_id=None,
            rows=[
                self._row(2, "Text alpha.", "Anti-Israel", review_state="reviewed", review_decision="confirm"),
                self._row(3, "Text beta.", "Not Antisemitic", review_state="reviewed", review_decision="confirm"),
            ],
        )
        record = run_learning_cycle(
            runs_dir=self.runs,
            run_id="learn-run",
            reference_path=self._reference(),
            export_bundles=False,
        )
        self.assertEqual(record["drift"]["rows_scored"], 2)
        self.assertEqual(record["drift"]["agreement_pct"], 100.0)
        self.assertEqual(record["feedback"]["training_eligible_rows"], 2)
        self.assertFalse(record["policy"]["retrains"])
        self.assertFalse(record["policy"]["changes_contract"])
        learning = self.runs / "learn-run" / "learning"
        self.assertTrue((learning / "latest_cycle.json").is_file())
        registry = (learning / "registry.jsonl").read_text().strip().splitlines()
        self.assertEqual(len(registry), 1)
        self.assertEqual(len(list_cycles(runs_dir=self.runs, run_id="learn-run")), 1)

    def test_cycle_survives_a_bundle_export_failure(self):
        upsert_run_rows(
            runs_dir=self.runs,
            run_id="learn-run",
            upload_id=None,
            rows=[self._row(2, "Text alpha.", "Anti-Israel", review_state="reviewed", review_decision="confirm")],
        )
        record = run_learning_cycle(
            runs_dir=self.runs,
            run_id="learn-run",
            reference_path=self._reference(),
            export_bundles=True,
            company_id="",  # invalid on purpose: the cycle must still record evidence
        )
        self.assertIn("bundles", record)
        self.assertIsNotNone(record["policy"])

    def test_learning_endpoints_require_authentication(self):
        self.assertEqual(self.client.get("/learning/cycles/learn-run").status_code, 401)
        self.assertEqual(self.client.post("/learning/cycle/learn-run").status_code, 401)


if __name__ == "__main__":
    unittest.main()
