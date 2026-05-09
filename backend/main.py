from pathlib import Path
import json
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
import urllib.parse
import urllib.request

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from backend.services.auth_service import (
    ALLOWED_ROLES,
    SESSION_COOKIE,
    auth_enabled,
    create_session,
    delete_session,
    local_access_code,
)
from backend.services.request_auth import require_permission, session_payload
from backend.services.excel_service import intake_workbook, list_upload_records, read_upload_record
from backend.services.run_lifecycle_service import discover_run_process_pid, pid_alive, pid_command
from backend.services.ops_db_service import (
    build_operations_overview,
    build_run_segment_summary,
    reconcile_run_segments,
    reset_run_segments,
    resume_run_segments,
    start_run_attempt,
)
from backend.services.run_state_service import (
    append_action,
    build_artifact_center,
    build_run_detail,
    build_row_inspector,
    build_review_queue,
    create_run_record,
    list_run_records,
    read_action_log,
    read_review_state,
    read_run_record,
    refresh_run_record,
    run_dir,
    run_history_dir,
    sync_review_rows_from_output,
    upsert_review_row,
    write_run_record,
    write_signoff,
)
from src.excel_io import MAX_INPUT_FILE_BYTES
from src.defaults import (
    DEFAULT_INPUT_PATH,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCKED_SSOT_PATH,
    DEFAULT_MAX_WORKERS,
    DEFAULT_OLLAMA_URL,
    DEFAULT_PRODUCTION_MODE,
    DEFAULT_REVIEW_MODE,
    DEFAULT_SSOT_PATH,
)
from src.lanes import load_lane_config

app = FastAPI(title="{spot} Classification Backend", version="0.5.0")
RUNS_DIR = Path(os.getenv("RUNS_DIR", str(Path(__file__).resolve().parent.parent / "runs")))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_BIN = Path(os.getenv("SPOT_NATIVE_PYTHON_BIN") or sys.executable)
BACKEND_ACTIVE_RUN_STATES = {"STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING", "PAUSED"}
SUPERVISOR_PID = int(os.getenv("SPOT_NATIVE_SUPERVISOR_PID", "0") or "0")
_SUPERVISOR_WATCHDOG_STARTED = False


@app.get("/api/health")
def api_health():
    return {
        "ok": True,
        "status": "online",
        "launch": {"ready": True},
        "service": "{spot} Classification Backend",
        "version": "0.5.0",
        "auth_enabled": auth_enabled(),
        "host": "127.0.0.1",
        "port": 8765,
    }


@app.get("/auth/config")
def auth_config():
    return {
        "auth_enabled": auth_enabled(),
        "allowed_roles": sorted(ALLOWED_ROLES),
        "access_code_hint": "Set SPOT_LOCAL_ACCESS_CODE to rotate the shared local access code.",
    }


@app.get("/auth/session")
def auth_session(request: Request):
    session = session_payload(request)
    return {
        "auth_enabled": auth_enabled(),
        "authenticated": bool(session),
        "session": session,
    }


@app.post("/auth/login")
def auth_login(response: Response, payload: dict | None = Body(default=None)):
    payload = payload or {}
    if not auth_enabled():
        return {
            "auth_enabled": False,
            "authenticated": True,
            "session": {
                "session_id": "local-auth-disabled",
                "role": "admin",
                "actor_name": "local-admin",
                "auth_enabled": False,
            },
        }
    access_code = str(payload.get("access_code", ""))
    role = str(payload.get("role", "")).strip()
    actor_name = str(payload.get("actor_name", "")).strip() or role or "local-user"
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ALLOWED_ROLES)}")
    if access_code != local_access_code():
        raise HTTPException(status_code=403, detail="invalid local access code")
    session = create_session(role=role, actor_name=actor_name)
    response.set_cookie(
        SESSION_COOKIE,
        session["session_id"],
        httponly=True,
        samesite="lax",
        max_age=12 * 60 * 60,
    )
    return {"auth_enabled": True, "authenticated": True, "session": session}


@app.post("/auth/logout")
def auth_logout(request: Request, response: Response):
    delete_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE)
    return {"auth_enabled": auth_enabled(), "authenticated": False}


