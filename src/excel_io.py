from __future__ import annotations

from pathlib import Path
from typing import List, Set

from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from .models import ClassificationResult, InputRow, SSOT


class InputFileError(RuntimeError):
    pass


MAX_INPUT_FILE_BYTES = 25 * 1024 * 1024
MAX_INPUT_ROWS = 50000
MAX_POST_TEXT_LENGTH = 10000


ADDED_COLUMNS = [
    "Raw Category",
    "Assigned Category",
    "Consensus Tier",
    "Minority Report",
    "Model Votes",
    "Fallback Events",
    "Judge Score",
    "Judge Verdict",
    "Confidence Score",
    "Soft Signal Score",
    "Soft Signal Flags",
    "Soft Signal Evidence",
    "Explanation / Reasoning",
    "Flags",
    "Model Version",
    "Prompt Version",
    "Taxonomy Version",
    "SSOT Version",
    "Pipeline Version",
    "Run ID",
    "Run Language",
    "Review Mode",
    "Review Required",
    "Row Hash",
]


def read_input_rows(path: Path, ssot: SSOT) -> List[InputRow]:
    if path.suffix.lower() != ".xlsx":
        raise InputFileError("Input must be .xlsx")
    if path.stat().st_size > MAX_INPUT_FILE_BYTES:
        raise InputFileError(
            f"Input workbook is too large. Maximum supported size is {MAX_INPUT_FILE_BYTES // (1024 * 1024)} MiB."
        )

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise InputFileError(
            f"Corrupted/invalid workbook: {exc}. Expected a valid .xlsx with columns: {ssot.policy.expected_columns}"
        ) from exc

    ws = wb[wb.sheetnames[0]]
    rows_iter = ws.iter_rows(min_row=1, max_row=1, values_only=True)
    header = next(rows_iter, None)
    if not header:
        raise InputFileError("Input worksheet is empty. Expected header row.")

    header_values = [str(v).strip() if v is not None else "" for v in header]
    expected = ssot.policy.expected_columns
    if header_values[: len(expected)] != expected:
        raise InputFileError(
            f"Invalid schema. Expected first columns {expected}; got {header_values[:len(expected)]}. Fix input schema to match the sample format."
        )

    try:
        _min_col, _min_row, _max_col, max_row = range_boundaries(ws.calculate_dimension())
    except Exception:
        max_row = ws.max_row

    rows: List[InputRow] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, max_row=max_row, values_only=True), start=2):
        item_number = "" if row[0] is None else str(row[0]).strip()
        post_text = "" if row[1] is None else str(row[1]).strip()
        category = "" if len(row) < 3 or row[2] is None else str(row[2]).strip()
        if item_number == "" and post_text == "" and category == "":
            continue
        if len(post_text) > MAX_POST_TEXT_LENGTH:
            raise InputFileError(
                f"Input row {idx} exceeds the maximum supported post text length of {MAX_POST_TEXT_LENGTH} characters."
            )
        if "\x00" in post_text:
            raise InputFileError(f"Input row {idx} contains invalid null-byte content.")
        rows.append(InputRow(row_index=idx, item_number=item_number, post_text=post_text))
        if len(rows) > MAX_INPUT_ROWS:
            raise InputFileError(f"Input workbook exceeds the maximum supported row count of {MAX_INPUT_ROWS}.")

    if not rows:
        raise InputFileError("Input worksheet has no data rows.")

    return rows


def write_output(
    input_path: Path,
    output_path: Path,
    ssot: SSOT,
    run_id: str,
    run_language: str,
    review_mode: str,
    pipeline_version: str,
    results: List[ClassificationResult],
    row_hashes: List[str],
) -> None:
    wb = load_workbook(input_path)
    ws = wb[wb.sheetnames[0]]

    start_col = ws.max_column + 1
    for offset, col_name in enumerate(ADDED_COLUMNS):
        ws.cell(row=1, column=start_col + offset, value=col_name)

    for i, result in enumerate(results, start=2):
        if not result.category:
            result.category = "Not Antisemitic"
            result.flags = sorted(set(result.flags + ["EMPTY_CATEGORY_RECOVERED"]))
        review_required = "YES" if "REVIEW_REQUIRED" in result.flags else "NO"
        values = [
            result.raw_category,
            result.category,
            result.consensus_tier,
            result.minority_label,
            "" if not result.model_votes else ";".join(f"{k}:{v}" for k, v in sorted(result.model_votes.items())),
            "" if not result.fallback_events else ";".join(sorted(set(result.fallback_events))),
            result.judge_score,
            result.judge_verdict,
            round(result.confidence, 4),
            "" if result.soft_signal_score is None else round(result.soft_signal_score, 4),
            "" if not result.soft_signal_flags else ";".join(sorted(set(result.soft_signal_flags))),
            "" if not result.soft_signal_evidence else " | ".join(result.soft_signal_evidence),
            result.explanation,
            ";".join(sorted(set(result.flags))),
            result.resolved_model_version or ssot.policy.model_version,
            ssot.policy.prompt_version,
            ssot.taxonomy.version,
            ssot.ssot_version,
            pipeline_version,
            run_id,
            run_language,
            review_mode,
            review_required,
            row_hashes[i - 2],
        ]
        write_row = result.row_index if result.row_index > 1 else i
        for offset, value in enumerate(values):
            ws.cell(row=write_row, column=start_col + offset, value=value)

    wb.save(output_path)


def validate_no_null_assigned_category(output_path: Path, expected_rows: List[int]) -> None:
    wb = load_workbook(output_path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    header = [str(v).strip() if v is not None else "" for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    try:
        category_col_idx = header.index("Assigned Category") + 1
    except ValueError as exc:
        raise InputFileError("Output validation failed: 'Assigned Category' column missing") from exc

    null_rows: List[int] = []
    for row_idx in expected_rows:
        val = ws.cell(row=row_idx, column=category_col_idx).value
        if val is None or str(val).strip() == "":
            null_rows.append(row_idx)

    if null_rows:
        sample = null_rows[:10]
        raise InputFileError(
            f"Output validation failed: null Assigned Category in {len(null_rows)} rows. Sample rows: {sample}"
        )


def extract_assigned_categories(output_path: Path, expected_rows: List[int]) -> Set[str]:
    wb = load_workbook(output_path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    header = [str(v).strip() if v is not None else "" for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    try:
        category_col_idx = header.index("Assigned Category") + 1
    except ValueError as exc:
        raise InputFileError("Output validation failed: 'Assigned Category' column missing") from exc

    values: Set[str] = set()
    for row_idx in expected_rows:
        val = ws.cell(row=row_idx, column=category_col_idx).value
        if val is None:
            continue
        txt = str(val).strip()
        if txt:
            values.add(txt)
    return values
