#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.run_state_service import create_run_record

BASE_URL = "http://127.0.0.1:8765"
APP_PATH = Path("/Applications/spot.app")
RUNS_DIR = Path.home() / "Library" / "Application Support" / "spot" / "runs"
COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))


def request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    url = urllib.parse.urljoin(f"{BASE_URL}/", path.lstrip("/"))
    body = data
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, method=method, headers=request_headers)
    try:
        with OPENER.open(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def wait_for_health(timeout_seconds: int = 45) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            status, payload = request_json("/api/health")
            if status == 200 and payload.get("ok"):
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("native runtime did not become healthy in time")


def login_if_needed() -> None:
    status, payload = request_json("/auth/config")
    if status != 200:
        raise RuntimeError(f"auth config unavailable: {status} {payload}")
    if not payload.get("auth_enabled"):
        return
    status, payload = request_json(
        "/auth/login",
        method="POST",
        payload={"actor_name": "native-smoke", "role": "admin", "access_code": os.getenv("SPOT_LOCAL_ACCESS_CODE", "spot-local")},
    )
    if status != 200:
        raise RuntimeError(f"auth login failed: {status} {payload}")


def build_review_workbook(path: Path) -> None:
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
            "Native smoke flagged row.",
            "",
            "Anti-Israel",
            "CLASSIFIER_FALLBACK_FAILED",
            0.41,
            "Synthetic native smoke reasoning.",
            "LOW_CONFIDENCE",
            "YES",
        ]
    )
    wb.save(path)
    wb.close()


def prepare_completed_review_run(run_id: str) -> None:
    run_path = RUNS_DIR / run_id
    if run_path.exists():
        shutil.rmtree(run_path)
    run_path.mkdir(parents=True, exist_ok=True)
    output_path = run_path / "output.xlsx"
    build_review_workbook(output_path)
    create_run_record(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        input_path=str(REPO_ROOT / "samples" / "sample_germany.xlsx"),
        output_path=str(output_path),
        upload_id=None,
        language="de",
        review_mode="partial",
        start_payload={"language": "de", "review_mode": "partial", "limit": 1},
    )
    (run_path / "progress.json").write_text(
        json.dumps({"run_id": run_id, "state": "COMPLETED", "processed_rows": 1, "total_rows": 1, "progress_percentage": 100.0}),
        encoding="utf-8",
    )
    (run_path / "control.json").write_text(
        json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(output_path)}),
        encoding="utf-8",
    )
    (run_path / "artifact_manifest.json").write_text(json.dumps({"artifacts": ["output.xlsx"]}), encoding="utf-8")
    (run_path / "integrity_report.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    (run_path / "policy.json").write_text(json.dumps({"policy": "native-smoke"}), encoding="utf-8")
    (run_path / "logs.txt").write_text("native smoke log\n", encoding="utf-8")


def prepare_recoverable_run(run_id: str) -> None:
    sample_path = REPO_ROOT / "samples" / "sample_germany.xlsx"
    run_path = RUNS_DIR / run_id
    run_path.mkdir(parents=True, exist_ok=True)
    create_run_record(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        input_path=str(sample_path),
        output_path=str(run_path / "output.xlsx"),
        upload_id=None,
        language="de",
        review_mode="partial",
        start_payload={"language": "de", "review_mode": "partial", "limit": 1},
    )
    (run_path / "progress.json").write_text(
        json.dumps({"run_id": run_id, "state": "INTERRUPTED", "processed_rows": 0, "total_rows": 1, "progress_percentage": 0.0}),
        encoding="utf-8",
    )
    (run_path / "control.json").write_text(
        json.dumps({"run_id": run_id, "pid": None, "paused": False, "output": str(run_path / "output.xlsx")}),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Native acceptance smoke for {spot}.")
    parser.add_argument("--reinstall", action="store_true", help="Rebuild and reinstall /Applications/spot.app before the smoke.")
    args = parser.parse_args()

    if args.reinstall:
        subprocess.run(["bash", "build-bundle.sh"], cwd=REPO_ROOT / "app" / "macos", check=True)
        subprocess.run(["bash", "install-bundle.sh"], cwd=REPO_ROOT / "app" / "macos", check=True)

    if not APP_PATH.exists():
        raise RuntimeError("/Applications/spot.app is missing")

    subprocess.run(["pkill", "-x", "spot"], check=False)
    subprocess.run(["open", str(APP_PATH)], check=True)
    wait_for_health()
    login_if_needed()

    status, payload = request_json("/app")
    if status != 404:
        raise RuntimeError(f"expected deleted browser route to return 404, got {status} {payload}")

    sample_path = REPO_ROOT / "samples" / "sample_germany.xlsx"
    intake_status, intake_payload = request_json(
        f"/uploads/intake?filename={urllib.parse.quote('native-smoke.xlsx')}",
        method="POST",
        data=sample_path.read_bytes(),
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    )
    if intake_status != 200 or intake_payload.get("status") != "accepted":
        raise RuntimeError(f"native intake failed: {intake_status} {intake_payload}")

    completed_run_id = f"native-smoke-completed-{uuid.uuid4().hex[:8]}"
    recover_run_id = f"native-smoke-recover-{uuid.uuid4().hex[:8]}"
    prepare_completed_review_run(completed_run_id)
    prepare_recoverable_run(recover_run_id)

    status, review_payload = request_json(f"/runs/{completed_run_id}/review-rows")
    if status != 200 or not review_payload.get("rows"):
        raise RuntimeError(f"review queue failed: {status} {review_payload}")

    row_index = int(review_payload["rows"][0]["row_index"])
    status, inspector_payload = request_json(f"/runs/{completed_run_id}/review-rows/{row_index}")
    if status != 200 or int(inspector_payload.get("row_index") or 0) != row_index:
        raise RuntimeError(f"review inspector failed: {status} {inspector_payload}")

    status, artifacts_payload = request_json(f"/runs/{completed_run_id}/artifacts")
    artifact_names = {item["name"] for item in artifacts_payload.get("artifacts", [])} if status == 200 else set()
    if status != 200 or "output.xlsx" not in artifact_names:
        raise RuntimeError(f"artifact center failed: {status} {artifacts_payload}")

    status, recover_payload = request_json(f"/runs/{recover_run_id}/recover", method="POST")
    if status != 200 or recover_payload.get("run_id") != recover_run_id or "running" not in recover_payload:
        raise RuntimeError(f"recover failed: {status} {recover_payload}")

    print("native acceptance smoke passed")
    print(
        json.dumps(
            {
                "intake_upload_id": intake_payload.get("upload_id"),
                "review_run_id": completed_run_id,
                "recover_run_id": recover_run_id,
                "recover_state": recover_payload.get("state"),
                "review_rows": len(review_payload.get("rows", [])),
                "artifacts": sorted(artifact_names),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
