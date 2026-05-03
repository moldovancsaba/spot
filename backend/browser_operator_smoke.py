from __future__ import annotations

import io
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.main import RUNS_DIR, app
from backend.services.run_state_service import create_run_record, write_run_record


def _build_workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Item number", "Post text", "Category"])
    ws.append(["1", "Synthetic browser smoke row", ""])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _prepare_synthetic_run(run_id: str) -> Path:
    run_path = RUNS_DIR / run_id
    if run_path.exists():
        shutil.rmtree(run_path)
    run_path.mkdir(parents=True, exist_ok=True)

    create_run_record(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        input_path="samples/sample_germany.xlsx",
        output_path=str(run_path / "output.xlsx"),
        upload_id=None,
        language="de",
        review_mode="partial",
        start_payload={"input": "samples/sample_germany.xlsx", "language": "de", "review_mode": "partial", "limit": 1},
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
            "Synthetic flagged row for browser smoke.",
            "",
            "Anti-Israel",
            "CLASSIFIER_FALLBACK_FAILED",
            0.41,
            "Synthetic reasoning for browser smoke validation.",
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
    (run_path / "logs.txt").write_text("synthetic browser smoke log\n", encoding="utf-8")
    return run_path


def main() -> int:
    client = TestClient(app)
    unauth_upload = client.post("/uploads/intake", headers={"X-Filename": "unauth.xlsx"}, content=_build_workbook_bytes())
    assert unauth_upload.status_code == 401, unauth_upload.text
    unauth_runs = client.get("/runs")
    assert unauth_runs.status_code == 401, unauth_runs.text
    unauth_uploads = client.get("/uploads")
    assert unauth_uploads.status_code == 401, unauth_uploads.text

    login = client.post("/auth/login", json={"actor_name": "browser-smoke", "role": "admin", "access_code": "spot-local"})
    assert login.status_code == 200, login.text
    session = client.get("/auth/session")
    assert session.status_code == 200, session.text
    session_body = session.json()
    assert session_body["authenticated"] is True, session_body
    assert session_body["session"]["role"] == "admin", session_body

    upload = client.post(
        "/uploads/intake",
        headers={"X-Filename": "browser_smoke.xlsx"},
        content=_build_workbook_bytes(),
    )
    assert upload.status_code == 200, upload.text
    upload_body = upload.json()
    assert upload_body["status"] == "accepted", upload_body
    upload_record = client.get(f"/uploads/{upload_body['upload_id']}")
    assert upload_record.status_code == 200, upload_record.text

    run_id = f"browser-smoke-{uuid.uuid4().hex[:8]}"
    _prepare_synthetic_run(run_id)

    state = client.get(f"/runs/{run_id}/state")
    assert state.status_code == 200, state.text
    detail = client.get(f"/runs/{run_id}/detail")
    assert detail.status_code == 200, detail.text
    actions_before = client.get(f"/runs/{run_id}/actions")
    assert actions_before.status_code == 200, actions_before.text
    queue = client.get(f"/runs/{run_id}/review-rows")
    assert queue.status_code == 200, queue.text
    row = client.get(f"/runs/{run_id}/review-rows/2")
    assert row.status_code == 200, row.text
    artifacts = client.get(f"/runs/{run_id}/artifacts")
    assert artifacts.status_code == 200, artifacts.text
    missing_row_update = client.post(
        f"/runs/{run_id}/review-rows/999",
        json={"review_state": "reviewed", "review_decision": "confirm", "reviewer_note": "should fail"},
    )
    assert missing_row_update.status_code == 404, missing_row_update.text
    signoff_before_review = client.post(
        f"/runs/{run_id}/signoff",
        json={"decision": "accepted_with_conditions", "note": "should be blocked before review completion"},
    )
    assert signoff_before_review.status_code == 409, signoff_before_review.text

    review_update = client.post(
        f"/runs/{run_id}/review-rows/2",
        json={"review_state": "reviewed", "review_decision": "confirm", "reviewer_note": "browser smoke note"},
    )
    assert review_update.status_code == 200, review_update.text
    queue_filtered = client.get(f"/runs/{run_id}/review-rows?review_state=reviewed&review_decision=confirm")
    assert queue_filtered.status_code == 200, queue_filtered.text
    assert len(queue_filtered.json()["rows"]) == 1, queue_filtered.text
    signoff = client.post(
        f"/runs/{run_id}/signoff",
        json={"decision": "accepted_with_conditions", "note": "synthetic browser smoke signoff"},
    )
    assert signoff.status_code == 200, signoff.text
    recover = client.post(f"/runs/{run_id}/recover")
    assert recover.status_code == 200, recover.text
    retry = client.post(f"/runs/{run_id}/retry")
    assert retry.status_code == 409, retry.text
    download = client.get(f"/runs/{run_id}/artifacts/download/output.xlsx")
    assert download.status_code == 200, download.text
    actions_after = client.get(f"/runs/{run_id}/actions")
    assert actions_after.status_code == 200, actions_after.text
    assert len(actions_after.json()["actions"]) >= len(actions_before.json()["actions"]), actions_after.text

    for path, needle in {
        "/": "{spot} Browser Surface",
        "/app": "{spot} Browser Surface",
        f"/runs/{run_id}/view": "{spot} Run Workspace",
        f"/runs/{run_id}/review": "{spot} Review Workspace",
        f"/runs/{run_id}/review-rows/2/view": "{spot} Evidence Workspace",
        f"/runs/{run_id}/artifacts/view": "{spot} Artifact Workspace",
    }.items():
        res = client.get(path)
        assert res.status_code == 200, (path, res.status_code)
        assert needle in res.text, (path, needle)

    print(
        json.dumps(
            {
                "upload_id": upload_body["upload_id"],
                "run_id": run_id,
                "session_role": session_body["session"]["role"],
                "detail_state": detail.json()["state"],
                "review_rows": len(queue.json()["rows"]),
                "signoff": signoff.json()["decision"],
                "recover_state": recover.json()["state"],
                "retry_status": retry.status_code,
                "page_render_check": "passed",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"browser operator smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
