#!/usr/bin/env python3
"""Priority-case notification drill (go-live tasks 15/16).

Builds a FICTIONAL case package so the notification chain (who, in what order, which channel, expected
acknowledgement) can be exercised end-to-end with no real submission. It also writes the escalation record
into the run's case log, so the drill itself is auditable.

Usage (repo root):
    .venv/bin/python script/escalation_drill.py --run-id <run_id> --runs-dir runs --db runs/spot_ops.sqlite3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--db", default="runs/spot_ops.sqlite3")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.services.ops_db_service import upsert_case_escalation

    case = {
        "case_id": f"{args.run_id}:DRILL-{time.strftime('%Y%m%dT%H%M%S')}",
        "source_ref": "FICTIONAL-source-for-drill",
        "snapshot_text": "FICTIONAL snapshot text for the notification drill. No real submission.",
        "known_dates": "FICTIONAL timestamps",
        "context": "FICTIONAL platform and item reference",
        "fact_summary": "Short factual description of the fictional case.",
        "urgency": "high",
        "notification_order": "primary recipient, then deputy (fill per approved task 15 record)",
        "escalated_by": "spot-operator",
        "escalated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    record = upsert_case_escalation(runs_dir=Path(args.runs_dir), run_id=args.run_id,
                                    row_index=-1, fields=case)
    print(json.dumps({
        "drill": True,
        "note": "FICTIONAL case: exercise the notification chain; never submit this to any authority.",
        "case": {key: record.get(key) for key in ("case_id", "urgency", "notification_order",
                                                  "escalated_by", "escalated_at")},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
