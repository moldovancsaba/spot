from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook

import backend.main as main_module
from backend.services import auth_service
from backend.services.run_state_service import create_run_record


def _build_workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Item number", "Post text", "Category"])
    ws.append(["1", "Synthetic contract test row", ""])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _prepare_synthetic_run(runs_dir: Path, run_id: str) -> Path:
    run_path = runs_dir / run_id
    if run_path.exists():
        shutil.rmtree(run_path)
    run_path.mkdir(parents=True, exist_ok=True)

    create_run_record(
        runs_dir=runs_dir,
        run_id=run_id,
        input_path="samples/sample_germany.xlsx",
        output_path=str(run_path / "output.xlsx"),
        upload_id=None,
        language="de",
        review_mode="partial",
        start_payload={"upload_id": "synthetic-upload", "language": "de", "review_mode": "partial", "limit": 1},
    )

    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "Item number",
            "Post text",
            "Category",
            "Assigned Category",
            "Fallback Events",
            "Confidence Score",
            "Explanation / Reasoning",
            "Flags",
            "Review Required",
        ]
    )
    ws.append(
        [
            "1",
            "Synthetic flagged row for contract regression.",
            "",
            "Anti-Israel",
            "CLASSIFIER_FALLBACK_FAILED",
            0.41,
            "Synthetic reasoning.",
            "LOW_CONFIDENCE",
            "YES",
        ]
    )
    wb.save(run_path / "output.xlsx")
    wb.close()

    (run_path / "progress.json").write_text(
        json.dumps({"run_id": run_id, "state": "COMPLETED", "progress_percentage": 100.0, "processed_rows": 1, "total_rows": 1}),
        encoding="utf-8",
    )
    (run_path / "control.json").write_text(
        json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
        encoding="utf-8",
    )
    (run_path / "artifact_manifest.json").write_text(json.dumps({"artifacts": ["output.xlsx"]}), encoding="utf-8")
    (run_path / "integrity_report.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    (run_path / "policy.json").write_text(json.dumps({"policy": "synthetic"}), encoding="utf-8")
    (run_path / "logs.txt").write_text("synthetic contract log\n", encoding="utf-8")
    return run_path


class BackendContractRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.runs_dir = Path(self.tempdir.name) / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.previous_runs_dir = main_module.RUNS_DIR
        self.previous_production_mode = main_module.DEFAULT_PRODUCTION_MODE
        main_module.RUNS_DIR = self.runs_dir
        auth_service._SESSIONS.clear()
        self.client = TestClient(main_module.app)

    def tearDown(self) -> None:
        main_module.RUNS_DIR = self.previous_runs_dir
        main_module.DEFAULT_PRODUCTION_MODE = self.previous_production_mode
        auth_service._SESSIONS.clear()
        self.tempdir.cleanup()

    def _login_admin(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"actor_name": "contract-test", "role": "admin", "access_code": "spot-local"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_read_endpoints_require_authentication(self) -> None:
        self.assertEqual(self.client.get("/runs").status_code, 401)
        self.assertEqual(self.client.get("/uploads").status_code, 401)
        self.assertEqual(self.client.get("/classify/status/example-run").status_code, 401)

    def test_review_update_rejects_nonexistent_row(self) -> None:
        self._login_admin()
        run_id = f"contract-run-{uuid.uuid4().hex[:8]}"
        _prepare_synthetic_run(self.runs_dir, run_id)
        response = self.client.post(
            f"/runs/{run_id}/review-rows/999",
            json={"review_state": "reviewed", "review_decision": "confirm", "reviewer_note": "should fail"},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_signoff_requires_review_completion(self) -> None:
        self._login_admin()
        run_id = f"contract-run-{uuid.uuid4().hex[:8]}"
        _prepare_synthetic_run(self.runs_dir, run_id)
        blocked = self.client.post(
            f"/runs/{run_id}/signoff",
            json={"decision": "accepted_with_conditions", "note": "blocked until review is complete"},
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)

        reviewed = self.client.post(
            f"/runs/{run_id}/review-rows/2",
            json={"review_state": "reviewed", "review_decision": "confirm", "reviewer_note": "done"},
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.text)

        allowed = self.client.post(
            f"/runs/{run_id}/signoff",
            json={"decision": "accepted_with_conditions", "note": "all review rows complete"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_archive_existing_run_state_preserves_old_attempt(self) -> None:
        run_id = "archive-check"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        marker = run_path / "marker.txt"
        marker.write_text("keep me", encoding="utf-8")

        main_module._archive_existing_run_state(run_id)

        self.assertFalse(run_path.exists())
        history_root = self.runs_dir / "_history"
        archived = list(history_root.glob(f"{run_id}-*"))
        self.assertEqual(len(archived), 1)
        self.assertEqual((archived[0] / "marker.txt").read_text(encoding="utf-8"), "keep me")

    def test_production_payload_restrictions_block_arbitrary_paths(self) -> None:
        main_module.DEFAULT_PRODUCTION_MODE = True

        main_module._assert_allowed_classify_payload({"upload_id": "upload-1", "language": "de", "review_mode": "partial", "limit": 1})

        with self.assertRaises(HTTPException):
            main_module._assert_allowed_classify_payload({"input": "/tmp/file.xlsx"})

        with self.assertRaises(HTTPException):
            main_module._assert_allowed_classify_payload({"output": "/tmp/out.xlsx"})


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BackendContractRegressionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
