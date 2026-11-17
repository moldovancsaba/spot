#!/usr/bin/env python3
"""Weekly operational metrics for the TEV fifth-workday review (go-live task 20).

Reads canonical state and prints the review template with measured values: throughput, processed/error/
review counts, SLA status, audit-sample coverage and handover counts. Fields without a source remain empty
for the joint review to fill.

Usage (repo root):
    .venv/bin/python script/weekly_metrics.py --run-id <run_id> [--db runs/spot_ops.sqlite3] [--runs-dir runs]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--db", default="runs/spot_ops.sqlite3")
    ap.add_argument("--runs-dir", default="runs")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.services.run_state_service import run_sla_status

    db = Path(args.db)
    rows = {}
    if db.exists():
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            (processed, reviewed) = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(review_required),0) FROM run_rows WHERE run_id=?",
                (args.run_id,),
            ).fetchone()
            error_rows = conn.execute(
                "SELECT COUNT(*) FROM run_rows WHERE run_id=? AND flags_json LIKE '%ANALYSIS_FAILED%'",
                (args.run_id,),
            ).fetchone()[0]
            audit_rows = conn.execute(
                "SELECT COUNT(*) FROM run_rows WHERE run_id=? AND flags_json LIKE '%AUDIT_SAMPLE%'",
                (args.run_id,),
            ).fetchone()[0]
            escalated = conn.execute(
                "SELECT COUNT(*) FROM case_escalations WHERE run_id=?", (args.run_id,)
            ).fetchone()[0]
            rows = {"processed": processed, "review_required": reviewed, "error_rows": error_rows,
                    "audit_sampled": audit_rows, "escalated_cases": escalated}
        except sqlite3.OperationalError as exc:
            print(f"db read skipped: {exc}", file=sys.stderr)
        finally:
            conn.close()

    sla = run_sla_status(runs_dir=Path(args.runs_dir), run_id=args.run_id) or {}
    indicators = [
        ("Indicator", "Expected value", "Measured value", "Deviation", "Action", "Owner", "Deadline"),
        ("Rows processed", "", rows.get("processed", ""), "", "", "", ""),
        ("Review-required rows", "", rows.get("review_required", ""), "", "", "", ""),
        ("Error rows", "", rows.get("error_rows", ""), "", "", "", ""),
        ("Audit-sampled rows", "", rows.get("audit_sampled", ""), "", "", "", ""),
        ("Escalated cases", "", rows.get("escalated_cases", ""), "", "", "", ""),
        ("SLA status", "", sla.get("status", ""), "", "", "", ""),
        ("False-flag rate (task 08)", "", "", "", "", "", ""),
        ("Miss rate (task 08)", "", "", "", "", "", ""),
        ("Expert response within 1 business day", "", "", "", "", "", ""),
    ]
    for row in indicators:
        print("\t".join(str(cell) for cell in row))
    print("\nNext review date: ____________")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
