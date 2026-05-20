from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .excel_io import (
    InputFileError,
    build_row_manifest_entries,
    build_stored_row_entries,
    canonicalize_xlsx_input_rows,
    read_input_rows,
    summarize_canonical_input_rows,
)
from .models import CanonicalInputRow, SSOT


FIRST_WORKSHEET_SENTINEL = "__first_worksheet__"


@dataclass(frozen=True)
class ImportedBatch:
    source_type: str
    source_name: str
    source_sheet: str
    canonical_rows: list[CanonicalInputRow]
    validation_summary: dict
    row_manifest_entries: list[dict]
    stored_row_entries: list[dict]


def import_input_file(path: Path, ssot: SSOT) -> ImportedBatch:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _import_xlsx(path, ssot)
    raise InputFileError(f"Unsupported input type '{suffix or '(none)'}'.")


def _import_xlsx(path: Path, ssot: SSOT) -> ImportedBatch:
    rows = read_input_rows(path, ssot)
    source_name = path.name
    source_sheet = FIRST_WORKSHEET_SENTINEL
    canonical_rows = canonicalize_xlsx_input_rows(rows, source_name=source_name, source_sheet=source_sheet)
    validation_summary = {
        "accepted": True,
        "row_count": len(canonical_rows),
        **summarize_canonical_input_rows(canonical_rows),
    }
    return ImportedBatch(
        source_type="xlsx",
        source_name=source_name,
        source_sheet=source_sheet,
        canonical_rows=canonical_rows,
        validation_summary=validation_summary,
        row_manifest_entries=build_row_manifest_entries(rows, source_name=source_name, source_sheet=source_sheet),
        stored_row_entries=build_stored_row_entries(rows, source_name=source_name, source_sheet=source_sheet),
    )
