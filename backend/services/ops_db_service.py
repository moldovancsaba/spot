from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any


DB_FILENAME = "spot_ops.sqlite3"
DEFAULT_SEGMENT_SIZE = 500
ACTIVE_RUN_STATES = {"STARTING", "PENDING", "VALIDATING", "PROCESSING", "WRITING", "PAUSED"}
TERMINAL_SEGMENT_STATES = {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}


def db_path(runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir / DB_FILENAME


def _connect(runs_dir: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(runs_dir))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS uploads (
            upload_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            bytes INTEGER NOT NULL,
            status TEXT NOT NULL,
            row_count INTEGER,
            segment_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            validation_error_type TEXT,
            validation_message TEXT
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            upload_id TEXT,
            language TEXT,
            review_mode TEXT,
            state TEXT NOT NULL,
            total_rows INTEGER,
            processed_rows INTEGER,
            progress_percentage REAL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (upload_id) REFERENCES uploads(upload_id)
        );

        CREATE TABLE IF NOT EXISTS segments (
            segment_id TEXT PRIMARY KEY,
            upload_id TEXT NOT NULL,
            segment_index INTEGER NOT NULL,
            row_start INTEGER NOT NULL,
            row_end INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            run_id TEXT,
            state TEXT NOT NULL DEFAULT 'READY',
            processed_rows INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT,
            claimed_at INTEGER,
            started_at INTEGER,
            completed_at INTEGER,
            last_error TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (upload_id) REFERENCES uploads(upload_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS feedback_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            row_index INTEGER NOT NULL,
            feedback_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_segments_upload_id ON segments(upload_id);
        CREATE INDEX IF NOT EXISTS idx_segments_run_id ON segments(run_id);
        CREATE INDEX IF NOT EXISTS idx_runs_upload_id ON runs(upload_id);
        """
    )
    _ensure_column(conn, "segments", "state", "TEXT NOT NULL DEFAULT 'READY'")
    _ensure_column(conn, "segments", "processed_rows", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "segments", "worker_id", "TEXT")
    _ensure_column(conn, "segments", "claimed_at", "INTEGER")
    _ensure_column(conn, "segments", "started_at", "INTEGER")
    _ensure_column(conn, "segments", "completed_at", "INTEGER")
    _ensure_column(conn, "segments", "last_error", "TEXT")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column in columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _now_ts() -> int:
    return int(time.time())


def _safe_read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


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


def _resolved_run_state(*, run_id: str, indexed_state: str | None, progress: dict | None, control: dict | None) -> str:
    progress_state = str(progress.get("state") or "").upper() if isinstance(progress, dict) else ""
    existing = str(indexed_state or "UNKNOWN").upper()
    running = _run_process_alive(run_id, (control or {}).get("pid"))
    paused = bool((control or {}).get("paused"))
    cancelled = bool((control or {}).get("cancelled") or (control or {}).get("stopped_at"))
    nonterminal = ACTIVE_RUN_STATES

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


def _resolved_run_snapshot(runs_dir: Path, run_id: str, indexed_run: sqlite3.Row | None) -> dict | None:
    if not indexed_run:
        return None
    run_dir = runs_dir / run_id
    progress = _safe_read_json(run_dir / "progress.json")
    control = _safe_read_json(run_dir / "control.json")
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
    processing_stats = _safe_read_json(run_dir / "processing_stats.json")
    state = _resolved_run_state(run_id=run_id, indexed_state=str(indexed_run["state"] or ""), progress=progress, control=control)
    processed_rows = int(progress.get("processed_rows") or 0) if isinstance(progress, dict) else int(indexed_run["processed_rows"] or 0)
    total_rows = (
        int(progress.get("total_rows"))
        if isinstance(progress, dict) and progress.get("total_rows") not in {None, ""}
        else (int(indexed_run["total_rows"]) if indexed_run["total_rows"] is not None else None)
    )
    progress_percentage = (
        float(progress.get("progress_percentage") or 0.0)
        if isinstance(progress, dict)
        else float(indexed_run["progress_percentage"] or 0.0)
    )
    return {
        "run_id": run_id,
        "state": state,
        "processed_rows": processed_rows,
        "total_rows": total_rows,
        "progress_percentage": progress_percentage,
        "row_progress_percentage": round((processed_rows / total_rows) * 100, 2) if total_rows else (100.0 if state == "COMPLETED" else 0.0),
        "estimated_remaining_seconds": _estimate_remaining_seconds(indexed_run if state in ACTIVE_RUN_STATES else None),
        "processing_stats": processing_stats or _fallback_processing_stats(indexed_run),
    }


def _segment_rows(row_count: int, segment_size: int) -> list[dict]:
    segments: list[dict] = []
    if row_count <= 0:
        return segments
    segment_index = 0
    for start in range(1, row_count + 1, segment_size):
        segment_index += 1
        end = min(start + segment_size - 1, row_count)
        segments.append(
            {
                "segment_index": segment_index,
                "row_start": start,
                "row_end": end,
                "row_count": end - start + 1,
            }
        )
    return segments


def record_upload(*, runs_dir: Path, record: dict, segment_size: int = DEFAULT_SEGMENT_SIZE) -> dict:
    now = _now_ts()
    validation = record.get("validation") or {}
    row_count = int(validation.get("row_count") or 0) if validation.get("accepted") else 0
    segments = _segment_rows(row_count, segment_size) if record.get("status") == "accepted" else []
    with _connect(runs_dir) as conn:
        conn.execute(
            """
            INSERT INTO uploads (
                upload_id, filename, stored_path, bytes, status, row_count, segment_count, created_at, updated_at,
                validation_error_type, validation_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(upload_id) DO UPDATE SET
                filename=excluded.filename,
                stored_path=excluded.stored_path,
                bytes=excluded.bytes,
                status=excluded.status,
                row_count=excluded.row_count,
                segment_count=excluded.segment_count,
                updated_at=excluded.updated_at,
                validation_error_type=excluded.validation_error_type,
                validation_message=excluded.validation_message
            """,
            (
                record["upload_id"],
                record["filename"],
                record["stored_path"],
                int(record["bytes"]),
                record["status"],
                row_count or None,
                len(segments),
                int(record.get("created_at") or now),
                now,
                validation.get("error_type"),
                validation.get("message"),
            ),
        )
        conn.execute("DELETE FROM segments WHERE upload_id = ?", (record["upload_id"],))
        for item in segments:
            conn.execute(
                """
                INSERT INTO segments (
                    segment_id, upload_id, segment_index, row_start, row_end, row_count, run_id, state, processed_rows, worker_id, claimed_at,
                    started_at, completed_at, last_error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, 'READY', 0, NULL, NULL, NULL, NULL, NULL, ?, ?)
                """,
                (
                    f"{record['upload_id']}-seg-{item['segment_index']:05d}",
                    record["upload_id"],
                    item["segment_index"],
                    item["row_start"],
                    item["row_end"],
                    item["row_count"],
                    now,
                    now,
                ),
            )
        _append_event(conn, "upload", record["upload_id"], "upload_recorded", record)
        conn.commit()
    return build_upload_queue_summary(runs_dir=runs_dir, upload_id=record["upload_id"])


def register_run(*, runs_dir: Path, run_id: str, upload_id: str | None, language: str, review_mode: str, state: str) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        resolved_upload_id = upload_id
        if resolved_upload_id:
            upload_row = conn.execute("SELECT row_count FROM uploads WHERE upload_id = ?", (resolved_upload_id,)).fetchone()
            if not upload_row:
                resolved_upload_id = None
        else:
            upload_row = None
        total_rows = None
        if upload_row and upload_row["row_count"] is not None:
            total_rows = int(upload_row["row_count"])
        conn.execute(
            """
            INSERT INTO runs (run_id, upload_id, language, review_mode, state, total_rows, processed_rows, progress_percentage, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                upload_id=excluded.upload_id,
                language=excluded.language,
                review_mode=excluded.review_mode,
                state=excluded.state,
                total_rows=COALESCE(excluded.total_rows, runs.total_rows),
                updated_at=excluded.updated_at
            """,
            (run_id, resolved_upload_id, language, review_mode, state, total_rows, now, now),
        )
        if resolved_upload_id:
            conn.execute(
                """
                UPDATE segments
                SET run_id = ?,
                    state = CASE WHEN state IN ('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED') THEN state ELSE 'QUEUED' END,
                    processed_rows = CASE WHEN state = 'COMPLETED' THEN row_count ELSE processed_rows END,
                    worker_id = NULL,
                    claimed_at = NULL,
                    started_at = CASE WHEN state IN ('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED') THEN started_at ELSE NULL END,
                    completed_at = CASE WHEN state = 'COMPLETED' THEN completed_at ELSE NULL END,
                    last_error = NULL,
                    updated_at = ?
                WHERE upload_id = ?
                """,
                (run_id, now, resolved_upload_id),
            )
        _append_event(
            conn,
            "run",
            run_id,
            "run_registered",
            {"upload_id": resolved_upload_id, "language": language, "review_mode": review_mode, "state": state},
        )
        conn.commit()


def update_run_snapshot(
    *,
    runs_dir: Path,
    run_id: str,
    upload_id: str | None,
    language: str | None,
    review_mode: str | None,
    state: str,
    progress: dict | None,
    created_at: int | None = None,
) -> None:
    now = _now_ts()
    processed_rows = int(progress.get("processed_rows") or 0) if isinstance(progress, dict) else 0
    total_rows = progress.get("total_rows") if isinstance(progress, dict) else None
    progress_percentage = float(progress.get("progress_percentage") or 0) if isinstance(progress, dict) else 0.0
    with _connect(runs_dir) as conn:
        resolved_upload_id = upload_id
        if resolved_upload_id:
            upload_row = conn.execute("SELECT upload_id FROM uploads WHERE upload_id = ?", (resolved_upload_id,)).fetchone()
            if not upload_row:
                resolved_upload_id = None
        existing = conn.execute("SELECT created_at, total_rows FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        resolved_created = int(created_at or (existing["created_at"] if existing else now))
        resolved_total = int(total_rows) if total_rows not in {None, ""} else (int(existing["total_rows"]) if existing and existing["total_rows"] is not None else None)
        conn.execute(
            """
            INSERT INTO runs (run_id, upload_id, language, review_mode, state, total_rows, processed_rows, progress_percentage, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                upload_id=COALESCE(excluded.upload_id, runs.upload_id),
                language=COALESCE(excluded.language, runs.language),
                review_mode=COALESCE(excluded.review_mode, runs.review_mode),
                state=excluded.state,
                total_rows=COALESCE(excluded.total_rows, runs.total_rows),
                processed_rows=excluded.processed_rows,
                progress_percentage=excluded.progress_percentage,
                updated_at=excluded.updated_at
            """,
            (
                run_id,
                resolved_upload_id,
                language,
                review_mode,
                state,
                resolved_total,
                processed_rows,
                progress_percentage,
                resolved_created,
                now,
            ),
        )
        conn.commit()


def claim_next_segment(*, runs_dir: Path, run_id: str, worker_id: str) -> dict | None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        segment = conn.execute(
            """
            SELECT * FROM segments
            WHERE run_id = ? AND state IN ('QUEUED', 'READY')
            ORDER BY segment_index ASC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        if not segment:
            return None
        conn.execute(
            """
            UPDATE segments
            SET state = 'PROCESSING',
                worker_id = ?,
                claimed_at = COALESCE(claimed_at, ?),
                started_at = COALESCE(started_at, ?),
                updated_at = ?
            WHERE segment_id = ?
            """,
            (worker_id, now, now, now, segment["segment_id"]),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM segments WHERE segment_id = ?", (segment["segment_id"],)).fetchone()
    return dict(updated) if updated else None


def update_segment_progress(*, runs_dir: Path, segment_id: str, processed_rows: int) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        existing = conn.execute(
            "SELECT processed_rows FROM segments WHERE segment_id = ?",
            (segment_id,),
        ).fetchone()
        existing_rows = int(existing["processed_rows"] or 0) if existing else 0
        resolved_rows = max(max(int(processed_rows), 0), existing_rows)
        conn.execute(
            """
            UPDATE segments
            SET processed_rows = ?,
                state = CASE WHEN state IN ('FAILED', 'BLOCKED', 'CANCELLED', 'COMPLETED') THEN state ELSE 'PROCESSING' END,
                updated_at = ?
            WHERE segment_id = ?
            """,
            (resolved_rows, now, segment_id),
        )
        conn.commit()


def complete_segment(*, runs_dir: Path, segment_id: str) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        row = conn.execute("SELECT row_count FROM segments WHERE segment_id = ?", (segment_id,)).fetchone()
        if not row:
            return
        conn.execute(
            """
            UPDATE segments
            SET state = 'COMPLETED',
                processed_rows = ?,
                completed_at = ?,
                updated_at = ?,
                last_error = NULL
            WHERE segment_id = ?
            """,
            (int(row["row_count"]), now, now, segment_id),
        )
        conn.commit()


def fail_segment(*, runs_dir: Path, segment_id: str, error_message: str, state: str = "FAILED") -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        conn.execute(
            """
            UPDATE segments
            SET state = ?,
                updated_at = ?,
                completed_at = CASE WHEN ? IN ('FAILED', 'BLOCKED', 'CANCELLED') THEN ? ELSE completed_at END,
                last_error = ?
            WHERE segment_id = ?
            """,
            (state, now, state, now, error_message, segment_id),
        )
        conn.commit()


def reset_run_segments(*, runs_dir: Path, run_id: str) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        conn.execute(
            """
            UPDATE segments
            SET state = 'QUEUED',
                processed_rows = 0,
                worker_id = NULL,
                claimed_at = NULL,
                started_at = NULL,
                completed_at = NULL,
                last_error = NULL,
                updated_at = ?
            WHERE run_id = ?
            """,
            (now, run_id),
        )
        conn.commit()


def reconcile_run_segments(*, runs_dir: Path, run_id: str, target_state: str = "QUEUED") -> int:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        rows = conn.execute(
            """
            SELECT segment_id, row_count, processed_rows
            FROM segments
            WHERE run_id = ? AND state = 'PROCESSING'
            """,
            (run_id,),
        ).fetchall()
        if not rows:
            return 0
        count = 0
        for row in rows:
            row_count = int(row["row_count"] or 0)
            processed_rows = min(int(row["processed_rows"] or 0), row_count)
            resolved_state = "COMPLETED" if processed_rows >= row_count and row_count > 0 else target_state
            resolved_processed_rows = row_count if resolved_state == "COMPLETED" else 0
            conn.execute(
                """
                UPDATE segments
                SET state = ?,
                    processed_rows = ?,
                    worker_id = NULL,
                    completed_at = CASE WHEN ? = 'COMPLETED' THEN COALESCE(completed_at, ?) ELSE completed_at END,
                    updated_at = ?
                WHERE segment_id = ?
                """,
                (resolved_state, resolved_processed_rows, resolved_state, now, now, row["segment_id"]),
            )
            count += 1
        conn.commit()
    return count


def block_remaining_segments(*, runs_dir: Path, run_id: str, state: str, error_message: str) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        conn.execute(
            """
            UPDATE segments
            SET state = ?,
                completed_at = ?,
                updated_at = ?,
                last_error = COALESCE(last_error, ?)
            WHERE run_id = ? AND state NOT IN ('COMPLETED', 'FAILED', 'BLOCKED', 'CANCELLED')
            """,
            (state, now, now, error_message, run_id),
        )
        conn.commit()


def build_run_segment_summary(*, runs_dir: Path, run_id: str) -> dict[str, Any]:
    with _connect(runs_dir) as conn:
        segments = conn.execute("SELECT * FROM segments WHERE run_id = ? ORDER BY segment_index ASC", (run_id,)).fetchall()
    status_counts: dict[str, int] = {}
    total_rows = 0
    processed_rows = 0
    review: dict[str, Any] = {"total_segments": len(segments), "processed_rows": 0, "total_rows": 0, "segments_by_status": {}, "active_segment": None}
    for segment in segments:
        status = str(segment["state"] or "READY")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_rows += int(segment["row_count"] or 0)
        if status == "COMPLETED":
            processed_rows += int(segment["row_count"] or 0)
        if status == "PROCESSING" and review["active_segment"] is None:
            review["active_segment"] = dict(segment)
    review["total_rows"] = total_rows
    review["processed_rows"] = processed_rows
    review["segments_by_status"] = status_counts
    review["completed_segments"] = status_counts.get("COMPLETED", 0)
    review["progress_percentage"] = round((processed_rows / total_rows) * 100, 2) if total_rows else 0.0
    review["segment_progress_percentage"] = round((review["completed_segments"] / len(segments)) * 100, 2) if segments else 0.0
    return review


def _append_event(conn: sqlite3.Connection, entity_type: str, entity_id: str, event_type: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO events (entity_type, entity_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (entity_type, entity_id, event_type, json.dumps(payload, ensure_ascii=False), _now_ts()),
    )


def _estimate_remaining_seconds(run: sqlite3.Row | None) -> int | None:
    if not run:
        return None
    state = str(run["state"] or "UNKNOWN")
    if state not in ACTIVE_RUN_STATES:
        return 0 if state == "COMPLETED" else None
    total_rows = int(run["total_rows"] or 0)
    processed_rows = int(run["processed_rows"] or 0)
    created_at = int(run["created_at"] or 0)
    updated_at = int(run["updated_at"] or 0)
    elapsed = max(updated_at - created_at, 0)
    if total_rows <= 0 or processed_rows <= 0 or elapsed <= 0:
        return None
    rows_remaining = max(total_rows - processed_rows, 0)
    rows_per_second = processed_rows / elapsed
    if rows_per_second <= 0:
        return None
    return int(round(rows_remaining / rows_per_second))


def _row_progress_percentage(run: sqlite3.Row | None) -> float:
    if not run:
        return 0.0
    total_rows = int(run["total_rows"] or 0)
    processed_rows = int(run["processed_rows"] or 0)
    if total_rows <= 0:
        return 100.0 if str(run["state"] or "") == "COMPLETED" else 0.0
    return round(max(0.0, min(100.0, (processed_rows / total_rows) * 100.0)), 2)


def _read_processing_stats(runs_dir: Path, run_id: str | None) -> dict | None:
    if not run_id:
        return None
    path = runs_dir / run_id / "processing_stats.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _fallback_processing_stats(run: sqlite3.Row | None) -> dict | None:
    if not run:
        return None
    processed_rows = int(run["processed_rows"] or 0)
    total_rows = int(run["total_rows"] or 0)
    created_at = int(run["created_at"] or 0)
    updated_at = int(run["updated_at"] or 0)
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


def build_upload_queue_summary(*, runs_dir: Path, upload_id: str) -> dict:
    with _connect(runs_dir) as conn:
        upload = conn.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
        if not upload:
            return {"upload_id": upload_id, "segment_size": DEFAULT_SEGMENT_SIZE, "segments": {}}
        segments = conn.execute(
            "SELECT * FROM segments WHERE upload_id = ? ORDER BY segment_index ASC",
            (upload_id,),
        ).fetchall()
        run = conn.execute(
            "SELECT * FROM runs WHERE upload_id = ? ORDER BY updated_at DESC LIMIT 1",
            (upload_id,),
        ).fetchone()
        status_counts: dict[str, int] = {}
        for segment in segments:
            status = str(segment["state"] or "READY")
            status_counts[status] = status_counts.get(status, 0) + 1
        total_segments = len(segments)
        completed_segments = status_counts.get("COMPLETED", 0)
        segment_progress_pct = round((completed_segments / total_segments) * 100, 2) if total_segments else 0.0
        segment_processed_rows = sum(
            int(segment["row_count"] or 0)
            for segment in segments
            if str(segment["state"] or "READY") == "COMPLETED"
        )
        total_segment_rows = sum(int(segment["row_count"] or 0) for segment in segments)
        resolved_run = _resolved_run_snapshot(runs_dir, str(run["run_id"]), run) if run else None
        row_progress_pct = round((segment_processed_rows / total_segment_rows) * 100, 2) if total_segment_rows else (resolved_run or {}).get("row_progress_percentage", _row_progress_percentage(run))
        eta_seconds = (resolved_run or {}).get("estimated_remaining_seconds", _estimate_remaining_seconds(run))
        processing_stats = (resolved_run or {}).get("processing_stats") or _read_processing_stats(runs_dir, str(run["run_id"]) if run else None) or _fallback_processing_stats(run)
        return {
            "upload_id": upload_id,
            "status": upload["status"],
            "filename": upload["filename"],
            "row_count": upload["row_count"],
            "segment_size": DEFAULT_SEGMENT_SIZE,
            "segment_count": total_segments,
            "segments_by_status": status_counts,
            "progress_percentage": row_progress_pct if run else segment_progress_pct,
            "row_progress_percentage": row_progress_pct,
            "segment_progress_percentage": segment_progress_pct,
            "estimated_remaining_seconds": eta_seconds,
            "processing_stats": processing_stats,
            "run": resolved_run,
        }


def build_operations_overview(*, runs_dir: Path) -> dict:
    with _connect(runs_dir) as conn:
        uploads = conn.execute("SELECT upload_id FROM uploads ORDER BY created_at DESC").fetchall()
        summaries = [build_upload_queue_summary(runs_dir=runs_dir, upload_id=row["upload_id"]) for row in uploads]
        aggregate: dict[str, int] = {}
        total_segments = 0
        completed_segments = 0
        total_rows = 0
        processed_rows = 0
        for summary in summaries:
            total_segments += int(summary.get("segment_count") or 0)
            completed_segments += int((summary.get("segments_by_status") or {}).get("COMPLETED") or 0)
            total_rows += int(summary.get("row_count") or 0)
            run = summary.get("run") or {}
            processing_stats = summary.get("processing_stats") or {}
            processed_rows += int(processing_stats.get("processed_rows") or run.get("processed_rows") or 0)
            for name, value in (summary.get("segments_by_status") or {}).items():
                aggregate[name] = aggregate.get(name, 0) + int(value)
        active_uploads = sum(1 for summary in summaries if summary.get("run") and str((summary.get("run") or {}).get("state", "")) in ACTIVE_RUN_STATES)
        return {
            "uploads": len(summaries),
            "active_uploads": active_uploads,
            "total_segments": total_segments,
            "completed_segments": completed_segments,
            "total_rows": total_rows,
            "processed_rows": processed_rows,
            "progress_percentage": round((processed_rows / total_rows) * 100, 2) if total_rows else (round((completed_segments / total_segments) * 100, 2) if total_segments else 0.0),
            "segments_by_status": aggregate,
            "recent_uploads": summaries[:10],
        }
