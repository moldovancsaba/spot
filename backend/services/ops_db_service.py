from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from backend.services.run_lifecycle_service import (
    DEFAULT_ACTIVE_RUN_STATES,
    discover_run_process_pid,
    effective_segment_state_for_run,
    normalize_state_from_segments,
    resolve_run_process_pid,
    resolve_run_state,
)

DB_FILENAME = "spot_ops.sqlite3"
DEFAULT_SEGMENT_SIZE = 500
ACTIVE_RUN_STATES = DEFAULT_ACTIVE_RUN_STATES
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

        CREATE TABLE IF NOT EXISTS upload_rows (
            upload_id TEXT NOT NULL,
            sequence_index INTEGER NOT NULL,
            row_index INTEGER NOT NULL,
            item_number TEXT NOT NULL,
            post_text TEXT NOT NULL,
            source_category TEXT,
            row_hash TEXT NOT NULL,
            post_text_sha256 TEXT NOT NULL,
            post_text_length INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (upload_id, sequence_index),
            FOREIGN KEY (upload_id) REFERENCES uploads(upload_id)
        );

        CREATE TABLE IF NOT EXISTS run_attempts (
            attempt_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            attempt_type TEXT NOT NULL,
            source_state TEXT,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            started_at INTEGER NOT NULL,
            completed_at INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS run_rows (
            run_id TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            upload_id TEXT,
            attempt_id TEXT,
            sequence_index INTEGER,
            item_number TEXT NOT NULL DEFAULT '',
            post_text TEXT NOT NULL DEFAULT '',
            row_hash TEXT,
            assigned_category TEXT,
            confidence_score REAL,
            explanation TEXT,
            flags_json TEXT NOT NULL DEFAULT '[]',
            fallback_events_json TEXT NOT NULL DEFAULT '[]',
            soft_signal_score REAL,
            soft_signal_flags_json TEXT NOT NULL DEFAULT '[]',
            soft_signal_evidence_json TEXT NOT NULL DEFAULT '[]',
            review_required INTEGER NOT NULL DEFAULT 0,
            review_state TEXT,
            review_decision TEXT,
            reviewer_note TEXT NOT NULL DEFAULT '',
            judge_score REAL,
            judge_verdict TEXT,
            consensus_tier TEXT,
            minority_label TEXT,
            model_votes_json TEXT,
            drafted_text TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (run_id, row_index),
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (upload_id) REFERENCES uploads(upload_id),
            FOREIGN KEY (attempt_id) REFERENCES run_attempts(attempt_id)
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
        CREATE INDEX IF NOT EXISTS idx_upload_rows_upload_sequence ON upload_rows(upload_id, sequence_index);
        CREATE INDEX IF NOT EXISTS idx_run_attempts_run_id ON run_attempts(run_id, attempt_number);
        CREATE INDEX IF NOT EXISTS idx_run_rows_run_id ON run_rows(run_id, row_index);
        CREATE INDEX IF NOT EXISTS idx_run_rows_review_required ON run_rows(run_id, review_required, review_state);
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


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _json_loads_dict(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resolved_run_state(*, run_id: str, indexed_state: str | None, progress: dict | None, control: dict | None) -> str:
    return resolve_run_state(
        run_id=run_id,
        existing_state=indexed_state,
        progress=progress,
        control=control,
        active_states=ACTIVE_RUN_STATES,
    )


def _resolved_total_rows(
    *,
    indexed_run: sqlite3.Row | None,
    progress: dict | None,
    segment_summary: dict[str, Any] | None = None,
) -> int | None:
    segment_total_rows = int((segment_summary or {}).get("total_rows") or 0)
    if segment_total_rows > 0:
        return segment_total_rows
    if isinstance(progress, dict) and progress.get("total_rows") not in {None, ""}:
        return int(progress.get("total_rows"))
    if indexed_run and indexed_run["total_rows"] is not None:
        return int(indexed_run["total_rows"])
    return None


def _resolved_processed_rows(
    *,
    indexed_run: sqlite3.Row | None,
    canonical_stats: dict[str, Any] | None,
    segment_summary: dict[str, Any] | None = None,
) -> int:
    canonical_processed_rows = int((canonical_stats or {}).get("processed_rows") or 0)
    if canonical_processed_rows > 0:
        return canonical_processed_rows
    segment_processed_rows = int((segment_summary or {}).get("processed_rows") or 0)
    if segment_processed_rows > 0:
        return segment_processed_rows
    if indexed_run:
        return int(indexed_run["processed_rows"] or 0)
    return 0


def _resolved_processing_stats(
    *,
    indexed_run: sqlite3.Row | None,
    processing_stats: dict | None,
    canonical_stats: dict[str, Any] | None,
    processed_rows: int,
    total_rows: int | None,
) -> dict[str, Any]:
    base = dict(processing_stats) if isinstance(processing_stats, dict) else {}
    if not base:
        base = dict(_fallback_processing_stats(indexed_run) or {})
    resolved = {
        **base,
        **(canonical_stats or {}),
        "processed_rows": processed_rows,
        "total_rows": total_rows,
    }
    return resolved


def _resolved_run_snapshot(runs_dir: Path, run_id: str, indexed_run: sqlite3.Row | None) -> dict | None:
    if not indexed_run:
        return None
    run_dir = runs_dir / run_id
    progress = _safe_read_json(run_dir / "progress.json")
    control = _safe_read_json(run_dir / "control.json")
    control = control if isinstance(control, dict) else {}
    discovered_pid = discover_run_process_pid(run_id)
    if discovered_pid and int(control.get("pid") or 0) != discovered_pid:
        control["pid"] = discovered_pid
        control.pop("shutdown_requested", None)
        control.pop("shutdown_requested_at", None)
        control.pop("shutdown_mode", None)
    elif resolve_run_process_pid(run_id, control.get("pid")) is not None:
        control.pop("shutdown_requested", None)
        control.pop("shutdown_requested_at", None)
        control.pop("shutdown_mode", None)
    processing_stats = _safe_read_json(run_dir / "processing_stats.json")
    canonical_stats = summarize_run_rows(runs_dir=runs_dir, run_id=run_id)
    state = _resolved_run_state(run_id=run_id, indexed_state=str(indexed_run["state"] or ""), progress=progress, control=control)
    segment_summary = build_run_segment_summary(runs_dir=runs_dir, run_id=run_id, effective_run_state=state)
    state = normalize_state_from_segments(state=state, segment_summary=segment_summary)
    processed_rows = _resolved_processed_rows(
        indexed_run=indexed_run,
        canonical_stats=canonical_stats,
        segment_summary=segment_summary,
    )
    total_rows = _resolved_total_rows(
        indexed_run=indexed_run,
        progress=progress,
        segment_summary=segment_summary,
    )
    progress_percentage = round((processed_rows / total_rows) * 100, 2) if total_rows else (100.0 if state == "COMPLETED" else 0.0)
    return {
        "run_id": run_id,
        "state": state,
        "processed_rows": processed_rows,
        "total_rows": total_rows,
        "progress_percentage": progress_percentage,
        "row_progress_percentage": round((processed_rows / total_rows) * 100, 2) if total_rows else (100.0 if state == "COMPLETED" else 0.0),
        "estimated_remaining_seconds": _estimate_remaining_seconds(indexed_run if state in ACTIVE_RUN_STATES else None),
        "segment_summary": segment_summary,
        "processing_stats": _resolved_processing_stats(
            indexed_run=indexed_run,
            processing_stats=processing_stats,
            canonical_stats=canonical_stats,
            processed_rows=processed_rows,
            total_rows=total_rows,
        ),
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


def replace_upload_rows(*, runs_dir: Path, upload_id: str, rows: list[dict]) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        conn.execute("DELETE FROM upload_rows WHERE upload_id = ?", (upload_id,))
        for row in rows:
            conn.execute(
                """
                INSERT INTO upload_rows (
                    upload_id, sequence_index, row_index, item_number, post_text, source_category,
                    row_hash, post_text_sha256, post_text_length, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    int(row["sequence_index"]),
                    int(row["row_index"]),
                    str(row.get("item_number") or ""),
                    str(row.get("post_text") or ""),
                    str(row.get("source_category") or ""),
                    str(row["row_hash"]),
                    str(row["post_text_sha256"]),
                    int(row["post_text_length"]),
                    now,
                ),
            )
        conn.commit()


def fetch_upload_rows_for_segment(*, runs_dir: Path, upload_id: str, row_start: int, row_end: int) -> list[dict]:
    with _connect(runs_dir) as conn:
        rows = conn.execute(
            """
            SELECT upload_id, sequence_index, row_index, item_number, post_text, source_category,
                   row_hash, post_text_sha256, post_text_length
            FROM upload_rows
            WHERE upload_id = ? AND sequence_index BETWEEN ? AND ?
            ORDER BY sequence_index ASC
            """,
            (upload_id, row_start, row_end),
        ).fetchall()
    return [dict(row) for row in rows]


def list_run_segments(*, runs_dir: Path, run_id: str) -> list[dict[str, Any]]:
    with _connect(runs_dir) as conn:
        rows = conn.execute(
            "SELECT * FROM segments WHERE run_id = ? ORDER BY segment_index ASC",
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_upload_rows_by_row_indices(*, runs_dir: Path, upload_id: str, row_indices: list[int]) -> dict[int, dict]:
    normalized = sorted({int(item) for item in row_indices if int(item) > 0})
    if not normalized:
        return {}
    placeholders = ",".join("?" for _ in normalized)
    with _connect(runs_dir) as conn:
        rows = conn.execute(
            f"""
            SELECT upload_id, sequence_index, row_index, item_number, post_text, source_category,
                   row_hash, post_text_sha256, post_text_length
            FROM upload_rows
            WHERE upload_id = ? AND row_index IN ({placeholders})
            ORDER BY row_index ASC
            """,
            (upload_id, *normalized),
        ).fetchall()
    return {int(row["row_index"]): dict(row) for row in rows}


def start_run_attempt(
    *,
    runs_dir: Path,
    run_id: str,
    attempt_type: str,
    source_state: str | None = None,
    status: str = "STARTING",
) -> dict[str, Any]:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(attempt_number), 0) AS max_attempt_number FROM run_attempts WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        attempt_number = int(row["max_attempt_number"] or 0) + 1
        attempt_id = f"{run_id}-attempt-{attempt_number:05d}-{now}"
        conn.execute(
            """
            INSERT INTO run_attempts (
                attempt_id, run_id, attempt_number, attempt_type, source_state, status, created_at, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (attempt_id, run_id, attempt_number, attempt_type, source_state, status, now, now),
        )
        conn.commit()
    return {
        "attempt_id": attempt_id,
        "run_id": run_id,
        "attempt_number": attempt_number,
        "attempt_type": attempt_type,
        "source_state": source_state,
        "status": status,
        "started_at": now,
    }


def latest_run_attempt(*, runs_dir: Path, run_id: str) -> dict[str, Any] | None:
    with _connect(runs_dir) as conn:
        row = conn.execute(
            """
            SELECT attempt_id, run_id, attempt_number, attempt_type, source_state, status, created_at, started_at, completed_at
            FROM run_attempts
            WHERE run_id = ?
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    return dict(row) if row else None


def update_latest_run_attempt_status(*, runs_dir: Path, run_id: str, status: str) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        row = conn.execute(
            "SELECT attempt_id FROM run_attempts WHERE run_id = ? ORDER BY attempt_number DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if not row:
            return
        completed_at = now if status.upper() in {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"} else None
        conn.execute(
            """
            UPDATE run_attempts
            SET status = ?,
                completed_at = COALESCE(?, completed_at)
            WHERE attempt_id = ?
            """,
            (status, completed_at, row["attempt_id"]),
        )
        conn.commit()


def _decode_run_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "row_index": int(row["row_index"]),
        "upload_id": str(row["upload_id"]) if row["upload_id"] else None,
        "attempt_id": str(row["attempt_id"]) if row["attempt_id"] else None,
        "sequence_index": int(row["sequence_index"]) if row["sequence_index"] is not None else None,
        "item_number": str(row["item_number"] or ""),
        "post_text": str(row["post_text"] or ""),
        "row_hash": str(row["row_hash"]) if row["row_hash"] else None,
        "assigned_category": str(row["assigned_category"]) if row["assigned_category"] else "",
        "confidence_score": float(row["confidence_score"]) if row["confidence_score"] is not None else None,
        "explanation": str(row["explanation"]) if row["explanation"] else "",
        "flags": [str(item) for item in _json_loads_list(row["flags_json"]) if str(item)],
        "fallback_events": [str(item) for item in _json_loads_list(row["fallback_events_json"]) if str(item)],
        "soft_signal_score": float(row["soft_signal_score"]) if row["soft_signal_score"] is not None else None,
        "soft_signal_flags": [str(item) for item in _json_loads_list(row["soft_signal_flags_json"]) if str(item)],
        "soft_signal_evidence": [str(item) for item in _json_loads_list(row["soft_signal_evidence_json"]) if str(item).strip()],
        "review_required": bool(int(row["review_required"] or 0)),
        "review_state": str(row["review_state"]) if row["review_state"] else "pending",
        "review_decision": str(row["review_decision"]) if row["review_decision"] else None,
        "reviewer_note": str(row["reviewer_note"] or ""),
        "judge_score": float(row["judge_score"]) if row["judge_score"] is not None else None,
        "judge_verdict": str(row["judge_verdict"]) if row["judge_verdict"] else None,
        "consensus_tier": str(row["consensus_tier"]) if row["consensus_tier"] else None,
        "minority_label": str(row["minority_label"]) if row["minority_label"] else None,
        "model_votes": _json_loads_dict(row["model_votes_json"]),
        "drafted_text": str(row["drafted_text"]) if row["drafted_text"] else None,
        "updated_at": int(row["updated_at"] or 0),
    }


def upsert_run_rows(
    *,
    runs_dir: Path,
    run_id: str,
    upload_id: str | None,
    rows: list[dict[str, Any]],
    attempt_id: str | None = None,
) -> int:
    if not rows:
        return 0
    now = _now_ts()
    normalized_row_indices = sorted({int(row.get("row_index") or 0) for row in rows if int(row.get("row_index") or 0) > 0})
    upload_row_map = fetch_upload_rows_by_row_indices(runs_dir=runs_dir, upload_id=upload_id, row_indices=normalized_row_indices) if upload_id else {}
    with _connect(runs_dir) as conn:
        existing_rows = conn.execute(
            f"""
            SELECT run_id, row_index, review_state, review_decision, reviewer_note
            FROM run_rows
            WHERE run_id = ? AND row_index IN ({",".join("?" for _ in normalized_row_indices)})
            """,
            (run_id, *normalized_row_indices),
        ).fetchall() if normalized_row_indices else []
        existing_map = {int(row["row_index"]): dict(row) for row in existing_rows}
        for row in rows:
            row_index = int(row.get("row_index") or 0)
            if row_index <= 0:
                continue
            source_row = upload_row_map.get(row_index, {})
            existing = existing_map.get(row_index, {})
            item_number = str(row.get("item_number") or source_row.get("item_number") or "")
            post_text = str(row.get("post_text") or source_row.get("post_text") or "")
            sequence_index = row.get("sequence_index", source_row.get("sequence_index"))
            review_required = row.get("review_required")
            if review_required is None:
                review_required = "REVIEW_REQUIRED" in {str(flag) for flag in row.get("flags", [])}
            reviewer_note = row.get("reviewer_note")
            if reviewer_note is None:
                reviewer_note = existing.get("reviewer_note") or ""
            review_state = row.get("review_state")
            if review_state is None:
                review_state = existing.get("review_state") or ("pending" if review_required else None)
            review_decision = row.get("review_decision")
            if review_decision is None:
                review_decision = existing.get("review_decision")
            conn.execute(
                """
                INSERT INTO run_rows (
                    run_id, row_index, upload_id, attempt_id, sequence_index, item_number, post_text, row_hash,
                    assigned_category, confidence_score, explanation, flags_json, fallback_events_json,
                    soft_signal_score, soft_signal_flags_json, soft_signal_evidence_json,
                    review_required, review_state, review_decision, reviewer_note,
                    judge_score, judge_verdict, consensus_tier, minority_label, model_votes_json, drafted_text,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, row_index) DO UPDATE SET
                    upload_id=COALESCE(excluded.upload_id, run_rows.upload_id),
                    attempt_id=COALESCE(excluded.attempt_id, run_rows.attempt_id),
                    sequence_index=COALESCE(excluded.sequence_index, run_rows.sequence_index),
                    item_number=COALESCE(NULLIF(excluded.item_number, ''), run_rows.item_number),
                    post_text=COALESCE(NULLIF(excluded.post_text, ''), run_rows.post_text),
                    row_hash=COALESCE(excluded.row_hash, run_rows.row_hash),
                    assigned_category=COALESCE(excluded.assigned_category, run_rows.assigned_category),
                    confidence_score=COALESCE(excluded.confidence_score, run_rows.confidence_score),
                    explanation=COALESCE(excluded.explanation, run_rows.explanation),
                    flags_json=excluded.flags_json,
                    fallback_events_json=excluded.fallback_events_json,
                    soft_signal_score=COALESCE(excluded.soft_signal_score, run_rows.soft_signal_score),
                    soft_signal_flags_json=excluded.soft_signal_flags_json,
                    soft_signal_evidence_json=excluded.soft_signal_evidence_json,
                    review_required=excluded.review_required,
                    review_state=COALESCE(excluded.review_state, run_rows.review_state),
                    review_decision=COALESCE(excluded.review_decision, run_rows.review_decision),
                    reviewer_note=COALESCE(excluded.reviewer_note, run_rows.reviewer_note),
                    judge_score=COALESCE(excluded.judge_score, run_rows.judge_score),
                    judge_verdict=COALESCE(excluded.judge_verdict, run_rows.judge_verdict),
                    consensus_tier=COALESCE(excluded.consensus_tier, run_rows.consensus_tier),
                    minority_label=COALESCE(excluded.minority_label, run_rows.minority_label),
                    model_votes_json=COALESCE(excluded.model_votes_json, run_rows.model_votes_json),
                    drafted_text=COALESCE(excluded.drafted_text, run_rows.drafted_text),
                    updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    row_index,
                    upload_id,
                    attempt_id,
                    int(sequence_index) if sequence_index not in {None, ""} else None,
                    item_number,
                    post_text,
                    str(row.get("row_hash") or source_row.get("row_hash") or "") or None,
                    str(row.get("assigned_category") or "") or None,
                    float(row["confidence_score"]) if row.get("confidence_score") is not None else None,
                    str(row.get("explanation") or "") or None,
                    _json_dumps([str(item) for item in row.get("flags", []) if str(item)]),
                    _json_dumps([str(item) for item in row.get("fallback_events", []) if str(item)]),
                    float(row["soft_signal_score"]) if row.get("soft_signal_score") is not None else None,
                    _json_dumps([str(item) for item in row.get("soft_signal_flags", []) if str(item)]),
                    _json_dumps([str(item).strip() for item in row.get("soft_signal_evidence", []) if str(item).strip()]),
                    1 if review_required else 0,
                    str(review_state) if review_state not in {None, ""} else None,
                    str(review_decision) if review_decision not in {None, ""} else None,
                    str(reviewer_note or ""),
                    float(row["judge_score"]) if row.get("judge_score") is not None else None,
                    str(row.get("judge_verdict") or "") or None,
                    str(row.get("consensus_tier") or "") or None,
                    str(row.get("minority_label") or "") or None,
                    _json_dumps(row.get("model_votes") or {}) if row.get("model_votes") else None,
                    str(row.get("drafted_text") or "") or None,
                    now,
                    now,
                ),
            )
        conn.commit()
    return len(rows)


def fetch_run_rows(*, runs_dir: Path, run_id: str, review_required_only: bool = False) -> list[dict[str, Any]]:
    where = "WHERE run_id = ?"
    params: list[Any] = [run_id]
    if review_required_only:
        where += " AND review_required = 1"
    with _connect(runs_dir) as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM run_rows
            {where}
            ORDER BY row_index ASC
            """,
            params,
        ).fetchall()
    return [_decode_run_row(row) for row in rows]


def fetch_run_row(*, runs_dir: Path, run_id: str, row_index: int) -> dict[str, Any] | None:
    with _connect(runs_dir) as conn:
        row = conn.execute(
            "SELECT * FROM run_rows WHERE run_id = ? AND row_index = ?",
            (run_id, row_index),
        ).fetchone()
    return _decode_run_row(row) if row else None


def summarize_run_rows(
    *,
    runs_dir: Path,
    run_id: str,
    row_index_min: int | None = None,
    row_index_max: int | None = None,
) -> dict[str, Any]:
    where = ["run_id = ?"]
    params: list[Any] = [run_id]
    if row_index_min is not None:
        where.append("row_index >= ?")
        params.append(int(row_index_min))
    if row_index_max is not None:
        where.append("row_index <= ?")
        params.append(int(row_index_max))
    where_clause = " AND ".join(where)

    with _connect(runs_dir) as conn:
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS processed_rows,
                SUM(CASE WHEN assigned_category IS NOT NULL AND assigned_category NOT IN ('', 'Not Antisemitic') THEN 1 ELSE 0 END) AS threat_rows_detected,
                SUM(CASE WHEN review_required = 1 THEN 1 ELSE 0 END) AS review_required_rows_detected,
                SUM(CASE WHEN judge_verdict IS NOT NULL OR judge_score IS NOT NULL THEN 1 ELSE 0 END) AS judged_rows,
                SUM(CASE WHEN
                    flags_json LIKE '%SECOND_PASS_RECHECK%' OR
                    flags_json LIKE '%SECOND_PASS_CONFIRMED%' OR
                    flags_json LIKE '%SECOND_PASS_DISAGREEMENT%' OR
                    flags_json LIKE '%SECOND_PASS_UNAVAILABLE%'
                THEN 1 ELSE 0 END) AS second_pass_candidates,
                SUM(CASE WHEN
                    flags_json LIKE '%SECOND_PASS_CONFIRMED%' OR
                    flags_json LIKE '%SECOND_PASS_DISAGREEMENT%'
                THEN 1 ELSE 0 END) AS second_pass_completed,
                SUM(CASE WHEN flags_json LIKE '%SECOND_PASS_CATEGORY_OVERRIDDEN%' THEN 1 ELSE 0 END) AS second_pass_overrides
            FROM run_rows
            WHERE {where_clause}
            """,
            params,
        ).fetchone()

    return {
        "processed_rows": int((row or {})["processed_rows"] or 0),
        "threat_rows_detected": int((row or {})["threat_rows_detected"] or 0),
        "review_required_rows_detected": int((row or {})["review_required_rows_detected"] or 0),
        "judged_rows": int((row or {})["judged_rows"] or 0),
        "second_pass_candidates": int((row or {})["second_pass_candidates"] or 0),
        "second_pass_completed": int((row or {})["second_pass_completed"] or 0),
        "second_pass_overrides": int((row or {})["second_pass_overrides"] or 0),
    }


def update_run_row_review(
    *,
    runs_dir: Path,
    run_id: str,
    row_index: int,
    review_state: str | None,
    review_decision: str | None,
    reviewer_note: str | None,
) -> None:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        conn.execute(
            """
            UPDATE run_rows
            SET review_state = COALESCE(?, review_state),
                review_decision = COALESCE(?, review_decision),
                reviewer_note = COALESCE(?, reviewer_note),
                updated_at = ?
            WHERE run_id = ? AND row_index = ?
            """,
            (review_state, review_decision, reviewer_note, now, run_id, row_index),
        )
        conn.commit()


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


def resume_run_segments(*, runs_dir: Path, run_id: str) -> int:
    now = _now_ts()
    with _connect(runs_dir) as conn:
        rows = conn.execute(
            """
            SELECT segment_id, row_count, processed_rows, state
            FROM segments
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchall()
        if not rows:
            return 0
        count = 0
        for row in rows:
            if str(row["state"] or "READY") == "COMPLETED":
                continue
            row_count = int(row["row_count"] or 0)
            processed_rows = max(0, min(int(row["processed_rows"] or 0), row_count))
            conn.execute(
                """
                UPDATE segments
                SET state = 'QUEUED',
                    processed_rows = ?,
                    worker_id = NULL,
                    claimed_at = NULL,
                    started_at = CASE WHEN ? > 0 THEN started_at ELSE NULL END,
                    completed_at = NULL,
                    last_error = NULL,
                    updated_at = ?
                WHERE segment_id = ?
                """,
                (processed_rows, processed_rows, now, row["segment_id"]),
            )
            count += 1
        conn.commit()
    return count


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
            resolved_processed_rows = row_count if resolved_state == "COMPLETED" else processed_rows
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


def build_run_segment_summary(*, runs_dir: Path, run_id: str, effective_run_state: str | None = None) -> dict[str, Any]:
    with _connect(runs_dir) as conn:
        segments = conn.execute("SELECT * FROM segments WHERE run_id = ? ORDER BY segment_index ASC", (run_id,)).fetchall()
    status_counts: dict[str, int] = {}
    total_rows = 0
    processed_rows = 0
    review: dict[str, Any] = {"total_segments": len(segments), "processed_rows": 0, "total_rows": 0, "segments_by_status": {}, "active_segment": None}
    for segment in segments:
        status = effective_segment_state_for_run(
            segment_state=str(segment["state"] or "READY"),
            run_state=effective_run_state,
        )
        status_counts[status] = status_counts.get(status, 0) + 1
        row_count = int(segment["row_count"] or 0)
        total_rows += row_count
        processed_rows += min(max(int(segment["processed_rows"] or 0), 0), row_count)
        if status == "PROCESSING" and review["active_segment"] is None:
            review["active_segment"] = dict(segment)
    review["total_rows"] = total_rows
    review["processed_rows"] = processed_rows
    review["segments_by_status"] = status_counts
    review["completed_segments"] = status_counts.get("COMPLETED", 0)
    review["progress_percentage"] = round((processed_rows / total_rows) * 100, 2) if total_rows else 0.0
    review["segment_progress_percentage"] = round((review["completed_segments"] / len(segments)) * 100, 2) if segments else 0.0
    return review


def count_other_runs_for_upload(*, runs_dir: Path, upload_id: str, excluding_run_id: str | None = None) -> int:
    with _connect(runs_dir) as conn:
        if excluding_run_id:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM runs WHERE upload_id = ? AND run_id != ?",
                (upload_id, excluding_run_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM runs WHERE upload_id = ?",
                (upload_id,),
            ).fetchone()
    return int((row or {})["count"] or 0)


def delete_run_snapshot(*, runs_dir: Path, run_id: str) -> None:
    with _connect(runs_dir) as conn:
        conn.execute("DELETE FROM feedback_items WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM events WHERE entity_type = 'run' AND entity_id = ?", (run_id,))
        conn.execute("DELETE FROM run_rows WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM run_attempts WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM segments WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        conn.commit()


def delete_upload_snapshot(*, runs_dir: Path, upload_id: str) -> None:
    with _connect(runs_dir) as conn:
        conn.execute("DELETE FROM feedback_items WHERE run_id IN (SELECT run_id FROM runs WHERE upload_id = ?)", (upload_id,))
        conn.execute("DELETE FROM run_rows WHERE upload_id = ?", (upload_id,))
        conn.execute("DELETE FROM upload_rows WHERE upload_id = ?", (upload_id,))
        conn.execute("DELETE FROM events WHERE entity_type = 'upload' AND entity_id = ?", (upload_id,))
        conn.execute("DELETE FROM segments WHERE upload_id = ?", (upload_id,))
        conn.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
        conn.commit()


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
            min(max(int(segment["processed_rows"] or 0), 0), int(segment["row_count"] or 0))
            for segment in segments
        )
        total_segment_rows = sum(int(segment["row_count"] or 0) for segment in segments)
        resolved_run = _resolved_run_snapshot(runs_dir, str(run["run_id"]), run) if run else None
        canonical_stats = summarize_run_rows(runs_dir=runs_dir, run_id=str(run["run_id"])) if run else {}
        run_processed_rows = _resolved_processed_rows(
            indexed_run=run,
            canonical_stats=canonical_stats,
            segment_summary=(resolved_run or {}).get("segment_summary"),
        )
        effective_processed_rows = max(run_processed_rows, segment_processed_rows)
        row_progress_pct = (
            round((effective_processed_rows / total_segment_rows) * 100, 2)
            if total_segment_rows
            else (resolved_run or {}).get("row_progress_percentage", _row_progress_percentage(run))
        )
        eta_seconds = (resolved_run or {}).get("estimated_remaining_seconds", _estimate_remaining_seconds(run))
        processing_stats = _resolved_processing_stats(
            indexed_run=run,
            processing_stats=_read_processing_stats(runs_dir, str(run["run_id"]) if run else None),
            canonical_stats=canonical_stats,
            processed_rows=effective_processed_rows,
            total_rows=total_segment_rows or ((resolved_run or {}).get("total_rows") if resolved_run else None),
        )
        return {
            "upload_id": upload_id,
            "status": upload["status"],
            "filename": upload["filename"],
            "row_count": upload["row_count"],
            "segment_size": DEFAULT_SEGMENT_SIZE,
            "segment_count": total_segments,
            "segments_by_status": status_counts,
            "progress_percentage": row_progress_pct if run else segment_progress_pct,
            "processed_rows": effective_processed_rows,
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
            processed_rows += int(summary.get("processed_rows") or processing_stats.get("processed_rows") or run.get("processed_rows") or 0)
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
