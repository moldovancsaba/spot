from __future__ import annotations

import json
import re
import time
from pathlib import Path

from backend.services.ops_db_service import build_upload_queue_summary, record_upload, replace_upload_rows
from src.excel_io import InputFileError, MAX_INPUT_ROWS, MAX_POST_TEXT_LENGTH, write_row_manifest
from src.intake_adapters import import_input_file
from src.ssot_loader import SSOTError, load_ssot


UPLOADS_DIRNAME = "uploads"


def uploads_dir(runs_dir: Path) -> Path:
    path = runs_dir / UPLOADS_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_dir(runs_dir: Path, upload_id: str) -> Path:
    path = uploads_dir(runs_dir) / upload_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_record_path(runs_dir: Path, upload_id: str) -> Path:
    return upload_dir(runs_dir, upload_id) / "upload.json"


def intake_workbook(
    *,
    runs_dir: Path,
    ssot_path: Path,
    upload_id: str,
    filename: str,
    content: bytes,
) -> dict:
    safe_name = _sanitize_filename(filename)
    intake_dir = upload_dir(runs_dir, upload_id)
    workbook_path = intake_dir / safe_name
    workbook_path.write_bytes(content)

    record = {
        "upload_id": upload_id,
        "filename": safe_name,
        "stored_path": str(workbook_path),
        "bytes": len(content),
        "status": "accepted",
        "created_at": int(time.time()),
        "validation": {},
    }

    try:
        ssot = load_ssot(ssot_path)
        batch = import_input_file(workbook_path, ssot)
        row_manifest_path = intake_dir / "row_manifest.jsonl"
        write_row_manifest(row_manifest_path, batch.row_manifest_entries)
        record["validation"] = {
            "accepted": True,
            "row_count": len(batch.canonical_rows),
            "expected_columns": ssot.policy.expected_columns,
            "max_input_rows": MAX_INPUT_ROWS,
            "max_post_text_length": MAX_POST_TEXT_LENGTH,
            "row_manifest_path": str(row_manifest_path),
            **batch.validation_summary,
        }
    except (InputFileError, SSOTError) as exc:
        record["status"] = "rejected"
        record["validation"] = {
            "accepted": False,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        record["status"] = "rejected"
        record["validation"] = {
            "accepted": False,
            "error_type": exc.__class__.__name__,
            "message": f"Unexpected intake validation failure: {exc}",
        }

    upload_record_path(runs_dir, upload_id).write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    record["queue_summary"] = record_upload(runs_dir=runs_dir, record=record)
    if record["status"] == "accepted":
        replace_upload_rows(runs_dir=runs_dir, upload_id=upload_id, rows=batch.stored_row_entries)
    return record


def read_upload_record(*, runs_dir: Path, upload_id: str) -> dict | None:
    path = upload_record_path(runs_dir, upload_id)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(record, dict):
            record["queue_summary"] = build_upload_queue_summary(runs_dir=runs_dir, upload_id=upload_id)
        return record
    except Exception:
        return None


def ensure_upload_rows_materialized(
    *,
    runs_dir: Path,
    ssot_path: Path,
    upload_id: str,
    fallback_input_path: Path | None = None,
) -> int:
    record = read_upload_record(runs_dir=runs_dir, upload_id=upload_id)
    if not record:
        raise FileNotFoundError(f"Upload record {upload_id} was not found.")
    if str(record.get("status") or "").lower() != "accepted":
        raise RuntimeError(f"Upload {upload_id} is not accepted and cannot be materialized.")

    candidate_paths: list[Path] = []
    stored_path = record.get("stored_path")
    if stored_path:
        candidate_paths.append(Path(str(stored_path)))
    if fallback_input_path is not None:
        candidate_paths.append(Path(fallback_input_path))

    workbook_path = next((path for path in candidate_paths if path.exists()), None)
    if workbook_path is None:
        searched = ", ".join(str(path) for path in candidate_paths) or "(none)"
        raise FileNotFoundError(f"Could not locate source workbook for upload {upload_id}. Checked: {searched}")

    ssot = load_ssot(ssot_path)
    batch = import_input_file(workbook_path, ssot)
    row_manifest_path = upload_dir(runs_dir, upload_id) / "row_manifest.jsonl"
    write_row_manifest(row_manifest_path, batch.row_manifest_entries)
    replace_upload_rows(runs_dir=runs_dir, upload_id=upload_id, rows=batch.stored_row_entries)

    validation = record.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    validation.update(
        {
            "accepted": True,
            "row_count": len(batch.canonical_rows),
            "expected_columns": ssot.policy.expected_columns,
            "max_input_rows": MAX_INPUT_ROWS,
            "max_post_text_length": MAX_POST_TEXT_LENGTH,
            "row_manifest_path": str(row_manifest_path),
            **batch.validation_summary,
        }
    )
    record["validation"] = validation
    record["stored_path"] = str(workbook_path)
    upload_record_path(runs_dir, upload_id).write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(batch.canonical_rows)


def list_upload_records(*, runs_dir: Path) -> list[dict]:
    root = uploads_dir(runs_dir)
    uploads: list[dict] = []
    for child in sorted(root.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        record = read_upload_record(runs_dir=runs_dir, upload_id=child.name)
        if record:
            uploads.append(record)
    return uploads


def _sanitize_filename(filename: str) -> str:
    candidate = Path(filename or "upload.xlsx").name
    candidate = re.sub(r"[\x00-\x1f\x7f/\\\\:*?\"<>|]+", "_", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" ._")
    if not candidate:
        candidate = "upload.xlsx"
    if not candidate.lower().endswith(".xlsx"):
        candidate = f"{candidate}.xlsx"
    return candidate
