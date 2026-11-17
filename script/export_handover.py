#!/usr/bin/env python3
"""Generate the TEV handover workbook for a run.

Deck p.10: the review package carries, per row - source or snapshot, relevant context, proposed category,
a short rationale and the open question - plus the run summary, with the machine result and expert decision
tracked separately. The workbook is regenerated deterministically from canonical rows and accompanied by an
integrity manifest.

Usage (repo root):
    .venv/bin/python script/export_handover.py --run-id <run_id> [--db runs/spot_ops.sqlite3] [--out runs/<run_id>/handover.xlsx]

The output contains:
  - Summary sheet: run identity, totals, category mix, review state mix.
  - Review sheet: rows requiring review, ordered by review priority, with the deck's handover fields.
  - <out>.manifest.json: sha256 of the workbook, row count, generated timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

HEADERS = ["Case ID", "Run ID", "Row Index", "Item Number", "Source / Snapshot", "Context",
           "Proposed Category", "Secondary Category", "Short Rationale", "Open Question",
           "Review State", "Expert Decision", "Reviewer Note", "Machine Flags", "Row Hash"]

POSITIVE = {"Anti-Israel", "Anti-Judaism", "Holocaust Denial", "Classical Antisemitism",
            "Structural Antisemitism", "Conspiracy Theories"}


def open_question(flags: list[str], category: str, judge_verdict: str | None) -> str:
    flags = set(flags or [])
    if "TRINITY_DISAGREEMENT" in flags:
        return "Evaluator lanes disagreed after the justification round; expert decision required."
    if "MISSING_CONTEXT" in flags:
        return "Context insufficient for a confident category; expert reading required."
    if "SOFT_SIGNAL_REVIEW" in flags:
        return "Soft antisemitism signals present; expert confirmation required."
    if str(judge_verdict or "").upper() in {"REVIEW", "FAIL"}:
        return f"Judge returned {judge_verdict}; expert decision required."
    if "AUDIT_SAMPLE" in flags:
        return "Random audit sample of a closed row; verify the machine verdict."
    if category in POSITIVE:
        return "Positive finding; expert confirmation required."
    return ""


def build_workbook(rows: list[dict], run_id: str, out: Path, run_summary: dict | None = None) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    summary.append(["Run ID", run_id])
    summary.append(["Generated", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())])
    summary.append(["Review rows", len(rows)])
    if not rows:
        summary.append(["Notice", "Zero findings: no rows required human review for this batch."])
    run_summary = run_summary or {}
    summary.append(["Processed rows", run_summary.get("processed_rows", "")])
    summary.append(["Error rows", run_summary.get("error_rows", "")])
    summary.append(["Review required", run_summary.get("review_required", len(rows))])
    summary.append(["Language", run_summary.get("language", "")])
    summary.append(["Country", run_summary.get("country", "")])
    import collections

    category_mix = collections.Counter(str(row.get("assigned_category") or "") for row in rows)
    state_mix = collections.Counter(str(row.get("review_state") or "pending") for row in rows)
    summary.append(["Category mix", json.dumps(dict(category_mix), ensure_ascii=False)])
    summary.append(["Review state mix", json.dumps(dict(state_mix), ensure_ascii=False)])
    summary.append(["Field guide", "Source / Snapshot: post text; Context: item number and source row; "
                                   "Proposed Category: machine verdict; Short Rationale: model explanation; "
                                   "Open Question: what the expert must decide."])

    sheet = wb.create_sheet("Review")
    for header in HEADERS:
        sheet.cell(row=1, column=HEADERS.index(header) + 1, value=header).font = Font(bold=True)
    for row in rows:
        flags = row.get("flags") or []
        sheet.append([
            row.get("case_id") or f"{run_id}:{row.get('row_index')}",
            run_id,
            row.get("row_index"),
            row.get("item_number"),
            str(row.get("post_text") or "")[:8000],
            f"item {row.get('item_number')} / source row {row.get('source_row_index')}",
            row.get("assigned_category"),
            row.get("secondary_category"),
            str(row.get("explanation") or "")[:700],
            open_question(flags, str(row.get("assigned_category") or ""), row.get("judge_verdict")),
            row.get("review_state") or "pending",
            row.get("review_decision"),
            row.get("reviewer_note"),
            ",".join(sorted(flags)),
            row.get("row_hash"),
        ])
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {"workbook": str(out), "sha256": digest, "rows": len(rows),
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    Path(str(out) + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--db", default="runs/spot_ops.sqlite3")
    ap.add_argument("--out")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from backend.services.run_state_service import _review_priority
    except ImportError:
        _review_priority = lambda row: (0, float(row.get("confidence_score") or 0), -int(row.get("row_index") or 0))

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    columns = {row[1] for row in conn.execute("PRAGMA table_info(run_rows)").fetchall()}
    secondary_expr = "secondary_category" if "secondary_category" in columns else "NULL AS secondary_category"
    cursor = conn.execute(
        f"""SELECT run_id, row_index, upload_id, item_number, post_text, row_hash, source_row_index,
                  assigned_category, {secondary_expr}, confidence_score, explanation, flags_json,
                  review_required, review_state, review_decision, reviewer_note, judge_verdict
           FROM run_rows WHERE run_id = ? AND review_required = 1""",
        (args.run_id,),
    )
    rows = []
    for db_row in cursor.fetchall():
        row = dict(db_row)
        try:
            row["flags"] = json.loads(row.get("flags_json") or "[]")
        except json.JSONDecodeError:
            row["flags"] = []
        rows.append(row)
    conn.close()
    if not rows:
        # A zero-findings day is a result, not a failure (deck p.4 task 04: record the zero-findings signal).
        out = Path(args.out) if args.out else Path("runs") / args.run_id / "handover.xlsx"
        manifest = build_workbook([], args.run_id, out)
        print(json.dumps({**manifest, "zero_findings": True}, indent=2))
        return 0

    rows.sort(key=_review_priority, reverse=True)
    out = Path(args.out) if args.out else Path("runs") / args.run_id / "handover.xlsx"
    manifest = build_workbook(rows, args.run_id, out)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
