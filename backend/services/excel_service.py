from __future__ import annotations

import json
import re
import time
from pathlib import Path

from src.excel_io import InputFileError, read_input_rows
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
        rows = read_input_rows(workbook_path, ssot)
        record["validation"] = {
            "accepted": True,
            "row_count": len(rows),
            "expected_columns": ssot.policy.expected_columns,
            "max_post_text_length": 10000,
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
    return record


def read_upload_record(*, runs_dir: Path, upload_id: str) -> dict | None:
    path = upload_record_path(runs_dir, upload_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._")
    if not candidate:
        candidate = "upload.xlsx"
    if not candidate.lower().endswith(".xlsx"):
        candidate = f"{candidate}.xlsx"
    return candidate