def _ssot_path_from_payload(payload: dict) -> Path:
    if DEFAULT_PRODUCTION_MODE:
        return Path(os.getenv("SPOT_LOCKED_SSOT_PATH", DEFAULT_LOCKED_SSOT_PATH))
    return Path(str(payload.get("ssot", DEFAULT_SSOT_PATH)))


def _resolve_input_path_from_payload(payload: dict) -> str:
    upload_id = payload.get("upload_id")
    if upload_id:
        record = read_upload_record(runs_dir=RUNS_DIR, upload_id=str(upload_id))
        if not record:
            raise HTTPException(status_code=404, detail="upload not found")
        if record.get("status") != "accepted":
            raise HTTPException(status_code=409, detail="upload is not accepted for run creation")
        stored_path = record.get("stored_path")
        if not stored_path or not Path(stored_path).exists():
            raise HTTPException(status_code=409, detail="accepted upload file is missing from local storage")
        return str(Path(stored_path))
    return str(payload.get("input", DEFAULT_INPUT_PATH))


@app.get("/runs/{run_id}")
def get_run(run_id: str, request: Request):
    require_permission(request, "view")
    run = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id, sync_review_rows=False)
    if run:
        return run
    progress_path = RUNS_DIR / run_id / "progress.json"
    if not progress_path.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return json.loads(progress_path.read_text(encoding="utf-8"))


@app.get("/runs")
def list_runs(request: Request):
    require_permission(request, "view")
    records = list_run_records(runs_dir=RUNS_DIR)
    if records:
        return records
    runs = []
    if not RUNS_DIR.exists():
        return runs
    for d in sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()], reverse=True):
        progress_path = d / "progress.json"
        if not progress_path.exists():
            continue
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        runs.append(
            {
                "run_id": progress.get("run_id", d.name),
                "status": progress.get("state"),
                "started_at": progress.get("started_at"),
                "completed_at": progress.get("completed_at"),
                "total_rows": progress.get("total_rows"),
                "progress_percentage": progress.get("progress_percentage"),
            }
        )
    return runs


@app.get("/runs/{run_id}/state")
def get_run_state(run_id: str, request: Request):
    require_permission(request, "view")
    run = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id, sync_review_rows=False)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/runs/{run_id}/detail")
def get_run_detail(run_id: str, request: Request):
    require_permission(request, "view")
    detail = build_run_detail(runs_dir=RUNS_DIR, run_id=run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="run not found")
    return detail


@app.get("/runs/{run_id}/review-rows")
def list_review_rows(
    run_id: str,
    request: Request,
    review_state: str = Query(default="all"),
    review_decision: str = Query(default="all"),
    sort_by: str = Query(default="row_index"),
    sort_order: str = Query(default="asc"),
):
    require_permission(request, "view")
    queue = build_review_queue(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        review_state_filter=review_state,
        decision_filter=review_decision,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if not queue:
        raise HTTPException(status_code=404, detail="run not found")
    return queue


@app.get("/runs/{run_id}/review-rows/{row_index}")
def get_review_row(run_id: str, row_index: int, request: Request):
    require_permission(request, "view")
    detail = build_row_inspector(runs_dir=RUNS_DIR, run_id=run_id, row_index=row_index)
    if not detail:
        raise HTTPException(status_code=404, detail="review row not found")
    return detail


@app.post("/runs/{run_id}/review-rows/{row_index}")
def update_review_row(run_id: str, row_index: int, request: Request, payload: dict | None = Body(default=None)):
    session = require_permission(request, "review")
    payload = payload or {}
    state = sync_review_rows_from_output(runs_dir=RUNS_DIR, run_id=run_id)
    if str(row_index) not in state.get("rows", {}):
        raise HTTPException(status_code=404, detail="review row not found")
    row = upsert_review_row(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        row_index=row_index,
        review_state_value=payload.get("review_state"),
        review_decision=payload.get("review_decision"),
        reviewer_note=payload.get("reviewer_note"),
        actor=str(session.get("actor_name", "local-reviewer")),
    )
    refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    return row


@app.get("/runs/{run_id}/actions")
def get_run_actions(run_id: str, request: Request):
    require_permission(request, "view")
    if not (RUNS_DIR / run_id).exists():
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "actions": read_action_log(runs_dir=RUNS_DIR, run_id=run_id)}


