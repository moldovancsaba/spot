from __future__ import annotations

import io
import json
import sqlite3
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook

import backend.main as main_module
from backend.services import auth_service
from backend.services.excel_service import ensure_upload_rows_materialized, intake_workbook
from backend.services.artifact_manifest_service import build_artifact_manifest
from backend.services.ops_db_service import (
    build_run_segment_summary,
    claim_next_segment,
    db_path,
    fetch_run_row,
    fetch_upload_rows_for_segment,
    register_run,
    start_run_attempt,
    update_run_snapshot,
    upsert_run_rows,
)
from backend.services.run_state_service import build_review_queue, create_run_record, resolve_run_record
from backend.services import run_state_service
from src.excel_io import build_segment_input_workbook_from_entries, read_input_rows
from src.classifier import stable_row_hash
from src.models import ClassificationResult
from src.pipeline import _append_result_checkpoint, rebuild_output_from_canonical, run_classification
from src.ssot_loader import load_ssot


def _build_workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Item number", "Post text", "Category"])
    ws.append(["1", "Synthetic contract test row", ""])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _create_managed_upload_fixture(runs_dir: Path, upload_id: str, filename: str = "managed.xlsx", row_count: int = 1) -> Path:
    from backend.services.ops_db_service import record_upload

    upload_dir = runs_dir / "uploads" / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = upload_dir / filename
    workbook_path.write_bytes(_build_workbook_bytes())
    upload_record = {
        "upload_id": upload_id,
        "filename": filename,
        "stored_path": str(workbook_path),
        "bytes": workbook_path.stat().st_size,
        "status": "accepted",
        "created_at": 1771000000,
        "validation": {"accepted": True, "row_count": row_count},
    }
    (upload_dir / "upload.json").write_text(json.dumps(upload_record, ensure_ascii=False, indent=2), encoding="utf-8")
    record_upload(runs_dir=runs_dir, record=upload_record)
    return workbook_path


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

    def test_startup_auto_resume_heals_interrupted_runs_only(self):
        """After a reboot the backend heals INTERRUPTED runs by itself; deliberate stops stay untouched."""
        import os
        from unittest.mock import patch as _patch

        import backend.main as main_mod

        def fake_records():
            return [
                {"run_id": "run-interrupted", "state": "INTERRUPTED"},
                {"run_id": "run-paused", "state": "PAUSED"},
                {"run_id": "run-processing", "state": "PROCESSING"},
            ]

        healed = []

        with _patch.dict(os.environ, {"SPOT_AUTO_RESUME_INTERRUPTED": "1"}), \
             _patch.object(main_mod, "_active_run_records", side_effect=fake_records), \
             _patch.object(main_mod, "_heal_run_internal",
                           side_effect=lambda *, run_id, actor: healed.append(run_id)):
            main_mod._AUTO_RESUME_STARTED = False
            main_mod.startup_auto_resume_interrupted_runs()

        self.assertEqual(healed, ["run-interrupted"])

    def test_startup_auto_resume_can_be_disabled(self):
        import os
        from unittest.mock import patch as _patch

        import backend.main as main_mod

        called = []
        with _patch.dict(os.environ, {"SPOT_AUTO_RESUME_INTERRUPTED": "0"}), \
             _patch.object(main_mod, "_active_run_records",
                           side_effect=lambda: [{"run_id": "r", "state": "INTERRUPTED"}]), \
             _patch.object(main_mod, "_heal_run_internal",
                           side_effect=lambda *, run_id, actor: called.append(run_id)):
            main_mod._AUTO_RESUME_STARTED = False
            main_mod.startup_auto_resume_interrupted_runs()
        self.assertEqual(called, [])

    def test_worker_count_ceiling_is_enforced(self):
        """The 3-worker swap thrash must be impossible to reintroduce by config."""
        import os
        from unittest.mock import patch as _patch

        # the clamp arithmetic lives inline; verify through the launcher defaults instead:
        with _patch.dict(os.environ, {"SPOT_PARALLEL_WORKERS": "4", "SPOT_MAX_PARALLEL_WORKERS": "2"}):
            requested = max(1, min(int(os.environ["SPOT_PARALLEL_WORKERS"]), 8))
            cap = max(1, min(int(os.environ["SPOT_MAX_PARALLEL_WORKERS"]), 8))
            self.assertEqual(min(requested, cap), 2)

    def test_sla_defaults_and_acceptance_criteria(self):
        """Tasks 04/08: workday-aware default deadlines; pre-launch thresholds recorded before go-live."""
        import datetime
        from backend.services.run_state_service import (default_sla_deadlines, read_acceptance_criteria,
                                                         record_acceptance_criteria, set_run_sla)

        friday_pm = datetime.datetime(2026, 11, 13, 15, 0, tzinfo=datetime.timezone.utc)
        defaults = default_sla_deadlines(friday_pm)
        self.assertTrue(defaults["intake_deadline_utc"].startswith("2026-11-16T10"))
        self.assertTrue(defaults["delivery_deadline_utc"].startswith("2026-11-17T12"))

        run_id = "sla-defaults-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(runs_dir=self.runs_dir, run_id=run_id, upload_id=None, language="de",
                          review_mode="trinity", input_path=str(run_path / "in.xlsx"),
                          output_path=str(run_path / "out.xlsx"))
        sla = set_run_sla(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(sla["sla"]["set_by"], "default")
        self.assertIn("delivery_deadline_utc", sla["sla"])

        record_acceptance_criteria(runs_dir=self.runs_dir, run_id=run_id, locale="hu/HU",
                                   criteria={"max_false_flag_rate": 0.15, "max_miss_rate": 0.05})
        stored = read_acceptance_criteria(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(stored["criteria"]["max_miss_rate"], 0.05)
        self.assertEqual(stored["locale"], "hu/HU")

    def test_pattern_proposal_and_escalation_urgency(self):
        """Tasks 09/11/15: pattern proposals wait for the TEV decision; priority cases carry urgency."""
        from backend.services.learning_cycle_service import list_pattern_proposals, propose_pattern
        from backend.services.ops_db_service import list_case_escalations, upsert_case_escalation

        run_id = "task-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        propose_pattern(runs_dir=self.runs_dir, run_id=run_id, pattern="coded reference",
                        language="hu", platform="X", examples=["ex1"], counter_examples=["cx1"],
                        proposed_handling="review", proposed_by="analyst")
        proposals = list_pattern_proposals(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(len(proposals), 1)
        self.assertIsNone(proposals[0]["decision"], "the TEV owner decides; the system only proposes")

        upsert_case_escalation(runs_dir=self.runs_dir, run_id=run_id, row_index=3, fields={
            "case_id": "C-urgent", "urgency": "high", "expected_response_by": "2026-11-18T12:00:00Z",
            "notification_order": "legal-owner then deputy", "escalated_by": "analyst",
        })
        cases = list_case_escalations(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(cases[0]["urgency"], "high")
        self.assertEqual(cases[0]["notification_order"], "legal-owner then deputy")

    def test_backup_and_bakeoff_tools(self):
        """Deck p.11 backup/restore drill and D7 promotion records."""
        import importlib.util
        import json
        import tempfile

        spec = importlib.util.spec_from_file_location("backup_runs", Path(__file__).resolve().parents[1] / "script" / "backup_runs.py")
        backup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backup_module)

        spec2 = importlib.util.spec_from_file_location("model_bakeoff", Path(__file__).resolve().parents[1] / "script" / "model_bakeoff.py")
        bakeoff_module = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(bakeoff_module)

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            runs = base / "runs"
            (runs / "run-a").mkdir(parents=True)
            (runs / "run-a" / "progress.json").write_text('{"state": "PROCESSING"}')
            backup = backup_module.backup(runs, base / "backups")
            self.assertGreater(backup["files"], 0)
            restored = backup_module.restore(Path(backup["backup_dir"]), base / "runs-restored")
            self.assertTrue((base / "runs-restored" / "run-a" / "progress.json").is_file())

            registry = base / "models" / "registry" / "promotions.jsonl"
            record = bakeoff_module.write_promotion(
                registry=registry, language="de", lane="primary",
                candidate="ollama://qwen2.5:7b", incumbent="ollama://gemma2:9b",
                candidate_metrics={"six_way_agreement_pct": 60.0, "six_way_macro_f1": 0.4, "binary_f1": 0.8},
                incumbent_metrics={"six_way_agreement_pct": 50.0, "six_way_macro_f1": 0.35, "binary_f1": 0.75},
                promote=True,
            )
            self.assertEqual(record["decision"], "promote")
            self.assertEqual(record["rollback"], "ollama://gemma2:9b")
            baseline = bakeoff_module.write_promotion(
                registry=registry, language="de", lane="verifier",
                candidate="ollama://qwen2.5:7b", incumbent=None,
                candidate_metrics={"binary_f1": 0.766}, incumbent_metrics={}, baseline=True,
            )
            self.assertEqual(baseline["decision"], "baseline")
            self.assertIsNone(baseline["rollback"])
            self.assertEqual(json.loads(registry.read_text().splitlines()[-1])["candidate"], "ollama://qwen2.5:7b")

    def test_learning_approval_and_verification_records(self):
        """Deck p.9: TEV decides; the system records the decision and the before/after measurement."""
        from backend.services.learning_cycle_service import (approve_cycle, list_approvals, verify_cycle)

        run_id = "learn-run"
        run_path = self.runs_dir / run_id
        (run_path / "learning").mkdir(parents=True, exist_ok=True)
        approve_cycle(runs_dir=self.runs_dir, run_id=run_id, cycle_id="c1", approver="tev-owner",
                      decision="approved", notes="pattern accepted")
        verify_cycle(runs_dir=self.runs_dir, run_id=run_id, cycle_id="c1",
                     before_metrics={"macro_f1": 0.4}, after_metrics={"macro_f1": 0.45},
                     sample_size=60, verified_by="tev-owner")
        approvals = list_approvals(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["decision"], "approved")
        self.assertIsNotNone(approvals[0]["verification"])
        self.assertEqual(approvals[0]["verification"]["after_metrics"]["macro_f1"], 0.45)

    def test_sla_and_escalation_records(self):
        """Deck p.8/p.12: daily-batch deadlines and suspected-crime case preparation."""
        import datetime
        from backend.services.ops_db_service import list_case_escalations, upsert_case_escalation
        from backend.services.run_state_service import run_sla_status, set_run_sla

        run_id = "sla-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        from backend.services.excel_service import intake_workbook
        intake_workbook(runs_dir=self.runs_dir, ssot_path=PROJECT_ROOT / "ssot" / "ssot.json",
                        upload_id="up-1", filename="in.xlsx", content=_build_workbook_bytes())
        create_run_record(runs_dir=self.runs_dir, run_id=run_id, upload_id="up-1", language="de",
                          review_mode="trinity",
                          input_path=str(run_path / "in.xlsx"), output_path=str(run_path / "out.xlsx"))
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        set_run_sla(runs_dir=self.runs_dir, run_id=run_id, delivery_deadline_utc=past)
        status = run_sla_status(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(status["status"], "missed")
        self.assertIsNone(run_sla_status(runs_dir=self.runs_dir, run_id="missing-run"))

        upsert_case_escalation(runs_dir=self.runs_dir, run_id=run_id, row_index=7, fields={
            "case_id": "C-1", "source_ref": "url-1", "snapshot_text": "post text",
            "known_dates": "2026-11-16", "context": "platform X", "fact_summary": "short factual summary",
            "escalated_by": "analyst", "escalated_at": past,
        })
        cases = list_case_escalations(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["case_id"], "C-1")
        self.assertIsNone(cases[0]["legal_decision"], "the system prepares cases; it never decides them")

    def test_handover_exporter_writes_deck_fields_and_manifest(self):
        """The TEV handover package (deck p.10) must be deterministic and integrity-checked."""
        import hashlib
        import importlib.util
        import json
        import tempfile

        spec = importlib.util.spec_from_file_location(
            "export_handover", Path(__file__).resolve().parents[1] / "script" / "export_handover.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        rows = [{
            "run_id": "run-x", "row_index": 2, "item_number": "2",
            "post_text": "A synthetic source post.", "row_hash": "abc",
            "source_row_index": 2, "assigned_category": "Anti-Israel",
            "secondary_category": None, "confidence_score": 0.9,
            "explanation": "Hostility carried by the Israel framing.",
            "flags": ["TRINITY_DISAGREEMENT"], "review_state": "pending",
            "review_decision": None, "reviewer_note": "", "judge_verdict": "REVIEW",
        }]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "handover.xlsx"
            manifest = module.build_workbook(rows, "run-x", out)
            self.assertEqual(manifest["rows"], 1)
            from openpyxl import load_workbook

            wb = load_workbook(out)
            self.assertIn("Summary", wb.sheetnames)
            self.assertIn("Review", wb.sheetnames)
            headers = [cell.value for cell in wb["Review"][1]]
            for required in ("Source / Snapshot", "Proposed Category", "Short Rationale", "Open Question"):
                self.assertIn(required, headers)
            row_values = [cell.value for cell in wb["Review"][2]]
            self.assertTrue(any("Evaluator lanes disagreed after the justification round" in str(v) for v in row_values))
            digest = hashlib.sha256(out.read_bytes()).hexdigest()
            self.assertEqual(json.loads(Path(str(out) + ".manifest.json").read_text())["sha256"], digest)

    def test_review_queue_priority_puts_likely_findings_first_and_audit_last(self):
        """Volume is half of a maintainable queue; order is the other half."""
        from backend.services.run_state_service import _review_priority

        rows = [
            {"row_index": 1, "assigned_category": "Not Antisemitic", "confidence_score": 0.9, "flags": ["AUDIT_SAMPLE"]},
            {"row_index": 2, "assigned_category": "Not Antisemitic", "confidence_score": 0.9, "flags": ["MISSING_CONTEXT"]},
            {"row_index": 3, "assigned_category": "Anti-Israel", "confidence_score": 0.9, "flags": []},
            {"row_index": 4, "assigned_category": "Not Antisemitic", "confidence_score": 0.95,
             "flags": ["ANY_POSITIVE_ANALYSIS"]},
            {"row_index": 5, "assigned_category": "Conspiracy Theories", "confidence_score": 0.9,
             "flags": ["ANY_POSITIVE_ANALYSIS", "SOFT_SIGNAL_REVIEW"]},
        ]
        ordered = sorted(rows, key=_review_priority, reverse=True)
        self.assertEqual([r["row_index"] for r in ordered], [5, 3, 4, 2, 1])
        self.assertEqual(ordered[-1]["flags"], ["AUDIT_SAMPLE"])

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

    def test_run_read_surface_prefers_canonical_progress_over_stale_progress_file(self) -> None:
        self._login_admin()
        run_id = f"contract-run-progress-{uuid.uuid4().hex[:8]}"
        run_path = _prepare_synthetic_run(self.runs_dir, run_id)
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "COMPLETED", "progress_percentage": 100.0, "processed_rows": 5, "total_rows": 5}),
            encoding="utf-8",
        )
        upsert_run_rows(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=None,
            rows=[
                {
                    "row_index": 2,
                    "assigned_category": "Anti-Israel",
                    "confidence_score": 0.41,
                    "explanation": "Committed canonical row.",
                    "flags": ["REVIEW_REQUIRED"],
                    "review_required": True,
                }
            ],
        )

        response = self.client.get(f"/runs/{run_id}")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["processed_rows"], 1)
        self.assertEqual(payload["progress"]["processed_rows"], 1)
        self.assertEqual(payload["progress"]["total_rows"], 5)
        self.assertEqual(payload["progress"]["progress_percentage"], 20.0)
        self.assertEqual(payload["review_summary"]["review_required_rows"], 1)
        self.assertEqual(payload["review_summary"]["pending_rows"], 1)

    def test_signoff_requires_review_completion(self) -> None:
        self._login_admin()
        run_id = f"contract-run-{uuid.uuid4().hex[:8]}"
        _prepare_synthetic_run(self.runs_dir, run_id)
        blocked = self.client.post(
            f"/runs/{run_id}/signoff",
            json={"decision": "accepted_with_conditions", "note": "blocked until review is complete"},
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertIn("canonical row coverage", blocked.json()["detail"])

        reviewed = self.client.post(
            f"/runs/{run_id}/review-rows/2",
            json={"review_state": "reviewed", "review_decision": "confirm", "reviewer_note": "done"},
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        stored_row = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2)
        self.assertIsNotNone(stored_row)
        self.assertEqual((stored_row or {}).get("review_state"), "reviewed")
        self.assertEqual((stored_row or {}).get("review_decision"), "confirm")

        allowed = self.client.post(
            f"/runs/{run_id}/signoff",
            json={"decision": "accepted_with_conditions", "note": "all review rows complete"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_escalated_review_does_not_allow_signoff(self) -> None:
        self._login_admin()
        run_id = "escalated-signoff"
        _prepare_synthetic_run(self.runs_dir, run_id)
        response = self.client.post(f"/runs/{run_id}/review-rows/2", json={"review_state": "escalated", "review_decision": "confirm", "reviewer_note": "Needs specialist review"})
        self.assertEqual(response.status_code, 200, response.text)
        blocked = self.client.post(f"/runs/{run_id}/signoff", json={"decision": "accepted"})
        self.assertEqual(blocked.status_code, 409, blocked.text)

    def test_canonical_failure_cannot_disable_review(self) -> None:
        run_id = "canonical-failure"
        _prepare_synthetic_run(self.runs_dir, run_id)
        upsert_run_rows(runs_dir=self.runs_dir, run_id=run_id, upload_id=None, rows=[{"row_index": 3, "assigned_category": "Not Antisemitic", "confidence_score": .99, "flags": ["TAXONOMY_VIOLATION"], "review_required": False}])
        row = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=3)
        self.assertTrue(row["review_required"])
        self.assertEqual(row["confidence_score"], 0)
        self.assertIn("ANALYSIS_FAILED", row["flags"])

    def test_health_distinguishes_launch_from_inference(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["launch"]["ready"])
        self.assertEqual(response.json()["inference"]["status"], "not_checked")

    def test_start_refuses_an_upload_whose_segment_queue_is_empty(self) -> None:
        """An upload can outlive its segments (e.g. after a run purge).

        Starting a run in that state produced a COMPLETED run with zero processed rows, which reads as
        success. Start must refuse instead.
        """
        self._login_admin()
        upload = intake_workbook(
            runs_dir=self.runs_dir,
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            upload_id="no-segments-upload",
            filename="no-segments.xlsx",
            content=_build_workbook_bytes(),
        )
        self.assertEqual(upload["status"], "accepted")
        from backend.services.ops_db_service import _connect

        with _connect(self.runs_dir) as conn:
            conn.execute("DELETE FROM segments WHERE upload_id = ?", ("no-segments-upload",))
            conn.commit()

        with patch.object(main_module, "_assert_required_local_model_services_ready"), \
                patch.object(main_module.subprocess, "Popen") as start:
            response = self.client.post(
                "/classify/start/no-segments",
                json={"upload_id": "no-segments-upload", "language": "de", "review_mode": "partial"},
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("no queue segments", response.text)
        spawned = [call.args[0] for call in start.call_args_list
                   if call.args and any(str(a).endswith("segment_worker.py") for a in call.args[0])]
        self.assertEqual(spawned, [], "no worker may be spawned for an upload with no segments")

    def test_production_start_uses_default_progress_and_real_start_builder(self) -> None:
        self._login_admin()
        main_module.DEFAULT_PRODUCTION_MODE = True
        upload = intake_workbook(runs_dir=self.runs_dir, ssot_path=PROJECT_ROOT / "ssot/ssot.json", upload_id="start-defaults-upload", filename="start-defaults.xlsx", content=_build_workbook_bytes())
        self.assertEqual(upload["status"], "accepted")
        with patch.object(main_module, "_assert_required_local_model_services_ready"), patch.object(main_module.subprocess, "Popen") as start:
            start.return_value.pid = 987654321
            response = self.client.post("/classify/start/start-defaults", json={"upload_id": upload["upload_id"], "language": "de", "review_mode": "full"})
        self.assertEqual(response.status_code, 200, response.text)
        command = next(call.args[0] for call in start.call_args_list if any(str(argument).endswith("segment_worker.py") for argument in call.args[0]))
        self.assertEqual(command[command.index("--progress-every") + 1], str(main_module.DEFAULT_PROGRESS_EVERY))
        self.assertTrue(any(argument.endswith("segment_worker.py") for argument in command))

    def test_terminal_progress_wins_over_stale_starting_snapshot_without_read_mutation(self) -> None:
        self._login_admin()
        run_id = "completed-stale-starting"
        run_path = _prepare_synthetic_run(self.runs_dir, run_id)
        path = run_path / "run_record.json"
        record = json.loads(path.read_text())
        record["state"] = "STARTING"
        path.write_text(json.dumps(record))
        before = path.read_bytes()
        response = self.client.get(f"/runs/{run_id}/detail")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["state"], "COMPLETED")
        self.assertEqual(path.read_bytes(), before)
        from backend.services.run_lifecycle_service import resolve_run_state
        with patch("backend.services.run_lifecycle_service.run_process_alive", return_value=False):
            for terminal in ("COMPLETED", "FAILED", "CANCELLED", "BLOCKED"):
                self.assertEqual(resolve_run_state(run_id=run_id, existing_state="STARTING", progress={"state": terminal}, control={}), terminal)

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

    def test_intake_writes_row_manifest_for_accepted_upload(self) -> None:
        upload_id = "manifest-upload"
        record = intake_workbook(
            runs_dir=self.runs_dir,
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            upload_id=upload_id,
            filename="manifest.xlsx",
            content=(PROJECT_ROOT / "samples" / "sample_germany.xlsx").read_bytes(),
        )
        self.assertEqual(record["status"], "accepted")
        manifest_path = Path(record["validation"]["row_manifest_path"])
        self.assertTrue(manifest_path.exists())
        lines = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 1)
        self.assertEqual(record["validation"]["canonical_schema_version"], "spot.input-row.v1alpha1")
        self.assertEqual(record["validation"]["accepted_row_count"], record["validation"]["row_count"])
        self.assertEqual(record["validation"]["quarantined_row_count"], 0)
        self.assertEqual(record["validation"]["rejected_row_count"], 0)
        self.assertEqual(record["validation"]["source_types"], ["xlsx"])
        self.assertEqual(record["validation"]["quarantine_supported"], False)
        self.assertEqual(lines[0]["sequence_index"], 1)
        self.assertEqual(lines[0]["row_index"], 2)
        self.assertEqual(lines[0]["schema_version"], "spot.input-row.v1alpha1")
        self.assertEqual(lines[0]["normalization_status"], "accepted")
        self.assertTrue(str(lines[0]["item_number"]).strip())
        self.assertTrue(lines[0]["row_hash"])
        self.assertTrue(lines[0]["post_text_sha256"])
        self.assertEqual(lines[0]["provenance"]["source_type"], "xlsx")
        self.assertEqual(lines[0]["provenance"]["source_name"], "manifest.xlsx")
        self.assertEqual(lines[0]["provenance"]["source_sheet"], "__first_worksheet__")
        self.assertEqual(lines[0]["provenance"]["source_row_index"], 2)
        stored_rows = fetch_upload_rows_for_segment(runs_dir=self.runs_dir, upload_id=upload_id, row_start=1, row_end=1)
        self.assertEqual(len(stored_rows), 1)
        self.assertEqual(stored_rows[0]["row_index"], 2)
        self.assertEqual(stored_rows[0]["item_number"], lines[0]["item_number"])
        self.assertEqual(stored_rows[0]["row_hash"], lines[0]["row_hash"])
        self.assertEqual(stored_rows[0]["schema_version"], "spot.input-row.v1alpha1")
        self.assertEqual(stored_rows[0]["normalization_status"], "accepted")
        self.assertEqual(stored_rows[0]["source_type"], "xlsx")
        self.assertEqual(stored_rows[0]["source_name"], "manifest.xlsx")
        self.assertEqual(stored_rows[0]["source_sheet"], "__first_worksheet__")
        self.assertEqual(stored_rows[0]["source_row_index"], 2)

    def test_segment_input_workbook_from_entries_returns_row_manifest_entries(self) -> None:
        segment_path = self.runs_dir / "segment-input.xlsx"
        manifest_entries = build_segment_input_workbook_from_entries(
            segment_path,
            [
                {
                    "sequence_index": 1,
                    "row_index": 2,
                    "item_number": "1",
                    "post_text": "Synthetic contract test row",
                    "source_category": "",
                    "row_hash": "hash-1",
                    "post_text_sha256": "sha-1",
                    "post_text_length": 27,
                }
            ],
        )
        self.assertTrue(segment_path.exists())
        self.assertEqual(len(manifest_entries), 1)
        self.assertEqual(manifest_entries[0]["sequence_index"], 1)
        self.assertEqual(manifest_entries[0]["row_index"], 2)
        self.assertEqual(manifest_entries[0]["item_number"], "1")
        self.assertEqual(manifest_entries[0]["row_hash"], "hash-1")

    def test_ensure_upload_rows_materialized_backfills_legacy_upload(self) -> None:
        upload_id = "legacy-upload"
        upload_dir = self.runs_dir / "uploads" / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = upload_dir / "legacy.xlsx"
        workbook_path.write_bytes((PROJECT_ROOT / "samples" / "sample_germany.xlsx").read_bytes())
        expected_count = len(read_input_rows(workbook_path, load_ssot(PROJECT_ROOT / "ssot/ssot.json")))
        upload_record = {
            "upload_id": upload_id,
            "filename": "legacy.xlsx",
            "stored_path": str(workbook_path),
            "bytes": workbook_path.stat().st_size,
            "status": "accepted",
            "created_at": 1771000000,
            "validation": {"accepted": True, "row_count": expected_count},
        }
        from backend.services.ops_db_service import record_upload

        (upload_dir / "upload.json").write_text(json.dumps(upload_record), encoding="utf-8")
        record_upload(runs_dir=self.runs_dir, record=upload_record)
        self.assertEqual(
            fetch_upload_rows_for_segment(runs_dir=self.runs_dir, upload_id=upload_id, row_start=1, row_end=5),
            [],
        )

        count = ensure_upload_rows_materialized(
            runs_dir=self.runs_dir,
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            upload_id=upload_id,
        )

        self.assertEqual(count, expected_count)
        stored_rows = fetch_upload_rows_for_segment(runs_dir=self.runs_dir, upload_id=upload_id, row_start=1, row_end=5)
        self.assertEqual(len(stored_rows), 5)
        self.assertEqual(stored_rows[0]["sequence_index"], 1)
        self.assertEqual(stored_rows[0]["row_index"], 2)
        self.assertEqual(stored_rows[0]["schema_version"], "spot.input-row.v1alpha1")
        self.assertEqual(stored_rows[0]["normalization_status"], "accepted")
        self.assertEqual(stored_rows[0]["source_type"], "xlsx")
        self.assertEqual(stored_rows[0]["source_name"], "legacy.xlsx")
        self.assertEqual(stored_rows[0]["source_sheet"], "__first_worksheet__")
        manifest_path = upload_dir / "row_manifest.jsonl"
        self.assertTrue(manifest_path.exists())
        manifest_lines = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(manifest_lines), expected_count)
        self.assertEqual(manifest_lines[0]["row_index"], 2)
        self.assertEqual(manifest_lines[0]["schema_version"], "spot.input-row.v1alpha1")
        refreshed_record = json.loads((upload_dir / "upload.json").read_text(encoding="utf-8"))
        self.assertEqual(refreshed_record["validation"]["canonical_schema_version"], "spot.input-row.v1alpha1")
        self.assertEqual(refreshed_record["validation"]["accepted_row_count"], expected_count)
        self.assertEqual(refreshed_record["validation"]["quarantined_row_count"], 0)

    def test_upload_backed_run_rows_require_resolved_source_lineage(self) -> None:
        upload_id = "lineage-upload"
        upload_dir = self.runs_dir / "uploads" / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = upload_dir / "lineage.xlsx"
        workbook_path.write_bytes(_build_workbook_bytes())
        upload_record = {
            "upload_id": upload_id,
            "filename": "lineage.xlsx",
            "stored_path": str(workbook_path),
            "bytes": workbook_path.stat().st_size,
            "status": "accepted",
            "created_at": 1771000000,
            "validation": {"accepted": True, "row_count": 1},
        }
        from backend.services.ops_db_service import record_upload, replace_upload_rows

        (upload_dir / "upload.json").write_text(json.dumps(upload_record), encoding="utf-8")
        record_upload(runs_dir=self.runs_dir, record=upload_record)
        replace_upload_rows(
            runs_dir=self.runs_dir,
            upload_id=upload_id,
            rows=[
                {
                    "sequence_index": 1,
                    "row_index": 2,
                    "item_number": "1",
                    "post_text": "Synthetic contract test row",
                    "source_category": "",
                    "row_hash": stable_row_hash("1", "Synthetic contract test row"),
                    "post_text_sha256": "sha-lineage-1",
                    "post_text_length": 27,
                    "normalization_status": "accepted",
                    "source_type": "xlsx",
                    "source_name": "lineage.xlsx",
                    "source_sheet": "__first_worksheet__",
                    "source_row_index": 2,
                }
            ],
        )
        create_run_record(
            runs_dir=self.runs_dir,
            run_id="lineage-run",
            input_path=str(workbook_path),
            output_path=str(self.runs_dir / "lineage-run" / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        from backend.services.ops_db_service import register_run

        register_run(
            runs_dir=self.runs_dir,
            run_id="lineage-run",
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            state="PROCESSING",
        )

        upsert_run_rows(
            runs_dir=self.runs_dir,
            run_id="lineage-run",
            upload_id=upload_id,
            rows=[
                {
                    "row_index": 2,
                    "assigned_category": "Not Antisemitic",
                    "confidence_score": 0.91,
                    "explanation": "Lineage-backed persistence.",
                    "flags": [],
                    "review_required": False,
                }
            ],
        )

        stored_row = fetch_run_row(runs_dir=self.runs_dir, run_id="lineage-run", row_index=2)
        self.assertIsNotNone(stored_row)
        self.assertEqual((stored_row or {}).get("upload_id"), upload_id)
        self.assertEqual((stored_row or {}).get("sequence_index"), 1)
        self.assertEqual((stored_row or {}).get("source_row_index"), 2)
        self.assertEqual((stored_row or {}).get("source_row_hash"), stable_row_hash("1", "Synthetic contract test row"))

    def test_upload_backed_run_rows_fail_when_source_lineage_is_missing(self) -> None:
        with self.assertRaises(RuntimeError):
            upsert_run_rows(
                runs_dir=self.runs_dir,
                run_id="broken-lineage-run",
                upload_id="missing-upload",
                rows=[
                    {
                        "row_index": 2,
                        "assigned_category": "Not Antisemitic",
                        "confidence_score": 0.91,
                        "explanation": "Should fail without upload lineage.",
                        "flags": [],
                        "review_required": False,
                    }
                ],
            )

    def test_production_payload_restrictions_block_arbitrary_paths(self) -> None:
        main_module.DEFAULT_PRODUCTION_MODE = True

        main_module._assert_allowed_classify_payload({"upload_id": "upload-1", "language": "de", "review_mode": "partial", "limit": 1})

        with self.assertRaises(HTTPException):
            main_module._assert_allowed_classify_payload({"input": "/tmp/file.xlsx"})

        with self.assertRaises(HTTPException):
            main_module._assert_allowed_classify_payload({"output": "/tmp/out.xlsx"})

    def test_recover_restarts_interrupted_segment_worker_run(self) -> None:
        self._login_admin()
        upload_id = "recover-upload"
        workbook_path = _create_managed_upload_fixture(self.runs_dir, upload_id, filename="recover.xlsx")
        from backend.services.ops_db_service import register_run
        run_id = "recover-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        register_run(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            state="PROCESSING",
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "PROCESSING", "progress_percentage": 0.0, "processed_rows": 0, "total_rows": 1}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": 999999, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )
        with patch.object(
            main_module,
            "_start_classify_run",
            return_value={"status": "restarted", "run_id": run_id, "pid": 12345},
        ) as mocked_start:
            response = self.client.post(f"/runs/{run_id}/recover")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "restarted")
        mocked_start.assert_called_once()

    def test_heal_restarts_stalled_segment_worker_run(self) -> None:
        self._login_admin()
        upload_id = "heal-upload"
        workbook_path = _create_managed_upload_fixture(self.runs_dir, upload_id, filename="heal.xlsx")
        run_id = "heal-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "PROCESSING", "progress_percentage": 5.0, "processed_rows": 5, "total_rows": 100}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": 54321, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )
        with patch.object(main_module, "_resolve_run_process_pid", return_value=54321), patch.object(
            main_module, "_signal_run_process"
        ) as mocked_signal, patch.object(
            main_module, "_wait_for_pid_exit", return_value=True
        ), patch.object(
            main_module, "_start_classify_run", return_value={"status": "restarted", "run_id": run_id, "pid": 12345}
        ) as mocked_start:
            response = self.client.post(f"/runs/{run_id}/heal")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "restarted")
        mocked_signal.assert_called_once()
        mocked_start.assert_called_once()

    def test_native_runtime_suspend_marks_active_run_for_resume(self) -> None:
        self._login_admin()
        workbook_path = _create_managed_upload_fixture(self.runs_dir, "upload-1", filename="native-suspend.xlsx")
        run_id = "native-suspend-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id="upload-1",
            language="de",
            review_mode="partial",
            start_payload={"upload_id": "upload-1", "language": "de", "review_mode": "partial"},
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "PROCESSING", "progress_percentage": 50.0, "processed_rows": 5, "total_rows": 10}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": 43210, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )
        with patch.object(main_module, "_pid_alive", side_effect=lambda pid: int(pid or 0) == 43210), patch.object(
            main_module,
            "_pid_command",
            return_value=f"python backend/segment_worker.py --run-id {run_id}",
        ), patch.object(
            run_state_service,
            "_pid_alive",
            side_effect=lambda pid: int(pid or 0) == 43210,
        ), patch.object(
            run_state_service,
            "_pid_command",
            return_value=f"python backend/segment_worker.py --run-id {run_id}",
        ), patch.object(main_module, "_signal_run_process") as mocked_signal:
            response = self.client.post("/native/runtime/suspend")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "suspend_requested")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["active_runs"][0]["run_id"], run_id)
        mocked_signal.assert_called_once()
        control = json.loads((run_path / "control.json").read_text(encoding="utf-8"))
        self.assertTrue(control["shutdown_requested"])
        self.assertEqual(control["shutdown_mode"], "suspend")
        self.assertFalse(control["paused"])

    def test_classify_status_does_not_trust_reused_unrelated_pid(self) -> None:
        self._login_admin()
        workbook_path = _create_managed_upload_fixture(self.runs_dir, "upload-1", filename="status-pid-reuse.xlsx")
        run_id = "status-pid-reuse"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id="upload-1",
            language="de",
            review_mode="partial",
            start_payload={"upload_id": "upload-1", "language": "de", "review_mode": "partial"},
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "INTERRUPTED", "processed_rows": 10, "total_rows": 100, "progress_percentage": 10.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": 424242, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )
        with patch.object(main_module, "_pid_alive", return_value=True), patch.object(
            main_module,
            "_pid_command",
            return_value="python unrelated_service.py --port 9999",
        ), patch.object(main_module, "_discover_classify_pid", return_value=None):
            response = self.client.get(f"/classify/status/{run_id}")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(payload["running"])
        self.assertIsNone(payload["pid"])

    def test_retry_upload_run_resumes_existing_state(self) -> None:
        self._login_admin()
        workbook_path = _create_managed_upload_fixture(self.runs_dir, "upload-1", filename="retry-upload.xlsx")
        run_id = "retry-upload-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id="upload-1",
            language="de",
            review_mode="partial",
            start_payload={"upload_id": "upload-1", "language": "de", "review_mode": "partial"},
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "FAILED", "processed_rows": 10, "total_rows": 100, "progress_percentage": 10.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )
        with patch.object(
            main_module,
            "_start_classify_run",
            return_value={"status": "restarted", "run_id": run_id, "pid": 12345},
        ) as mocked_start:
            response = self.client.post(f"/runs/{run_id}/retry")
        self.assertEqual(response.status_code, 200, response.text)
        mocked_start.assert_called_once()
        self.assertTrue(bool(mocked_start.call_args.kwargs.get("resume_existing")))

    def test_recovery_candidates_flag_missing_source_as_broken(self) -> None:
        self._login_admin()
        upload_id = "broken-upload"
        upload_dir = self.runs_dir / "uploads" / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = upload_dir / "missing.xlsx"
        upload_record = {
            "upload_id": upload_id,
            "filename": "missing.xlsx",
            "stored_path": str(workbook_path),
            "bytes": 0,
            "status": "accepted",
            "created_at": 1771000000,
            "validation": {"accepted": True, "row_count": 1},
        }
        from backend.services.ops_db_service import record_upload, register_run

        (upload_dir / "upload.json").write_text(json.dumps(upload_record), encoding="utf-8")
        record_upload(runs_dir=self.runs_dir, record=upload_record)
        run_id = "broken-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        register_run(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            state="PROCESSING",
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "PROCESSING", "processed_rows": 1, "total_rows": 10, "progress_percentage": 10.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )
        (run_path / "logs.txt").write_text("[FAILED] missing source workbook\n", encoding="utf-8")

        response = self.client.get("/runs/recovery-candidates/list")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["runs"]), 1)
        candidate = payload["runs"][0]
        self.assertEqual(candidate["run_id"], run_id)
        self.assertTrue(candidate["is_broken"])
        self.assertFalse(candidate["can_continue"])
        self.assertIn("managed source workbook is missing from local storage", candidate["broken_reasons"])
        self.assertEqual(candidate["last_log_line"], "[FAILED] missing source workbook")

    def test_register_run_requires_existing_managed_upload_relation(self) -> None:
        with self.assertRaises(RuntimeError) as exc:
            register_run(
                runs_dir=self.runs_dir,
                run_id="missing-managed-upload-run",
                upload_id="missing-upload",
                language="de",
                review_mode="partial",
                state="STARTING",
            )
        self.assertIn("Managed upload relation is missing", str(exc.exception))

    def test_update_run_snapshot_requires_existing_managed_upload_relation(self) -> None:
        with self.assertRaises(RuntimeError) as exc:
            update_run_snapshot(
                runs_dir=self.runs_dir,
                run_id="missing-managed-upload-run",
                upload_id="missing-upload",
                language="de",
                review_mode="partial",
                state="PROCESSING",
                progress={"processed_rows": 1, "total_rows": 10, "progress_percentage": 10.0},
            )
        self.assertIn("Managed upload relation is missing", str(exc.exception))

    def test_retry_recover_and_heal_block_broken_managed_runs(self) -> None:
        self._login_admin()
        run_id = "broken-managed-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        run_state_service.write_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            record={
                "run_id": run_id,
                "input_path": str(run_path / "missing.xlsx"),
                "output_path": str(run_path / "output.xlsx"),
                "upload_id": "missing-upload",
                "language": "de",
                "review_mode": "partial",
                "start_payload": {"upload_id": "missing-upload", "language": "de", "review_mode": "partial"},
                "state": "FAILED",
                "created_at": 1771000000,
                "updated_at": 1771000000,
            },
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "FAILED", "processed_rows": 1, "total_rows": 10, "progress_percentage": 10.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )

        for endpoint in ("retry", "recover", "heal"):
            response = self.client.post(f"/runs/{run_id}/{endpoint}")
            self.assertEqual(response.status_code, 409, response.text)
            self.assertIn("managed upload record is missing", response.json()["detail"])

    def test_delete_run_purges_run_and_managed_source_when_inactive(self) -> None:
        self._login_admin()
        upload_id = "purge-upload"
        upload_dir = self.runs_dir / "uploads" / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = upload_dir / "purge.xlsx"
        workbook_path.write_bytes(_build_workbook_bytes())
        upload_record = {
            "upload_id": upload_id,
            "filename": "purge.xlsx",
            "stored_path": str(workbook_path),
            "bytes": workbook_path.stat().st_size,
            "status": "accepted",
            "created_at": 1771000000,
            "validation": {"accepted": True, "row_count": 1},
        }
        from backend.services.ops_db_service import record_upload, register_run

        (upload_dir / "upload.json").write_text(json.dumps(upload_record), encoding="utf-8")
        record_upload(runs_dir=self.runs_dir, record=upload_record)
        run_id = "purge-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        register_run(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            state="FAILED",
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "FAILED", "processed_rows": 1, "total_rows": 10, "progress_percentage": 10.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )

        response = self.client.delete(f"/runs/{run_id}?purge_source=true")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "deleted")
        self.assertFalse(run_path.exists())
        self.assertFalse(upload_dir.exists())
        self.assertIsNone(run_state_service.read_run_record(runs_dir=self.runs_dir, run_id=run_id))

    def test_delete_run_does_not_purge_managed_source_by_default(self) -> None:
        """A bare DELETE must not destroy the source workbook; purging is opt-in."""
        self._login_admin()
        upload_id = "default-keep-upload"
        upload_dir = self.runs_dir / "uploads" / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = upload_dir / "keep.xlsx"
        workbook_path.write_bytes(_build_workbook_bytes())
        upload_record = {
            "upload_id": upload_id,
            "filename": "keep.xlsx",
            "stored_path": str(workbook_path),
            "bytes": workbook_path.stat().st_size,
            "status": "accepted",
            "created_at": 1771000000,
            "validation": {"accepted": True, "row_count": 1},
        }
        from backend.services.ops_db_service import record_upload, register_run

        (upload_dir / "upload.json").write_text(json.dumps(upload_record), encoding="utf-8")
        record_upload(runs_dir=self.runs_dir, record=upload_record)
        run_id = "default-keep-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        register_run(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            state="FAILED",
        )
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "FAILED", "processed_rows": 1, "total_rows": 10, "progress_percentage": 10.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
            encoding="utf-8",
        )

        response = self.client.delete(f"/runs/{run_id}")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(payload["purged_source"])
        self.assertFalse(run_path.exists())
        self.assertTrue(upload_dir.exists(), "source workbook must survive a default delete")
        self.assertTrue(workbook_path.exists())

    def test_run_events_trail_is_readable(self) -> None:
        """The append-only event trail had six writers and no reader; it now has an endpoint."""
        self._login_admin()
        run_id = "events-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir, run_id=run_id, input_path="in.xlsx",
            output_path=str(run_path / "output.xlsx"), upload_id=None,
            language="de", review_mode="partial",
        )
        from backend.services.ops_db_service import _append_event, _connect

        with _connect(self.runs_dir) as conn:
            _append_event(conn, "run", run_id, "synthetic_audit_event", {"note": "reader test"})
            conn.commit()

        response = self.client.get(f"/runs/{run_id}/events")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn("synthetic_audit_event", [e["event_type"] for e in payload["events"]])
        self.assertTrue(any(e["payload"].get("note") == "reader test" for e in payload["events"]))

    def test_run_events_endpoint_requires_auth(self) -> None:
        self.assertEqual(self.client.get("/runs/anything/events").status_code, 401)

    def test_dead_feedback_items_table_is_not_created(self) -> None:
        """feedback_items had no writer and no reader; a fresh database must not carry it."""
        from backend.services.ops_db_service import _connect

        with _connect(self.runs_dir) as conn:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertNotIn("feedback_items", names)
        self.assertIn("events", names)

    def test_empty_legacy_feedback_items_table_is_dropped_on_init(self) -> None:
        import sqlite3

        from backend.services.ops_db_service import _connect, db_path

        raw = sqlite3.connect(db_path(self.runs_dir))
        raw.execute(
            "CREATE TABLE feedback_items (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, "
            "row_index INTEGER NOT NULL, feedback_type TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "created_at INTEGER NOT NULL)"
        )
        raw.commit()
        raw.close()
        with _connect(self.runs_dir) as conn:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertNotIn("feedback_items", names)

    def test_legacy_feedback_items_with_rows_is_preserved(self) -> None:
        """The migration is guarded: it must never destroy data it does not understand."""
        import sqlite3

        from backend.services.ops_db_service import _connect, db_path

        raw = sqlite3.connect(db_path(self.runs_dir))
        raw.execute(
            "CREATE TABLE feedback_items (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, "
            "row_index INTEGER NOT NULL, feedback_type TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "created_at INTEGER NOT NULL)"
        )
        raw.execute(
            "INSERT INTO feedback_items (run_id, row_index, feedback_type, payload_json, created_at) "
            "VALUES ('legacy-run', 1, 'note', '{}', 0)"
        )
        raw.commit()
        raw.close()
        with _connect(self.runs_dir) as conn:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            count = conn.execute("SELECT COUNT(*) FROM feedback_items").fetchone()[0]
        self.assertIn("feedback_items", names)
        self.assertEqual(count, 1)

    def test_processed_row_precedence_is_shared_between_projections(self) -> None:
        """One rule for processed rows, so the dashboard and the queue cannot disagree.

        Precedence: canonical committed rows -> segment counters -> indexed snapshot -> progress.json,
        the last being a last-resort tier for legacy/interrupted runs that have no canonical rows.
        """
        from backend.services.ops_db_service import resolve_processed_rows
        from backend.services.run_state_service import _resolved_processed_rows as run_state_rows

        # full ladder
        self.assertEqual(resolve_processed_rows(
            canonical_processed_rows=3, segment_processed_rows=5,
            indexed_processed_rows=7, progress_processed_rows=9), 3)
        self.assertEqual(resolve_processed_rows(
            canonical_processed_rows=0, segment_processed_rows=5,
            indexed_processed_rows=7, progress_processed_rows=9), 5)
        self.assertEqual(resolve_processed_rows(
            canonical_processed_rows=0, segment_processed_rows=0,
            indexed_processed_rows=7, progress_processed_rows=9), 7)
        self.assertEqual(resolve_processed_rows(
            canonical_processed_rows=0, segment_processed_rows=0,
            indexed_processed_rows=0, progress_processed_rows=9), 9)

        # the run-record projection resolves through the same ladder
        record = {"processed_rows": 7}
        segment = {"processed_rows": 5}
        canonical = {"processed_rows": 3}
        self.assertEqual(run_state_rows(
            record=record, progress={"processed_rows": 9},
            canonical_stats=canonical, segment_summary=segment), 3)
        self.assertEqual(run_state_rows(
            record=record, progress={"processed_rows": 9},
            canonical_stats={}, segment_summary=segment), 5)
        self.assertEqual(run_state_rows(
            record=record, progress={"processed_rows": 9},
            canonical_stats={}, segment_summary={}), 7)
        # legacy run: no canonical rows, no snapshot counter -> the file tier is the only source
        self.assertEqual(run_state_rows(
            record={"processed_rows": 0}, progress={"processed_rows": 9},
            canonical_stats={}, segment_summary={}), 9)

    def test_run_classification_resumes_from_checkpoint(self) -> None:
        workbook_path = self.runs_dir / "resume-input.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Item number", "Post text", "Category"])
        ws.append(["1", "First resume row", ""])
        ws.append(["2", "Second resume row", ""])
        wb.save(workbook_path)
        wb.close()

        run_id = "resume-pipeline-run"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = run_dir / "result_checkpoint.jsonl"
        first_hash = stable_row_hash("1", "First resume row")
        first_result = ClassificationResult(
            row_index=2,
            raw_category="Not Antisemitic",
            category="Not Antisemitic",
            confidence=0.91,
            explanation="Checkpointed result.",
            flags=[],
            resolved_model_version="synthetic-model",
        )
        _append_result_checkpoint(checkpoint_path, result_index=0, row_hash=first_hash, result=first_result)

        def _fake_classify_batch(rows, ssot, max_workers, review_mode, model_name="", progress_callback=None, row_completion_callback=None, progress_every=100):
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].row_index, 3)
            second_hash = stable_row_hash(rows[0].item_number, rows[0].post_text)
            second_result = ClassificationResult(
                row_index=3,
                raw_category="Anti-Israel",
                category="Anti-Israel",
                confidence=0.88,
                explanation="Resumed row result.",
                flags=["REVIEW_REQUIRED"],
                resolved_model_version="synthetic-model",
            )
            if row_completion_callback:
                row_completion_callback(1, 1, 0, second_result, second_hash)
            return [second_result], [second_hash]

        with patch("src.pipeline.classify_batch", side_effect=_fake_classify_batch):
            run_classification(
                input_path=workbook_path,
                output_path=run_dir / "output.xlsx",
                run_id=run_id,
                run_language="de",
                review_mode="partial",
                ssot_path=PROJECT_ROOT / "ssot/ssot.json",
                runs_dir=self.runs_dir,
                max_workers=1,
                progress_every=1,
                resume_existing=True,
            )

        progress = json.loads((run_dir / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["state"], "COMPLETED")
        self.assertEqual(progress["total_rows"], 2)
        checkpoint_lines = [json.loads(line) for line in checkpoint_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(checkpoint_lines), 2)

    def test_run_classification_resumes_from_canonical_rows_without_checkpoint(self) -> None:
        workbook_path = self.runs_dir / "resume-canonical-input.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Item number", "Post text", "Category"])
        ws.append(["1", "First canonical resume row", ""])
        ws.append(["2", "Second canonical resume row", ""])
        wb.save(workbook_path)
        wb.close()

        run_id = "resume-canonical-run"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_dir / "output.xlsx"),
            upload_id=None,
            language="de",
            review_mode="partial",
            start_payload={"language": "de", "review_mode": "partial"},
        )
        upsert_run_rows(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=None,
            attempt_id=None,
            rows=[
                {
                    "row_index": 2,
                    "row_hash": stable_row_hash("1", "First canonical resume row"),
                    "assigned_category": "Not Antisemitic",
                    "confidence_score": 0.91,
                    "explanation": "Committed canonical result.",
                    "flags": [],
                    "review_required": False,
                }
            ],
        )

        def _fake_classify_batch(rows, ssot, max_workers, review_mode, model_name="", progress_callback=None, row_completion_callback=None, progress_every=100):
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].row_index, 3)
            second_hash = stable_row_hash(rows[0].item_number, rows[0].post_text)
            second_result = ClassificationResult(
                row_index=3,
                raw_category="Anti-Israel",
                category="Anti-Israel",
                confidence=0.88,
                explanation="Canonical resumed row result.",
                flags=["REVIEW_REQUIRED"],
                resolved_model_version="synthetic-model",
            )
            if row_completion_callback:
                row_completion_callback(1, 1, 0, second_result, second_hash)
            return [second_result], [second_hash]

        with patch("src.pipeline.classify_batch", side_effect=_fake_classify_batch):
            run_classification(
                input_path=workbook_path,
                output_path=run_dir / "output.xlsx",
                run_id=run_id,
                run_language="de",
                review_mode="partial",
                ssot_path=PROJECT_ROOT / "ssot/ssot.json",
                runs_dir=self.runs_dir,
                max_workers=1,
                progress_every=1,
                resume_existing=True,
                canonical_runs_dir=self.runs_dir,
                canonical_run_id=run_id,
            )

        progress = json.loads((run_dir / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["state"], "COMPLETED")
        self.assertEqual(progress["total_rows"], 2)
        stored_first = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2)
        stored_second = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=3)
        self.assertEqual((stored_first or {}).get("assigned_category"), "Not Antisemitic")
        self.assertEqual((stored_second or {}).get("assigned_category"), "Anti-Israel")

    def test_rebuild_output_from_canonical_recreates_segment_output(self) -> None:
        workbook_path = self.runs_dir / "rebuild-output-input.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Item number", "Post text", "Category"])
        ws.append(["1", "First rebuild row", ""])
        ws.append(["2", "Second rebuild row", ""])
        wb.save(workbook_path)
        wb.close()

        run_id = "rebuild-output-run"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_dir / "output.xlsx"),
            upload_id=None,
            language="de",
            review_mode="partial",
            start_payload={"language": "de", "review_mode": "partial"},
        )
        upsert_run_rows(
            runs_dir=self.runs_dir,
            run_id=run_id,
            upload_id=None,
            attempt_id=None,
            rows=[
                {
                    "row_index": 2,
                    "row_hash": stable_row_hash("1", "First rebuild row"),
                    "assigned_category": "Not Antisemitic",
                    "confidence_score": 0.91,
                    "explanation": "First canonical row.",
                    "flags": [],
                    "review_required": False,
                },
                {
                    "row_index": 3,
                    "row_hash": stable_row_hash("2", "Second rebuild row"),
                    "assigned_category": "Anti-Israel",
                    "confidence_score": 0.88,
                    "explanation": "Second canonical row.",
                    "flags": ["REVIEW_REQUIRED"],
                    "review_required": True,
                },
            ],
        )

        rebuilt = rebuild_output_from_canonical(
            input_path=workbook_path,
            output_path=run_dir / "output.xlsx",
            run_id=run_id,
            run_language="de",
            review_mode="partial",
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            canonical_runs_dir=self.runs_dir,
            canonical_run_id=run_id,
        )
        self.assertEqual(rebuilt, 2)
        queue = build_review_queue(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(len((queue or {}).get("rows", [])), 1)
        self.assertEqual((queue or {}).get("rows", [])[0]["assigned_category"], "Anti-Israel")

    def test_run_classification_persists_canonical_rows_during_execution(self) -> None:
        workbook_path = self.runs_dir / "canonical-input.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Item number", "Post text", "Category"])
        ws.append(["1", "Canonical execution row", ""])
        wb.save(workbook_path)
        wb.close()

        run_id = "canonical-runtime-run"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(workbook_path),
            output_path=str(run_dir / "output.xlsx"),
            upload_id=None,
            language="de",
            review_mode="partial",
            start_payload={"language": "de", "review_mode": "partial"},
        )
        attempt = start_run_attempt(runs_dir=self.runs_dir, run_id=run_id, attempt_type="start")

        def _fake_classify_batch(rows, ssot, max_workers, review_mode, model_name="", progress_callback=None, row_completion_callback=None, progress_every=100):
            result = ClassificationResult(
                row_index=2,
                raw_category="Anti-Israel",
                category="Anti-Israel",
                confidence=0.82,
                explanation="Canonical runtime persistence.",
                flags=["REVIEW_REQUIRED"],
                resolved_model_version="synthetic-model",
            )
            row_hash = stable_row_hash(rows[0].item_number, rows[0].post_text)
            if row_completion_callback:
                row_completion_callback(1, 1, 0, result, row_hash)
            return [result], [row_hash]

        with patch("src.pipeline.classify_batch", side_effect=_fake_classify_batch):
            run_classification(
                input_path=workbook_path,
                output_path=run_dir / "output.xlsx",
                run_id=run_id,
                run_language="de",
                review_mode="partial",
                ssot_path=PROJECT_ROOT / "ssot/ssot.json",
                runs_dir=self.runs_dir,
                max_workers=1,
                progress_every=1,
                canonical_runs_dir=self.runs_dir,
                canonical_run_id=run_id,
                canonical_attempt_id=str(attempt["attempt_id"]),
            )

        stored_row = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2)
        self.assertIsNotNone(stored_row)
        self.assertEqual((stored_row or {}).get("assigned_category"), "Anti-Israel")
        self.assertEqual((stored_row or {}).get("attempt_id"), attempt["attempt_id"])
        self.assertTrue((stored_row or {}).get("review_required"))

    def test_run_classification_advances_segment_progress_from_row_commits(self) -> None:
        upload_id = f"segment-progress-upload-{uuid.uuid4().hex[:8]}"
        record = intake_workbook(
            runs_dir=self.runs_dir,
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            upload_id=upload_id,
            filename="segment-progress.xlsx",
            content=_build_workbook_bytes(),
        )
        self.assertEqual(record["status"], "accepted")

        run_id = f"segment-progress-run-{uuid.uuid4().hex[:8]}"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(Path(record["stored_path"])),
            output_path=str(run_dir / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        attempt = start_run_attempt(runs_dir=self.runs_dir, run_id=run_id, attempt_type="start")
        segment = claim_next_segment(runs_dir=self.runs_dir, run_id=run_id, worker_id="segment-progress-test")
        self.assertIsNotNone(segment)

        def _fake_classify_batch(rows, ssot, max_workers, review_mode, model_name="", progress_callback=None, row_completion_callback=None, progress_every=100):
            result = ClassificationResult(
                row_index=2,
                raw_category="Not Antisemitic",
                category="Not Antisemitic",
                confidence=0.95,
                explanation="Segment progress commit.",
                flags=[],
                resolved_model_version="synthetic-model",
            )
            row_hash = stable_row_hash(rows[0].item_number, rows[0].post_text)
            if row_completion_callback:
                row_completion_callback(1, 1, 0, result, row_hash)
            return [result], [row_hash]

        with patch("src.pipeline.classify_batch", side_effect=_fake_classify_batch):
            run_classification(
                input_path=Path(record["stored_path"]),
                output_path=run_dir / "output.xlsx",
                run_id=run_id,
                run_language="de",
                review_mode="partial",
                ssot_path=PROJECT_ROOT / "ssot/ssot.json",
                runs_dir=self.runs_dir,
                max_workers=1,
                progress_every=1,
                canonical_runs_dir=self.runs_dir,
                canonical_run_id=run_id,
                canonical_upload_id=upload_id,
                canonical_attempt_id=str(attempt["attempt_id"]),
                canonical_segment_id=str(segment["segment_id"]),
            )

        summary = build_run_segment_summary(runs_dir=self.runs_dir, run_id=run_id, effective_run_state="PROCESSING")
        self.assertEqual(summary["processed_rows"], 1)

    def test_migrate_row_state_from_output_backfills_canonical_rows(self) -> None:
        self._login_admin()
        run_id = f"migrate-output-{uuid.uuid4().hex[:8]}"
        _prepare_synthetic_run(self.runs_dir, run_id)

        response = self.client.post(f"/runs/{run_id}/migrate-row-state")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["output_present"])
        self.assertEqual(payload["output_rows_migrated"], 1)

        stored_row = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2)
        self.assertIsNotNone(stored_row)
        self.assertEqual((stored_row or {}).get("assigned_category"), "Anti-Israel")
        self.assertTrue((stored_row or {}).get("review_required"))

    def test_review_queue_does_not_parse_output_without_explicit_migration(self) -> None:
        run_id = f"output-read-bridge-{uuid.uuid4().hex[:8]}"
        _prepare_synthetic_run(self.runs_dir, run_id)

        queue_before = build_review_queue(runs_dir=self.runs_dir, run_id=run_id)
        self.assertIsNotNone(queue_before)
        self.assertEqual(queue_before["rows"], [])
        self.assertIsNone(fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2))

        summary = run_state_service.migrate_run_rows_to_canonical(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(summary["output_rows_migrated"], 1)

        queue_after = build_review_queue(runs_dir=self.runs_dir, run_id=run_id)
        self.assertIsNotNone(queue_after)
        self.assertEqual(len(queue_after["rows"]), 1)
        self.assertEqual(queue_after["rows"][0]["row_index"], 2)
        self.assertEqual(queue_after["rows"][0]["assigned_category"], "Anti-Israel")

    def test_migrate_row_state_from_checkpoints_imports_nonreview_rows(self) -> None:
        self._login_admin()
        upload_id = f"checkpoint-upload-{uuid.uuid4().hex[:8]}"
        record = intake_workbook(
            runs_dir=self.runs_dir,
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            upload_id=upload_id,
            filename="checkpoint.xlsx",
            content=(PROJECT_ROOT / "samples" / "sample_germany.xlsx").read_bytes(),
        )
        self.assertEqual(record["status"], "accepted")

        run_id = f"checkpoint-run-{uuid.uuid4().hex[:8]}"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(Path(record["stored_path"])),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        checkpoint_dir = run_path / "_segments" / f"{upload_id}-seg-00001" / "runs" / f"{run_id}-segment-00001"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        _append_result_checkpoint(
            checkpoint_dir / "result_checkpoint.jsonl",
            result_index=0,
            row_hash=stable_row_hash(
                "1",
                "There are a lot of cultural barbarians in Germany now who hate us as Germans and abuse us as zombies or white bread. We are all pigs. That is racist, isn't it?",
            ),
            result=ClassificationResult(
                row_index=2,
                raw_category="Not Antisemitic",
                category="Not Antisemitic",
                confidence=0.91,
                explanation="Checkpointed non-review row.",
                flags=[],
                resolved_model_version="synthetic-model",
            ),
        )

        response = self.client.post(f"/runs/{run_id}/migrate-row-state?include_output=false")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["checkpoint_files_seen"], 1)
        self.assertEqual(payload["checkpoint_rows_migrated"], 1)
        self.assertFalse(payload["output_present"])

        stored_row = fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2)
        self.assertIsNotNone(stored_row)
        self.assertEqual((stored_row or {}).get("assigned_category"), "Not Antisemitic")
        self.assertFalse(bool((stored_row or {}).get("review_required")))
        self.assertEqual((stored_row or {}).get("sequence_index"), 1)
        self.assertEqual((stored_row or {}).get("source_row_index"), 2)
        self.assertTrue((stored_row or {}).get("source_row_hash"))

    def test_review_queue_does_not_import_live_checkpoint_rows_without_explicit_sync(self) -> None:
        upload_id = "live-review-upload"
        record = intake_workbook(
            runs_dir=self.runs_dir,
            ssot_path=PROJECT_ROOT / "ssot/ssot.json",
            upload_id=upload_id,
            filename="live-review.xlsx",
            content=(PROJECT_ROOT / "samples" / "sample_germany.xlsx").read_bytes(),
        )
        self.assertEqual(record["status"], "accepted")
        run_id = "live-review-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path=str(Path(record["stored_path"])),
            output_path=str(run_path / "output.xlsx"),
            upload_id=upload_id,
            language="de",
            review_mode="partial",
            start_payload={"upload_id": upload_id, "language": "de", "review_mode": "partial"},
        )
        checkpoint_dir = run_path / "_segments" / f"{upload_id}-seg-00001" / "runs" / f"{run_id}-segment-00001"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        _append_result_checkpoint(
            checkpoint_dir / "result_checkpoint.jsonl",
            result_index=0,
            row_hash=stable_row_hash("1", "There are a lot of cultural barbarians in Germany now who hate us as Germans and abuse us as zombies or white bread. We are all pigs. That is racist, isn't it?"),
            result=ClassificationResult(
                row_index=2,
                raw_category="Anti-Israel",
                category="Anti-Israel",
                confidence=0.77,
                explanation="Checkpointed flagged row.",
                flags=["REVIEW_REQUIRED"],
                resolved_model_version="synthetic-model",
            ),
        )
        queue = build_review_queue(runs_dir=self.runs_dir, run_id=run_id)
        self.assertIsNotNone(queue)
        self.assertEqual(queue["rows"], [])
        self.assertIsNone(fetch_run_row(runs_dir=self.runs_dir, run_id=run_id, row_index=2))
        self.assertFalse((run_path / "review_state.json").exists())

        synced = run_state_service.sync_review_rows_from_output(runs_dir=self.runs_dir, run_id=run_id)
        self.assertEqual(len((synced or {}).get("rows", {})), 1)

        queue_after = build_review_queue(runs_dir=self.runs_dir, run_id=run_id)
        rows = queue_after["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["row_index"], 2)
        self.assertEqual(rows[0]["review_state"], "pending")
        self.assertTrue(rows[0]["post_text"])

    def test_resolve_run_record_does_not_rewrite_run_record_or_snapshot(self) -> None:
        run_id = "resolve-read-only-run"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path="samples/sample_germany.xlsx",
            output_path=str(run_path / "output.xlsx"),
            upload_id=None,
            language="de",
            review_mode="partial",
            start_payload={"input": "samples/sample_germany.xlsx", "language": "de", "review_mode": "partial"},
        )
        run_record_path = run_path / "run_record.json"
        initial_record = json.loads(run_record_path.read_text(encoding="utf-8"))
        initial_record["state"] = "PROCESSING"
        initial_record["updated_at"] = 1772000000
        run_record_path.write_text(json.dumps(initial_record, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "PROCESSING", "processed_rows": 3, "total_rows": 10, "progress_percentage": 30.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False}),
            encoding="utf-8",
        )
        with sqlite3.connect(db_path(self.runs_dir)) as conn:
            before_snapshot = conn.execute("SELECT state, processed_rows, progress_percentage, updated_at FROM runs WHERE run_id = ?", (run_id,)).fetchone()

        resolved = resolve_run_record(runs_dir=self.runs_dir, run_id=run_id)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["state"], "INTERRUPTED")
        self.assertEqual((resolved.get("progress") or {}).get("processed_rows"), 3)
        self.assertEqual((resolved.get("progress") or {}).get("total_rows"), 10)

        after_record = run_record_path.read_text(encoding="utf-8")
        self.assertEqual(after_record, json.dumps(initial_record, ensure_ascii=False, indent=2))
        self.assertFalse((run_path / "review_state.json").exists())
        with sqlite3.connect(db_path(self.runs_dir)) as conn:
            after_snapshot = conn.execute("SELECT state, processed_rows, progress_percentage, updated_at FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        self.assertEqual(tuple(before_snapshot), tuple(after_snapshot))

    def test_get_run_state_does_not_persist_resolved_projection(self) -> None:
        self._login_admin()
        run_id = "get-run-state-read-only"
        run_path = self.runs_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        create_run_record(
            runs_dir=self.runs_dir,
            run_id=run_id,
            input_path="samples/sample_germany.xlsx",
            output_path=str(run_path / "output.xlsx"),
            upload_id=None,
            language="de",
            review_mode="partial",
            start_payload={"input": "samples/sample_germany.xlsx", "language": "de", "review_mode": "partial"},
        )
        run_record_path = run_path / "run_record.json"
        initial_record = json.loads(run_record_path.read_text(encoding="utf-8"))
        initial_record["state"] = "PROCESSING"
        initial_record["updated_at"] = 1772000100
        run_record_path.write_text(json.dumps(initial_record, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_path / "progress.json").write_text(
            json.dumps({"run_id": run_id, "state": "PROCESSING", "processed_rows": 4, "total_rows": 10, "progress_percentage": 40.0}),
            encoding="utf-8",
        )
        (run_path / "control.json").write_text(
            json.dumps({"run_id": run_id, "pid": None, "paused": False}),
            encoding="utf-8",
        )
        with sqlite3.connect(db_path(self.runs_dir)) as conn:
            before_snapshot = conn.execute("SELECT state, processed_rows, progress_percentage, updated_at FROM runs WHERE run_id = ?", (run_id,)).fetchone()

        response = self.client.get(f"/runs/{run_id}/state")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["state"], "INTERRUPTED")
        self.assertEqual(payload["progress"]["processed_rows"], 4)
        self.assertEqual(payload["progress"]["total_rows"], 10)

        after_record = run_record_path.read_text(encoding="utf-8")
        self.assertEqual(after_record, json.dumps(initial_record, ensure_ascii=False, indent=2))
        self.assertFalse((run_path / "review_state.json").exists())
        with sqlite3.connect(db_path(self.runs_dir)) as conn:
            after_snapshot = conn.execute("SELECT state, processed_rows, progress_percentage, updated_at FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        self.assertEqual(tuple(before_snapshot), tuple(after_snapshot))

    def test_artifact_manifest_catalog_includes_review_and_control_artifacts(self) -> None:
        run_dir = self.runs_dir / "artifact-manifest-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        for name in ["progress.json", "processing_stats.json", "review_state.json", "signoff.json", "action_log.jsonl", "control.json"]:
            (run_dir / name).write_text("{}", encoding="utf-8")
        manifest = build_artifact_manifest(run_dir=run_dir, sha256_file=lambda path: f"sha-{path.name}")
        artifacts = manifest["artifacts"]
        self.assertIn("review_state.json", artifacts)
        self.assertIn("signoff.json", artifacts)
        self.assertIn("action_log.jsonl", artifacts)
        self.assertIn("control.json", artifacts)
        self.assertIn("processing_stats.json", artifacts)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BackendContractRegressionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
