from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from zipfile import BadZipFile

from backend.services.ops_db_service import build_run_segment_summary, reconcile_run_segments, register_run, update_run_snapshot
from openpyxl import load_workbook


RUN_RECORD = "run_record.json"
REVIEW_STATE = "review_state.json"
SIGNOFF = "signoff.json"
ACTION_LOG = "action_log.jsonl"
ARTIFACT_NAMES = [
    "output.xlsx",
    "integrity_report.json",
    "artifact_manifest.json",
    "policy.json",
    "logs.txt",
    "progress.json",
    "processing_stats.json",
    "review_state.json",
    "signoff.json",
    "action_log.jsonl",
    "disagreement_report.json",
    "control.json",
]
RUN_HISTORY_DIRNAME = "_history"


def run_dir(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / run_id


def run_history_dir(runs_dir: Path) -> Path:
    path = runs_dir / RUN_HISTORY_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_record_path(runs_dir: Path, run_id: str) -> Path:
    return run_dir(runs_dir, run_id) / RUN_RECORD


def review_state_path(runs_dir: Path, run_id: str) -> Path:
    return run_dir(runs_dir, run_id) / REVIEW_STATE


def signoff_path(runs_dir: Path, run_id: str) -> Path:
    return run_dir(runs_dir, run_id) / SIGNOFF


def action_log_path(runs_dir: Path, run_id: str) -> Path:
    return run_dir(runs_dir, run_id) / ACTION_LOG


def safe_read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fallback_processing_stats(record: dict, progress: dict | list | None) -> dict:
    progress_dict = progress if isinstance(progress, dict) else {}
    processed_rows = int(progress_dict.get("processed_rows") or 0)
    total_rows = int(progress_dict.get("total_rows") or 0)
    created_at = int(record.get("created_at") or 0)
    updated_at = int(record.get("updated_at") or created_at or 0)
    elapsed_seconds = max(updated_at - created_at, 0)
    return {
        "processed_rows": processed_rows,
        "total_rows": total_rows,
        "elapsed_seconds": elapsed_seconds,
        "avg_seconds_per_row": round(elapsed_seconds / processed_rows, 4) if processed_rows > 0 else None,
        "threat_rows_detected": None,
        "threat_rate": None,
        "projected_threat_rows": None,
        "review_required_rows_detected": None,
        "judged_rows": 0,
        "second_pass_candidates": None,
        "second_pass_completed": None,
        "second_pass_overrides": None,
    }


def append_action(
    *,
    runs_dir: Path,
    run_id: str,
    action: str,
    actor: str = "local-operator",
    payload: dict | None = None,
) -> None:
    path = action_log_path(runs_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": int(time.time()),
        "actor": actor,
        "action": action,
        "payload": payload or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_action_log(*, runs_dir: Path, run_id: str) -> list[dict]:
    path = action_log_path(runs_dir, run_id)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def create_run_record(
    *,
    runs_dir: Path,
    run_id: str,
    input_path: str,
    output_path: str,
    upload_id: str | None,
    language: str,
    review_mode: str,
    start_payload: dict | None = None,
) -> dict:
    record = {
        "run_id": run_id,
        "upload_id": upload_id,
        "input_path": input_path,
        "output_path": output_path,
        "language": language,
        "review_mode": review_mode,
        "start_payload": start_payload or {},
        "state": "STARTING",
        "review_summary": {
            "review_required_rows": 0,
            "reviewed_rows": 0,
            "pending_rows": 0,
        },
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    write_run_record(runs_dir=runs_dir, run_id=run_id, record=record)
    register_run(
        runs_dir=runs_dir,
        run_id=run_id,
        upload_id=upload_id,
        language=language,
        review_mode=review_mode,
        state="STARTING",
    )
    append_action(
        runs_dir=runs_dir,
        run_id=run_id,
        action="run_created",
        payload={"upload_id": upload_id, "input_path": input_path, "output_path": output_path},
    )
    return record


def write_run_record(*, runs_dir: Path, run_id: str, record: dict) -> dict:
    record["updated_at"] = int(time.time())
    path = run_record_path(runs_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def read_run_record(*, runs_dir: Path, run_id: str) -> dict | None:
    data = safe_read_json(run_record_path(runs_dir, run_id))
    return data if isinstance(data, dict) else None


def read_signoff(*, runs_dir: Path, run_id: str) -> dict | None:
    data = safe_read_json(signoff_path(runs_dir, run_id))
    return data if isinstance(data, dict) else None


def write_signoff(
    *,
    runs_dir: Path,
    run_id: str,
    decision: str,
    note: str,
    actor: str,
) -> dict:
    payload = {
        "run_id": run_id,
        "decision": decision,
        "note": note,
        "actor": actor,
        "timestamp": int(time.time()),
    }
    path = signoff_path(runs_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_action(runs_dir=runs_dir, run_id=run_id, actor=actor, action="run_signoff", payload=payload)
    return payload


def read_review_state(*, runs_dir: Path, run_id: str) -> dict:
    data = safe_read_json(review_state_path(runs_dir, run_id))
    if isinstance(data, dict):
        return data
    return {"run_id": run_id, "rows": {}}


def write_review_state(*, runs_dir: Path, run_id: str, state: dict) -> dict:
    path = review_state_path(runs_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def sync_review_rows_from_output(*, runs_dir: Path, run_id: str) -> dict:
    path = run_dir(runs_dir, run_id) / "output.xlsx"
    state = read_review_state(runs_dir=runs_dir, run_id=run_id)
    existing_rows = state.setdefault("rows", {})
    if not path.exists():
        return state

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except (BadZipFile, OSError, ValueError):
        # A run may create output.xlsx before the workbook zip is fully written.
        return state
    try:
        ws = wb[wb.sheetnames[0]]
        header = [str(v).strip() if v is not None else "" for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        header_idx = {name: idx for idx, name in enumerate(header)}
        required = [
            "Item number",
            "Post text",
            "Assigned Category",
            "Confidence Score",
            "Explanation / Reasoning",
            "Flags",
            "Fallback Events",
            "Review Required",
        ]
        if any(name not in header_idx for name in required):
            return state

        rows: dict[str, dict] = {}
        for row_index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            item_number = "" if row[header_idx["Item number"]] is None else str(row[header_idx["Item number"]]).strip()
            post_text = "" if row[header_idx["Post text"]] is None else str(row[header_idx["Post text"]]).strip()
            assigned = "" if row[header_idx["Assigned Category"]] is None else str(row[header_idx["Assigned Category"]]).strip()
            explanation = "" if row[header_idx["Explanation / Reasoning"]] is None else str(row[header_idx["Explanation / Reasoning"]]).strip()
            flags = "" if row[header_idx["Flags"]] is None else str(row[header_idx["Flags"]]).strip()
            fallback_events = "" if row[header_idx["Fallback Events"]] is None else str(row[header_idx["Fallback Events"]]).strip()
            soft_signal_score = row[header_idx["Soft Signal Score"]] if "Soft Signal Score" in header_idx else None
            soft_signal_flags = (
                "" if "Soft Signal Flags" not in header_idx or row[header_idx["Soft Signal Flags"]] is None else str(row[header_idx["Soft Signal Flags"]]).strip()
            )
            soft_signal_evidence = (
                ""
                if "Soft Signal Evidence" not in header_idx or row[header_idx["Soft Signal Evidence"]] is None
                else str(row[header_idx["Soft Signal Evidence"]]).strip()
            )
            review_required = "" if row[header_idx["Review Required"]] is None else str(row[header_idx["Review Required"]]).strip()
            if review_required != "YES":
                continue
            key = str(row_index)
            existing = existing_rows.get(key, {})
            rows[key] = {
                "row_index": row_index,
                "item_number": item_number,
                "post_text": post_text,
                "assigned_category": assigned,
                "confidence_score": row[header_idx["Confidence Score"]],
                "explanation": explanation,
                "flags": [part for part in flags.split(";") if part],
                "fallback_events": [part for part in fallback_events.split(";") if part],
                "soft_signal_score": soft_signal_score,
                "soft_signal_flags": [part for part in soft_signal_flags.split(";") if part],
                "soft_signal_evidence": [part.strip() for part in soft_signal_evidence.split("|") if part.strip()],
                "review_required": True,
                "review_state": existing.get("review_state", "pending"),
                "review_decision": existing.get("review_decision"),
                "reviewer_note": existing.get("reviewer_note", ""),
                "updated_at": int(time.time()),
            }
        state["rows"] = rows
        write_review_state(runs_dir=runs_dir, run_id=run_id, state=state)
    finally:
        wb.close()
    return state


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _pid_command(pid: int | None) -> str:
    if not pid:
        return ""
    try:
        return subprocess.check_output(
            ["ps", "-p", str(int(pid)), "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _discover_run_process_pid(run_id: str) -> int | None:
    try:
        out = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    needle = f"--run-id {run_id}"
    for line in out.splitlines():
        if needle not in line:
            continue
        if "backend/segment_worker.py" not in line and "src.cli classify" not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            return int(parts[1])
        except ValueError:
            continue
    return None


def _run_process_alive(run_id: str, pid: int | None) -> bool:
    if not _pid_alive(pid):
        return False
    command = _pid_command(pid)
    if not command or run_id not in command:
        return False
    return "backend/segment_worker.py" in command or "src.cli classify" in command


def _resolve_run_state(*, run_id: str, existing_state: str | None, progress: dict | list | None, control: dict | list | None) -> str:
    progress_state = str(progress.get("state")) if isinstance(progress, dict) and progress.get("state") else ""
    control_dict = control if isinstance(control, dict) else {}
    pid = control_dict.get("pid")
    running = _run_process_alive(run_id, pid)
    paused = bool(control_dict.get("paused"))
    cancelled = bool(control_dict.get("cancelled") or control_dict.get("stopped_at"))
    nonterminal = {"STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING", "PAUSED"}
    existing = str(existing_state or "UNKNOWN").upper()

    if cancelled and not running:
        return "CANCELLED"
    if paused and running:
        return "PAUSED"
    if progress_state in nonterminal and not running:
        return "INTERRUPTED"
    if existing in nonterminal and not running:
        return "INTERRUPTED"
    if progress_state:
        return progress_state
    return existing


def upsert_review_row(
    *,
    runs_dir: Path,
    run_id: str,
    row_index: int,
    review_state_value: str | None,
    review_decision: str | None,
    reviewer_note: str | None,
    actor: str,
) -> dict:
    state = read_review_state(runs_dir=runs_dir, run_id=run_id)
    rows = state.setdefault("rows", {})
    key = str(row_index)
    existing = rows.get(key, {"row_index": row_index, "review_required": True})
    if review_state_value is not None:
        existing["review_state"] = review_state_value
    if review_decision is not None:
        existing["review_decision"] = review_decision
    if reviewer_note is not None:
        existing["reviewer_note"] = reviewer_note
    existing["updated_at"] = int(time.time())
    rows[key] = existing
    write_review_state(runs_dir=runs_dir, run_id=run_id, state=state)
    append_action(
        runs_dir=runs_dir,
        run_id=run_id,
        actor=actor,
        action="review_row_updated",
        payload={"row_index": row_index, "review_state": review_state_value, "review_decision": review_decision},
    )
    return existing


def refresh_run_record(*, runs_dir: Path, run_id: str, sync_review_rows: bool = True) -> dict | None:
    record = read_run_record(runs_dir=runs_dir, run_id=run_id)
    if not record:
        return None
    progress = safe_read_json(run_dir(runs_dir, run_id) / "progress.json")
    processing_stats = safe_read_json(run_dir(runs_dir, run_id) / "processing_stats.json")
    control = safe_read_json(run_dir(runs_dir, run_id) / "control.json")
    control = control if isinstance(control, dict) else {}
    discovered_pid = _discover_run_process_pid(run_id)
    if discovered_pid and int(control.get("pid") or 0) != discovered_pid:
        control["pid"] = discovered_pid
        control.pop("shutdown_requested", None)
        control.pop("shutdown_requested_at", None)
        control.pop("shutdown_mode", None)
    elif _run_process_alive(run_id, control.get("pid")):
        control.pop("shutdown_requested", None)
        control.pop("shutdown_requested_at", None)
        control.pop("shutdown_mode", None)
    signoff = read_signoff(runs_dir=runs_dir, run_id=run_id)
    review_state = (
        sync_review_rows_from_output(runs_dir=runs_dir, run_id=run_id)
        if sync_review_rows
        else read_review_state(runs_dir=runs_dir, run_id=run_id)
    )

    rows = review_state.get("rows", {})
    detected_review = int(processing_stats.get("review_required_rows_detected") or 0) if isinstance(processing_stats, dict) else 0
    total_review = max(len(rows), detected_review)
    reviewed = sum(1 for row in rows.values() if row.get("review_state") not in {None, "", "pending"})
    record["state"] = _resolve_run_state(run_id=run_id, existing_state=record.get("state"), progress=progress, control=control)
    if record["state"] == "INTERRUPTED":
        reconciled = reconcile_run_segments(runs_dir=runs_dir, run_id=run_id, target_state="QUEUED")
        if reconciled:
            control = safe_read_json(run_dir(runs_dir, run_id) / "control.json")
            control = control if isinstance(control, dict) else {}
            rediscovered_pid = _discover_run_process_pid(run_id)
            if rediscovered_pid:
                control["pid"] = rediscovered_pid
                control.pop("shutdown_requested", None)
                control.pop("shutdown_requested_at", None)
                control.pop("shutdown_mode", None)
            record["state"] = _resolve_run_state(run_id=run_id, existing_state=record.get("state"), progress=progress, control=control)
            record["control"] = control
    record["progress"] = progress
    record["processing_stats"] = processing_stats if isinstance(processing_stats, dict) else _fallback_processing_stats(record, progress)
    record["control"] = control
    record["signoff"] = signoff
    record["review_summary"] = {
        "review_required_rows": total_review,
        "reviewed_rows": reviewed,
        "pending_rows": max(total_review - reviewed, 0),
    }
    persisted = write_run_record(runs_dir=runs_dir, run_id=run_id, record=record)
    update_run_snapshot(
        runs_dir=runs_dir,
        run_id=run_id,
        upload_id=str(record.get("upload_id")) if record.get("upload_id") else None,
        language=str(record.get("language")) if record.get("language") else None,
        review_mode=str(record.get("review_mode")) if record.get("review_mode") else None,
        state=str(record.get("state", "UNKNOWN")),
        progress=progress if isinstance(progress, dict) else None,
        created_at=int(record.get("created_at")) if record.get("created_at") else None,
    )
    return persisted


def list_run_records(*, runs_dir: Path) -> list[dict]:
    items = []
    if not runs_dir.exists():
        return items
    for child in sorted(runs_dir.iterdir(), reverse=True):
        if not child.is_dir() or child.name in {"uploads", RUN_HISTORY_DIRNAME}:
            continue
        record = refresh_run_record(runs_dir=runs_dir, run_id=child.name, sync_review_rows=False) or read_run_record(runs_dir=runs_dir, run_id=child.name)
        if record:
            items.append(record)
    return items


def build_run_detail(*, runs_dir: Path, run_id: str) -> dict | None:
    record = refresh_run_record(runs_dir=runs_dir, run_id=run_id, sync_review_rows=False)
    if not record:
        return None
    run_path = run_dir(runs_dir, run_id)
    progress = record.get("progress") or {}
    processing_stats = record.get("processing_stats") or {}
    signoff = record.get("signoff")
    review_state = read_review_state(runs_dir=runs_dir, run_id=run_id)
    review_rows = sorted(review_state.get("rows", {}).values(), key=lambda row: row.get("row_index", 0))
    review_required_target = max(
        len(review_rows),
        int(processing_stats.get("review_required_rows_detected") or 0) if isinstance(processing_stats, dict) else 0,
    )
    output_path = Path(str(record.get("output_path", ""))) if record.get("output_path") else None
    run_output_path = run_path / "output.xlsx"
    resolved_output = run_output_path if run_output_path.exists() else output_path

    artifacts = list_run_artifacts(runs_dir=runs_dir, run_id=run_id)
    control = record.get("control") or {}
    pid = control.get("pid")
    paused = bool(control.get("paused"))
    running = False
    if pid:
        running = _run_process_alive(run_id, pid)

    state = str(record.get("state", "UNKNOWN"))
    segment_summary = build_run_segment_summary(runs_dir=runs_dir, run_id=run_id)
    pending_segments = int(segment_summary.get("segments_by_status", {}).get("QUEUED", 0))
    processing_segments = int(segment_summary.get("segments_by_status", {}).get("PROCESSING", 0))
    failed_segments = int(segment_summary.get("segments_by_status", {}).get("FAILED", 0))
    next_actions = []
    if state in {"FAILED", "INTERRUPTED"}:
        next_actions.extend(["inspect_failure", "retry_when_supported"])
    if state in {"COMPLETED"}:
        next_actions.append("download_output")
        if review_required_target > 0:
            next_actions.append("review_flagged_rows")
        else:
            next_actions.append("sign_off")
    if state in {"STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING"}:
        next_actions.extend(["monitor_progress", "pause_or_stop_if_needed"])
    if state in {"INTERRUPTED", "FAILED"} and pending_segments > 0:
        next_actions.append("recover_segment_worker")
    if signoff:
        next_actions = ["view_signoff", "download_output"] + [x for x in next_actions if x != "sign_off"]
    next_actions = list(dict.fromkeys(next_actions))

    available_operations = {
        "pause": running and not paused and state in {"STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING"},
        "resume": running and paused,
        "cancel": running,
        "retry": (not running) and state in {"FAILED", "CANCELLED", "INTERRUPTED"},
        "recover": True,
    }
    recovery = {
        "running": running,
        "paused": paused,
        "pid": pid,
        "has_control": bool(control),
        "has_progress": isinstance(progress, dict),
        "output_ready": bool(resolved_output and Path(resolved_output).exists()),
        "can_retry": available_operations["retry"],
        "can_cancel": available_operations["cancel"],
        "can_resume_worker": (not running) and bool(record.get("upload_id")) and pending_segments > 0,
        "pending_segments": pending_segments,
        "processing_segments": processing_segments,
        "failed_segments": failed_segments,
    }

    return {
        "run_id": run_id,
        "state": state,
        "language": record.get("language"),
        "review_mode": record.get("review_mode"),
        "upload_id": record.get("upload_id"),
        "input_path": record.get("input_path"),
        "output_path": str(resolved_output) if resolved_output else record.get("output_path"),
        "output_ready": bool(resolved_output and Path(resolved_output).exists()),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "progress": {
            "state": progress.get("state"),
            "message": progress.get("message"),
            "total_rows": progress.get("total_rows"),
            "processed_rows": progress.get("processed_rows"),
            "progress_percentage": progress.get("progress_percentage"),
            "started_at": progress.get("started_at"),
            "completed_at": progress.get("completed_at"),
        },
        "processing_stats": processing_stats,
        "review_summary": record.get("review_summary"),
        "signoff": signoff,
        "next_actions": next_actions,
        "available_operations": available_operations,
        "recovery": recovery,
        "segment_summary": segment_summary,
        "review_rows_preview": review_rows[:10],
        "artifacts": artifacts,
    }


def list_run_artifacts(*, runs_dir: Path, run_id: str) -> list[dict]:
    run_path = run_dir(runs_dir, run_id)
    artifacts = []
    for name in ARTIFACT_NAMES:
        p = run_path / name
        if p.exists():
            artifacts.append({"name": name, "path": str(p), "bytes": p.stat().st_size})
    return artifacts


def build_artifact_center(*, runs_dir: Path, run_id: str) -> dict | None:
    record = refresh_run_record(runs_dir=runs_dir, run_id=run_id, sync_review_rows=False)
    if not record:
        return None
    artifacts = list_run_artifacts(runs_dir=runs_dir, run_id=run_id)
    items = []
    for item in artifacts:
        purpose = {
            "output.xlsx": "Governed output workbook",
            "integrity_report.json": "Integrity and distribution audit report",
            "artifact_manifest.json": "Artifact hash manifest",
            "policy.json": "Resolved run policy and route metadata",
            "logs.txt": "Execution log for the run lifecycle",
            "progress.json": "Lifecycle progress record",
            "processing_stats.json": "Live row/time/threat snapshot during processing",
            "review_state.json": "Persistent browser review state",
            "signoff.json": "Acceptance decision record",
            "action_log.jsonl": "Operator action log",
            "disagreement_report.json": "Disagreement evidence when produced",
            "control.json": "Local process control state",
        }.get(item["name"], "Run artifact")
        items.append(
            {
                **item,
                "purpose": purpose,
                "download_path": f"/runs/{run_id}/artifacts/download/{item['name']}",
            }
        )
    return {
        "run_id": run_id,
        "state": record.get("state"),
        "signoff": record.get("signoff"),
        "review_summary": record.get("review_summary"),
        "artifacts": items,
    }


def build_review_queue(
    *,
    runs_dir: Path,
    run_id: str,
    review_state_filter: str | None = None,
    decision_filter: str | None = None,
    sort_by: str = "row_index",
    sort_order: str = "asc",
) -> dict | None:
    record = refresh_run_record(runs_dir=runs_dir, run_id=run_id)
    if not record:
        return None
    state = sync_review_rows_from_output(runs_dir=runs_dir, run_id=run_id)
    rows = list(state.get("rows", {}).values())

    if review_state_filter and review_state_filter != "all":
        rows = [row for row in rows if str(row.get("review_state", "pending")) == review_state_filter]
    if decision_filter and decision_filter != "all":
        rows = [row for row in rows if str(row.get("review_decision") or "") == decision_filter]

    reverse = sort_order == "desc"
    if sort_by == "confidence":
        rows.sort(key=lambda row: float(row.get("confidence_score") or 0), reverse=reverse)
    elif sort_by == "category":
        rows.sort(key=lambda row: str(row.get("assigned_category") or ""), reverse=reverse)
    elif sort_by == "review_state":
        rows.sort(key=lambda row: str(row.get("review_state") or "pending"), reverse=reverse)
    else:
        rows.sort(key=lambda row: int(row.get("row_index") or 0), reverse=reverse)

    return {
        "run_id": run_id,
        "state": record.get("state"),
        "review_summary": record.get("review_summary"),
        "filters": {
            "review_state": review_state_filter or "all",
            "review_decision": decision_filter or "all",
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
        "rows": rows,
    }


def build_row_inspector(*, runs_dir: Path, run_id: str, row_index: int) -> dict | None:
    record = refresh_run_record(runs_dir=runs_dir, run_id=run_id)
    if not record:
        return None
    state = sync_review_rows_from_output(runs_dir=runs_dir, run_id=run_id)
    row = state.get("rows", {}).get(str(row_index))
    if not row:
        return None
    disagreement_path = run_dir(runs_dir, run_id) / "disagreement_report.json"
    disagreement_row = None
    if disagreement_path.exists():
        try:
            payload = json.loads(disagreement_path.read_text(encoding="utf-8"))
            for item in payload.get("rows", []):
                if int(item.get("row_index", -1)) == row_index:
                    disagreement_row = item
                    break
        except Exception:
            disagreement_row = None
    return {
        "run_id": run_id,
        "row_index": row_index,
        "run_state": record.get("state"),
        "language": record.get("language"),
        "review_mode": record.get("review_mode"),
        "row": row,
        "evidence": {
            "explanation": row.get("explanation"),
            "flags": row.get("flags", []),
            "fallback_events": row.get("fallback_events", []),
            "soft_signal_score": row.get("soft_signal_score"),
            "soft_signal_flags": row.get("soft_signal_flags", []),
            "soft_signal_evidence": row.get("soft_signal_evidence", []),
            "disagreement": disagreement_row,
        },
        "review_controls": {
            "review_state": row.get("review_state", "pending"),
            "review_decision": row.get("review_decision"),
            "reviewer_note": row.get("reviewer_note", ""),
        },
    }