@app.post("/runs/{run_id}/signoff")
def run_signoff(run_id: str, request: Request, payload: dict | None = Body(default=None)):
    session = require_permission(request, "signoff")
    record = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    if not record:
        raise HTTPException(status_code=404, detail="run not found")
    if str(record.get("state")) != "COMPLETED":
        raise HTTPException(status_code=409, detail="run sign-off is only allowed after a completed run")
    review_summary = record.get("review_summary") or {}
    if int(review_summary.get("pending_rows") or 0) > 0:
        raise HTTPException(status_code=409, detail="run sign-off is blocked while review rows are still pending")
    required_artifacts = {"output.xlsx", "policy.json", "integrity_report.json", "artifact_manifest.json", "logs.txt"}
    available_artifacts = {item["name"] for item in (build_artifact_center(runs_dir=RUNS_DIR, run_id=run_id) or {}).get("artifacts", [])}
    missing_artifacts = sorted(required_artifacts - available_artifacts)
    if missing_artifacts:
        raise HTTPException(status_code=409, detail=f"run sign-off is blocked until required artifacts exist: {missing_artifacts}")
    payload = payload or {}
    decision = str(payload.get("decision", "")).strip()
    if decision not in {"accepted", "accepted_with_conditions", "not_accepted"}:
        raise HTTPException(status_code=400, detail="decision must be one of accepted, accepted_with_conditions, not_accepted")
    result = write_signoff(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        decision=decision,
        note=str(payload.get("note", "")),
        actor=str(session.get("actor_name", "acceptance-lead")),
    )
    refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    return result


@app.get("/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str, request: Request):
    require_permission(request, "view")
    center = build_artifact_center(runs_dir=RUNS_DIR, run_id=run_id)
    if not center:
        raise HTTPException(status_code=404, detail="run not found")
    return center


@app.get("/runs/{run_id}/artifacts/download/{artifact_name}")
def download_run_artifact(run_id: str, artifact_name: str, request: Request):
    require_permission(request, "download_artifact")
    center = build_artifact_center(runs_dir=RUNS_DIR, run_id=run_id)
    if not center:
        raise HTTPException(status_code=404, detail="run not found")
    for item in center["artifacts"]:
        if item["name"] == artifact_name:
            path = Path(item["path"])
            if not path.exists():
                raise HTTPException(status_code=404, detail="artifact file missing")
            return FileResponse(path, filename=artifact_name)
    raise HTTPException(status_code=404, detail="artifact not found")


@app.get("/uploads")
def list_uploads(request: Request):
    require_permission(request, "view")
    return list_upload_records(runs_dir=RUNS_DIR)


@app.get("/uploads/{upload_id}")
def get_upload(upload_id: str, request: Request):
    require_permission(request, "view")
    record = read_upload_record(runs_dir=RUNS_DIR, upload_id=upload_id)
    if not record:
        raise HTTPException(status_code=404, detail="upload not found")
    return record


@app.get("/operations/overview")
def operations_overview(request: Request):
    require_permission(request, "view")
    return build_operations_overview(runs_dir=RUNS_DIR)


@app.post("/uploads/intake")
async def upload_intake(request: Request):
    require_permission(request, "upload")
    filename = (
        urllib.parse.unquote(request.query_params.get("filename", "")).strip()
        or urllib.parse.unquote(request.headers.get("x-filename", "")).strip()
        or "upload.xlsx"
    )
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="empty request body")
    if len(content) > MAX_INPUT_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Input workbook is too large. Maximum supported size is {MAX_INPUT_FILE_BYTES // (1024 * 1024)} MiB.",
        )

    upload_id = f"upload-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    record = intake_workbook(
        runs_dir=RUNS_DIR,
        ssot_path=Path(DEFAULT_SSOT_PATH),
        upload_id=upload_id,
        filename=filename,
        content=content,
    )
    return record


def _safe_read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _control_path(run_id: str) -> Path:
    return RUNS_DIR / run_id / "control.json"


