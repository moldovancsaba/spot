#!/usr/bin/env python3
"""Measure review-routing economics for a candidate model configuration.

The product requirement is recall-first: find antisemitic rows and put them in front of a human. But every
row that is auto-cleared is a row a human never sees, and every row forced to review is human workload.
This tool runs a labelled gate through the REAL pipeline (including the independent verifier and judge) and
reports the tradeoff:

  * review rate       - fraction of rows a human must look at
  * cleared positive  - antisemitic rows that no human would ever see (the recall cost of clearing)
  * effective recall  - positives still surfaced to a human
  * precision of the  - among rows the pipeline presents as positive findings

It does not change any state; it only reads the gate and reports.

Usage (repo root):
    .venv/bin/python script/measure_routing.py --gate runs/learning/train-schema-20261112/gate.jsonl
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

POSITIVE = {"Anti-Israel", "Anti-Judaism", "Classical Antisemitism", "Structural Antisemitism", "Conspiracy Theories"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--review-mode", default="partial")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.classifier import classify_row
    from src.models import InputRow
    from src.ssot_loader import load_ssot

    ssot = load_ssot(Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")
    print(f"auto-clear disabled: {os.getenv('SPOT_DISABLE_AUTO_CLEAR', '0')}", file=sys.stderr)

    records = [json.loads(line) for line in Path(args.gate).read_text().splitlines() if line.strip()]
    if args.limit:
        records = records[: args.limit]

    rows = []
    for index, record in enumerate(records, start=1):
        messages = record["messages"]
        gold = json.loads(messages[-1]["content"])["category"]
        # The gate is stored in pipeline-prompt form: the user message IS the classifier prompt.
        prompt = messages[0]["content"] if messages[0]["role"] == "user" else messages[1]["content"]
        text = prompt.split("SOURCE_POST_JSON: ", 1)[1] if "SOURCE_POST_JSON: " in prompt else prompt
        try:
            text = json.loads(text)
        except json.JSONDecodeError:
            pass
        result = classify_row(InputRow(row_index=index, item_number=str(index), post_text=str(text)),
                              ssot, args.review_mode)
        flags = set(result.flags or [])
        rows.append({
            "gold": gold,
            "predicted": result.category,
            "confidence": result.confidence,
            "review_required": bool(flags & {"REVIEW_REQUIRED", "ANALYSIS_FAILED", "ANY_POSITIVE_ANALYSIS"}),
            "auto_cleared": "REVIEW_REQUIRED" not in flags and "ANALYSIS_FAILED" not in flags,
            "flags": sorted(flags),
        })
        if index % 10 == 0:
            print(f"  {index}/{len(records)}", file=sys.stderr, flush=True)

    positives = [r for r in rows if r["gold"] in POSITIVE]
    cleared = [r for r in rows if r["auto_cleared"]]
    cleared_positives = [r for r in cleared if r["gold"] in POSITIVE]
    reviewed = [r for r in rows if r["review_required"]]
    surfaced_positives = [r for r in reviewed if r["gold"] in POSITIVE]
    flagged_positive = [r for r in rows if r["predicted"] in POSITIVE]

    report = {
        "gate_rows": len(rows),
        "positives": len(positives),
        "review_rate_pct": round(100 * len(reviewed) / len(rows), 2),
        "cleared_rows": len(cleared),
        "cleared_positives": len(cleared_positives),
        "cleared_miss_rate_pct": round(100 * len(cleared_positives) / len(positives), 2) if positives else 0.0,
        "effective_recall_pct": round(100 * len(surfaced_positives) / len(positives), 2) if positives else 0.0,
        "positive_findings": len(flagged_positive),
        "positive_findings_precision": round(
            sum(1 for r in flagged_positive if r["gold"] in POSITIVE) / len(flagged_positive), 3
        ) if flagged_positive else 0.0,
        "cleared_flag_mix": dict(collections.Counter(f for r in cleared for f in r["flags"]).most_common(6)),
        "rows": rows,
    }
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
