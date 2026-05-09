from __future__ import annotations

import os
import subprocess


DEFAULT_ACTIVE_RUN_STATES = {"STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING", "PAUSED"}


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def pid_command(pid: int | None) -> str:
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


def pid_matches_run(pid: int | None, run_id: str) -> bool:
    command = pid_command(pid)
    if not command or run_id not in command:
        return False
    return "backend/segment_worker.py" in command or "src.cli classify" in command


def discover_run_process_pid(run_id: str) -> int | None:
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


def resolve_run_process_pid(run_id: str, pid: int | None) -> int | None:
    if pid and pid_alive(pid) and pid_matches_run(pid, run_id):
        return int(pid)
    discovered = discover_run_process_pid(run_id)
    if discovered and pid_alive(discovered) and pid_matches_run(discovered, run_id):
        return int(discovered)
    return None


def run_process_alive(run_id: str, pid: int | None) -> bool:
    return resolve_run_process_pid(run_id, pid) is not None


def resolve_run_state(
    *,
    run_id: str,
    existing_state: str | None,
    progress: dict | list | None,
    control: dict | list | None,
    active_states: set[str] | None = None,
) -> str:
    progress_state = str(progress.get("state")) if isinstance(progress, dict) and progress.get("state") else ""
    control_dict = control if isinstance(control, dict) else {}
    running = run_process_alive(run_id, control_dict.get("pid"))
    paused = bool(control_dict.get("paused"))
    cancelled = bool(control_dict.get("cancelled") or control_dict.get("stopped_at"))
    nonterminal = active_states or DEFAULT_ACTIVE_RUN_STATES
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


def effective_segment_state_for_run(*, segment_state: str, run_state: str | None) -> str:
    resolved_segment_state = str(segment_state or "READY").upper()
    resolved_run_state = str(run_state or "").upper()
    if resolved_segment_state == "PROCESSING" and resolved_run_state == "INTERRUPTED":
        return "QUEUED"
    return resolved_segment_state


def normalize_state_from_segments(*, state: str, segment_summary: dict | None) -> str:
    resolved = str(state or "UNKNOWN").upper()
    if resolved != "COMPLETED" or not isinstance(segment_summary, dict):
        return resolved

    total_segments = int(segment_summary.get("total_segments") or 0)
    if total_segments <= 0:
        return resolved

    status_counts = segment_summary.get("segments_by_status") or {}
    completed_segments = int(status_counts.get("COMPLETED") or 0)
    queued_segments = int(status_counts.get("QUEUED") or 0)
    processing_segments = int(status_counts.get("PROCESSING") or 0)
    failed_segments = int(status_counts.get("FAILED") or 0)
    blocked_segments = int(status_counts.get("BLOCKED") or 0)
    cancelled_segments = int(status_counts.get("CANCELLED") or 0)

    if completed_segments >= total_segments:
        return resolved
    if queued_segments > 0 or processing_segments > 0:
        return "INTERRUPTED"
    if failed_segments > 0 or blocked_segments > 0:
        return "FAILED"
    if cancelled_segments > 0:
        return "INTERRUPTED"
    return resolved