def _write_control(run_id: str, payload: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _control_path(run_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_control(run_id: str) -> dict | None:
    return _safe_read_json(_control_path(run_id))


def _pid_alive(pid: int | None) -> bool:
    return pid_alive(pid)


def _pid_command(pid: int | None) -> str:
    return pid_command(pid)


def _discover_classify_pid(run_id: str) -> int | None:
    return discover_run_process_pid(run_id)


def _resolve_run_process_pid(run_id: str, pid: int | None) -> int | None:
    if pid and _pid_alive(pid):
        command = _pid_command(pid)
        if command and run_id in command and ("backend/segment_worker.py" in command or "src.cli classify" in command):
            return int(pid)
    discovered = _discover_classify_pid(run_id)
    if discovered and _pid_alive(discovered):
        command = _pid_command(discovered)
        if command and run_id in command and ("backend/segment_worker.py" in command or "src.cli classify" in command):
            return int(discovered)
    return None


def _signal_run_process(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
        return
    except Exception:
        os.kill(pid, sig)


def _wait_for_pid_exit(pid: int | None, timeout_seconds: float = 5.0) -> bool:
    if pid is None:
        return True
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)
    return not _pid_alive(pid)


def _assert_production_mode_allows_eval() -> None:
    if DEFAULT_PRODUCTION_MODE:
        raise HTTPException(status_code=403, detail="Evaluation start is disabled in SPOT production mode")


def _assert_allowed_classify_payload(payload: dict) -> None:
    if not DEFAULT_PRODUCTION_MODE:
        return
    allowed_keys = {"upload_id", "language", "review_mode", "limit"}
    unexpected = sorted(set(payload.keys()) - allowed_keys)
    if unexpected:
        raise HTTPException(
            status_code=403,
            detail=f"Unsupported classify payload keys in SPOT production mode: {unexpected}",
        )


def _archive_existing_run_state(run_id: str) -> None:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        return
    history_root = run_history_dir(RUNS_DIR)
    archive_name = f"{run_id}-{int(time.time())}"
    destination = history_root / archive_name
    counter = 1
    while destination.exists():
        counter += 1
        destination = history_root / f"{archive_name}-{counter}"
    shutil.move(str(run_dir), str(destination))


def _ollama_server_reachable(timeout: float = 2.0) -> bool:
    base_url = DEFAULT_OLLAMA_URL.rsplit("/api/", 1)[0]
    tags_url = f"{base_url}/api/tags"
    request = urllib.request.Request(tags_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 0) < 300
    except Exception:
        return False


def _assert_required_local_model_services_ready() -> None:
    lane_config = load_lane_config()
    uses_ollama = any(
        backend == "ollama"
        for backend in [
            lane_config.classifier_backend,
            lane_config.classifier_fallback_backend,
            lane_config.drafter_backend,
            lane_config.drafter_fallback_backend,
            lane_config.judge_backend,
            lane_config.judge_fallback_backend,
        ]
    )
    if uses_ollama and not _ollama_server_reachable():
        raise HTTPException(
            status_code=409,
            detail="ollama runtime is required by the configured lane stack but the local ollama server is not reachable",
        )


def _find_blocking_active_run(*, excluding_run_id: str | None = None) -> dict | None:
    for record in _active_run_records(excluding_run_id=excluding_run_id):
        return record
    return None


def _active_run_records(*, excluding_run_id: str | None = None) -> list[dict]:
    active_records: list[dict] = []
    for record in list_run_records(runs_dir=RUNS_DIR):
        candidate_run_id = str(record.get("run_id") or "")
        if not candidate_run_id or candidate_run_id == excluding_run_id:
            continue
        state = str(record.get("state") or "").upper()
        if state not in BACKEND_ACTIVE_RUN_STATES:
            continue
        control = record.get("control") or {}
        pid = _resolve_run_process_pid(candidate_run_id, control.get("pid"))
        if pid is not None or state == "PAUSED":
            active_records.append(record)
    return active_records


def _mark_run_shutdown_requested(run_id: str) -> dict:
    control = _read_control(run_id) or {"run_id": run_id}
    control["shutdown_requested"] = True
    control["shutdown_mode"] = "suspend"
    control["shutdown_requested_at"] = int(time.time())
    control["paused"] = False
    _write_control(run_id, control)
    return control


def _request_run_suspend(*, run_id: str, actor: str) -> dict:
    record = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    if not record:
        raise HTTPException(status_code=404, detail="run not found")
    control = _mark_run_shutdown_requested(run_id)
    pid = _resolve_run_process_pid(run_id, control.get("pid"))
    if pid is not None:
        _signal_run_process(int(pid), signal.SIGTERM)
    append_action(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        actor=actor,
        action="classify_suspend_requested",
        payload={"pid": pid, "shutdown_mode": "suspend"},
    )
    return {
        "run_id": run_id,
        "pid": pid,
        "status": "suspend_requested",
        "state": record.get("state"),
    }


def _native_supervisor_watchdog() -> None:
    if SUPERVISOR_PID <= 0:
        return
    while True:
        time.sleep(2)
        if _pid_alive(SUPERVISOR_PID):
            continue
        for record in _active_run_records():
            run_id = str(record.get("run_id") or "")
            if not run_id:
                continue
            try:
                _request_run_suspend(run_id=run_id, actor="spot-native-supervisor-watchdog")
            except Exception:
                pass
        os.kill(os.getpid(), signal.SIGTERM)
        return


@app.on_event("startup")
def startup_native_supervisor_watchdog() -> None:
    global _SUPERVISOR_WATCHDOG_STARTED
    if SUPERVISOR_PID <= 0 or _SUPERVISOR_WATCHDOG_STARTED:
        return
    thread = threading.Thread(target=_native_supervisor_watchdog, name="spot-native-watchdog", daemon=True)
    thread.start()
    _SUPERVISOR_WATCHDOG_STARTED = True


@app.post("/classify/start/{run_id}")
def classify_start(run_id: str, request: Request, payload: dict | None = Body(default=None)):
    session = require_permission(request, "start_run")
    payload = payload or {}
    return _start_classify_run(run_id=run_id, payload=payload, actor=str(session.get("actor_name", "local-operator")))


def _start_classify_run(*, run_id: str, payload: dict, actor: str, resume_existing: bool = False) -> dict:
    _assert_required_local_model_services_ready()
    blocking_run = _find_blocking_active_run(excluding_run_id=run_id)
    if blocking_run:
        blocking_run_id = str(blocking_run.get("run_id") or "")
        blocking_state = str(blocking_run.get("state") or "UNKNOWN")
        raise HTTPException(
            status_code=409,
            detail=f"run '{blocking_run_id}' is already active in state '{blocking_state}'",
        )
    control = _read_control(run_id) or {}
    existing_pid = _resolve_run_process_pid(run_id, control.get("pid"))
    if existing_pid is not None:
        _signal_run_process(existing_pid, signal.SIGTERM)
        time.sleep(0.2)

    run_dir = RUNS_DIR / run_id
    _assert_allowed_classify_payload(payload)
    input_path = _resolve_input_path_from_payload(payload)
    if DEFAULT_PRODUCTION_MODE and not payload.get("upload_id"):
        raise HTTPException(status_code=403, detail="SPOT production mode requires classify runs to start from an accepted upload")
    output_path = (
        str(run_dir / "output.xlsx")
        if DEFAULT_PRODUCTION_MODE
        else str(payload.get("output", str(PROJECT_ROOT / "samples" / f"{run_id}_output.xlsx")))
    )
    ssot_path = str(_ssot_path_from_payload(payload))
    language = str(payload.get("language", DEFAULT_LANGUAGE))
    review_mode = str(payload.get("review_mode", DEFAULT_REVIEW_MODE))
    max_workers = str(payload.get("max_workers", DEFAULT_MAX_WORKERS))
    progress_every = str(payload.get("progress_every", DEFAULT_PROGRESS_EVERY))
    limit = payload.get("limit", None)
    source_state = None
    if resume_existing:
        existing_record = read_run_record(runs_dir=RUNS_DIR, run_id=run_id)
        if not existing_record:
            raise HTTPException(status_code=404, detail="run not found")
        source_state = str(existing_record.get("state") or "") or None
        existing_record["input_path"] = input_path
        existing_record["output_path"] = output_path
        existing_record["upload_id"] = str(payload.get("upload_id")) if payload.get("upload_id") is not None else existing_record.get("upload_id")
        existing_record["language"] = language
        existing_record["review_mode"] = review_mode
        existing_record["start_payload"] = payload
        existing_record["state"] = "STARTING"
        write_run_record(runs_dir=RUNS_DIR, run_id=run_id, record=existing_record)
    else:
        _archive_existing_run_state(run_id)
        create_run_record(
            runs_dir=RUNS_DIR,
            run_id=run_id,
            input_path=input_path,
            output_path=output_path,
            upload_id=str(payload.get("upload_id")) if payload.get("upload_id") is not None else None,
            language=language,
            review_mode=review_mode,
            start_payload=payload,
        )
    attempt = start_run_attempt(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        attempt_type="resume" if resume_existing else "start",
        source_state=source_state,
    )
    attempt_id = str(attempt.get("attempt_id") or "")
    if payload.get("upload_id"):
        if resume_existing:
            resume_run_segments(runs_dir=RUNS_DIR, run_id=run_id)
        else:
            reset_run_segments(runs_dir=RUNS_DIR, run_id=run_id)
        cmd = [
            str(PYTHON_BIN),
            str(PROJECT_ROOT / "backend" / "segment_worker.py"),
            "--run-id",
            run_id,
            "--upload-id",
            str(payload.get("upload_id") or ""),
            "--input",
            input_path,
            "--output",
            output_path,
            "--language",
            language,
            "--review-mode",
            review_mode,
            "--ssot",
            ssot_path,
            "--runs-dir",
            str(RUNS_DIR),
            "--max-workers",
            max_workers,
            "--progress-every",
            progress_every,
            "--attempt-id",
            attempt_id,
        ]
        if resume_existing:
            cmd.append("--resume-existing")
        log_path = RUNS_DIR / f"{run_id}-segment-worker.log"
    else:
        cmd = [
            str(PYTHON_BIN),
            "-m",
            "src.cli",
            "classify",
            "--input",
            input_path,
            "--output",
            output_path,
            "--run-id",
            run_id,
            "--language",
            language,
            "--review-mode",
            review_mode,
            "--ssot",
            ssot_path,
            "--runs-dir",
            "runs",
            "--max-workers",
            max_workers,
            "--progress-every",
            progress_every,
            "--canonical-runs-dir",
            str(RUNS_DIR),
            "--canonical-run-id",
            run_id,
            "--canonical-attempt-id",
            attempt_id,
        ]
        if payload.get("upload_id"):
            cmd.extend(["--canonical-upload-id", str(payload.get("upload_id"))])
        log_path = RUNS_DIR / f"{run_id}-classify-ui.log"
    if limit is not None:
        cmd.extend(["--limit", str(limit)])

    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    _write_control(
        run_id,
        {
            "run_id": run_id,
            "pid": proc.pid,
            "paused": False,
            "started_at": int(time.time()),
            "attempt_id": attempt_id,
            "input": input_path,
            "upload_id": payload.get("upload_id"),
            "output": output_path,
        },
    )
    append_action(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        action="classify_recovered" if resume_existing else "classify_started",
        actor=actor,
        payload={
            "pid": proc.pid,
            "attempt_id": attempt_id,
            "upload_id": payload.get("upload_id"),
            "language": language,
            "review_mode": review_mode,
        },
    )
    refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    return {
        "status": "restarted" if resume_existing else "started",
        "run_id": run_id,
        "pid": proc.pid,
        "attempt_id": attempt_id,
        "input": input_path,
        "upload_id": payload.get("upload_id"),
        "output": output_path,
    }


@app.post("/classify/pause/{run_id}")
def classify_pause(run_id: str, request: Request):
    session = require_permission(request, "manage_run")
    control = _read_control(run_id)
    pid = _resolve_run_process_pid(run_id, control.get("pid") if control else None)
    if not control:
        control = {"run_id": run_id, "pid": pid, "paused": False}
    if pid is None:
        raise HTTPException(status_code=404, detail="run process not found")
    _signal_run_process(pid, signal.SIGSTOP)
    control["paused"] = True
    control["paused_at"] = int(time.time())
    _write_control(run_id, control)
    append_action(runs_dir=RUNS_DIR, run_id=run_id, actor=str(session.get("actor_name", "local-operator")), action="classify_paused", payload={"pid": pid})
    refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    return {"status": "paused", "run_id": run_id, "pid": pid}


@app.post("/classify/resume/{run_id}")
def classify_resume(run_id: str, request: Request):
    session = require_permission(request, "manage_run")
    control = _read_control(run_id)
    pid = _resolve_run_process_pid(run_id, control.get("pid") if control else None)
    if not control:
        control = {"run_id": run_id, "pid": pid, "paused": True}
    if pid is None:
        raise HTTPException(status_code=404, detail="run process not found")
    _signal_run_process(pid, signal.SIGCONT)
    control["paused"] = False
    control["resumed_at"] = int(time.time())
    _write_control(run_id, control)
    append_action(runs_dir=RUNS_DIR, run_id=run_id, actor=str(session.get("actor_name", "local-operator")), action="classify_resumed", payload={"pid": pid})
    refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    return {"status": "resumed", "run_id": run_id, "pid": pid}


@app.post("/classify/stop/{run_id}")
def classify_stop(run_id: str, request: Request):
    session = require_permission(request, "manage_run")
    control = _read_control(run_id)
    pid = _resolve_run_process_pid(run_id, control.get("pid") if control else None)
    if not control:
        control = {"run_id": run_id, "pid": pid, "paused": False}
    if pid is None:
        raise HTTPException(status_code=404, detail="run process not found")
    _signal_run_process(pid, signal.SIGTERM)
    control["paused"] = False
    control["stopped_at"] = int(time.time())
    control["cancelled"] = True
    _write_control(run_id, control)
    record = read_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    if record:
        record["state"] = "CANCELLED"
        write_run_record(runs_dir=RUNS_DIR, run_id=run_id, record=record)
    append_action(runs_dir=RUNS_DIR, run_id=run_id, actor=str(session.get("actor_name", "local-operator")), action="classify_stopped", payload={"pid": pid})
    refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    return {"status": "stopped", "run_id": run_id, "pid": pid}


@app.post("/runs/{run_id}/cancel")
def run_cancel(run_id: str, request: Request):
    return classify_stop(run_id=run_id, request=request)


@app.post("/native/runtime/suspend")
def native_runtime_suspend(request: Request):
    session = require_permission(request, "manage_run")
    suspended = [
        _request_run_suspend(
            run_id=str(record.get("run_id") or ""),
            actor=str(session.get("actor_name", "spot-native-supervisor")),
        )
        for record in _active_run_records()
        if str(record.get("run_id") or "")
    ]
    return {
        "status": "suspend_requested",
        "active_runs": suspended,
        "count": len(suspended),
    }


@app.post("/runs/{run_id}/retry")
def run_retry(run_id: str, request: Request):
    session = require_permission(request, "manage_run")
    record = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    if not record:
        raise HTTPException(status_code=404, detail="run not found")
    if str(record.get("state")) not in {"FAILED", "CANCELLED", "INTERRUPTED"}:
        raise HTTPException(status_code=409, detail=f"run state '{record.get('state')}' is not retryable")
    control = record.get("control") or {}
    if _resolve_run_process_pid(run_id, control.get("pid")) is not None:
        raise HTTPException(status_code=409, detail="run is still active")
    payload = dict(record.get("start_payload") or {})
    if not payload:
        raise HTTPException(status_code=409, detail="run cannot be retried because start payload is unavailable")
    append_action(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        actor=str(session.get("actor_name", "local-operator")),
        action="classify_retry_requested",
        payload={"source_state": record.get("state")},
    )
    return _start_classify_run(
        run_id=run_id,
        payload=payload,
        actor=str(session.get("actor_name", "local-operator")),
        resume_existing=bool(record.get("upload_id")),
    )


@app.post("/runs/{run_id}/recover")
def run_recover(run_id: str, request: Request):
    session = require_permission(request, "manage_run")
    record = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    if not record:
        raise HTTPException(status_code=404, detail="run not found")
    control = record.get("control") or {}
    pid = _resolve_run_process_pid(run_id, control.get("pid"))
    segment_summary = build_run_segment_summary(runs_dir=RUNS_DIR, run_id=run_id)
    pending_segments = int(segment_summary.get("segments_by_status", {}).get("QUEUED", 0))
    processing_segments = int(segment_summary.get("segments_by_status", {}).get("PROCESSING", 0))
    should_resume_worker = (
        bool(record.get("upload_id"))
        and pid is None
        and str(record.get("state")) in {"INTERRUPTED", "FAILED"}
        and (pending_segments > 0 or processing_segments > 0)
    )
    if should_resume_worker:
        payload = dict(record.get("start_payload") or {})
        if not payload:
            raise HTTPException(status_code=409, detail="run cannot be recovered because start payload is unavailable")
        payload.setdefault("upload_id", record.get("upload_id"))
        payload.setdefault("language", record.get("language"))
        payload.setdefault("review_mode", record.get("review_mode"))
        return _start_classify_run(
            run_id=run_id,
            payload=payload,
            actor=str(session.get("actor_name", "local-operator")),
            resume_existing=True,
        )
    recovered_status = {
        "run_id": run_id,
        "pid": pid,
        "running": pid is not None,
        "paused": bool(control.get("paused")),
        "state": record.get("state"),
        "output_ready": bool(record.get("output_path") and Path(str(record.get("output_path"))).exists()),
        "pending_segments": pending_segments,
        "processing_segments": processing_segments,
    }
    append_action(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        actor=str(session.get("actor_name", "local-operator")),
        action="run_recovered",
        payload=recovered_status,
    )
    return recovered_status


@app.post("/runs/{run_id}/heal")
def run_heal(run_id: str, request: Request):
    session = require_permission(request, "manage_run")
    actor = str(session.get("actor_name", "local-operator"))
    record = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id)
    if not record:
        raise HTTPException(status_code=404, detail="run not found")
    payload = dict(record.get("start_payload") or {})
    if not payload:
        raise HTTPException(status_code=409, detail="run cannot be healed because start payload is unavailable")

    control = record.get("control") or {}
    pid = _resolve_run_process_pid(run_id, control.get("pid"))
    upload_id = str(record.get("upload_id") or payload.get("upload_id") or "")
    if upload_id:
        reconcile_run_segments(runs_dir=RUNS_DIR, run_id=run_id, target_state="QUEUED")
        _mark_run_shutdown_requested(run_id)
    if pid is not None:
        _signal_run_process(int(pid), signal.SIGTERM)
        if not _wait_for_pid_exit(pid):
            _signal_run_process(int(pid), signal.SIGKILL)
            _wait_for_pid_exit(pid, timeout_seconds=1.5)

    payload.setdefault("upload_id", record.get("upload_id"))
    payload.setdefault("language", record.get("language"))
    payload.setdefault("review_mode", record.get("review_mode"))
    append_action(
        runs_dir=RUNS_DIR,
        run_id=run_id,
        actor=actor,
        action="run_heal_requested",
        payload={"previous_pid": pid, "source_state": record.get("state"), "upload_id": payload.get("upload_id")},
    )
    return _start_classify_run(
        run_id=run_id,
        payload=payload,
        actor=actor,
        resume_existing=True,
    )


@app.get("/classify/status/{run_id}")
def classify_status(run_id: str, request: Request):
    require_permission(request, "view")
    record = refresh_run_record(runs_dir=RUNS_DIR, run_id=run_id, sync_review_rows=False)
    if record:
        progress = record.get("progress") if isinstance(record.get("progress"), dict) else None
        control = record.get("control") if isinstance(record.get("control"), dict) else {}
        pid = _resolve_run_process_pid(run_id, control.get("pid") if control else None)
        running = pid is not None
        paused = bool(control.get("paused")) if control else False
        output_path = record.get("output_path") or control.get("output")
        output_exists = bool(output_path and Path(str(output_path)).exists())
        effective_state = str(record.get("state") or "UNKNOWN")
        if paused and running:
            effective_state = "PAUSED"
        elif running and effective_state in {"NOT_STARTED", "UNKNOWN"}:
            effective_state = "STARTING"
        return {
            "run_id": run_id,
            "timestamp": int(time.time()),
            "effective_state": effective_state,
            "running": running,
            "paused": paused,
            "pid": pid,
            "progress": progress,
            "control": control,
            "output_exists": output_exists,
        }

    progress = _safe_read_json(RUNS_DIR / run_id / "progress.json")
    control = _read_control(run_id)
    pid = _resolve_run_process_pid(run_id, control.get("pid") if control else None)
    running = pid is not None
    paused = bool(control.get("paused")) if control else False
    output_path = control.get("output") if control else None
    output_exists = bool(output_path and Path(output_path).exists())
    effective_state = "NOT_STARTED"
    if progress:
        effective_state = str(progress.get("state") or "UNKNOWN")
    if paused and running:
        effective_state = "PAUSED"
    elif running and effective_state in {"NOT_STARTED", "UNKNOWN"}:
        effective_state = "STARTING"
    return {
        "run_id": run_id,
        "timestamp": int(time.time()),
        "effective_state": effective_state,
        "running": running,
        "paused": paused,
        "pid": pid,
        "progress": progress,
        "control": control,
        "output_exists": output_exists,
    }
