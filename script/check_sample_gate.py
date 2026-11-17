#!/usr/bin/env python3
"""Score a TEV expert check sample against the current lanes and compare with recorded acceptance criteria.

Go-live tasks 07/08: the first real-data measurement. A check sample is an expert-labelled JSONL with one
record per item:

    {"language": "hu", "country": "HU", "item_id": "...", "text": "...", "label": "Anti-Israel",
     "reason": "...", "labeller": "..."}

Labels use the seven canonical categories. The report computes, per lane and for the trinity, the false-flag
rate (labelled negative, flagged for review), the miss rate (labelled positive, closed without review) and
agreement, then compares them against the acceptance criteria recorded for that locale (if any).

Usage (repo root):
    .venv/bin/python script/check_sample_gate.py --sample <sample.jsonl> \
        [--criteria docs/evaluation/acceptance_criteria_hu.json] [--lanes ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

POSITIVE = {"Anti-Israel", "Anti-Judaism", "Holocaust Denial", "Classical Antisemitism",
            "Structural Antisemitism", "Conspiracy Theories"}
CATEGORIES = POSITIVE | {"Not Antisemitic"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--criteria")
    ap.add_argument("--lanes",
                    default="mlx://mlx-community/Apertus-8B-Instruct-2509-4bit,ollama://qwen2.5:7b,ollama://gemma2:9b")
    ap.add_argument("--out")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.classifier import classify_batch
    from src.lanes import parse_model_spec
    from src.models import InputRow
    from src.ssot_loader import load_ssot

    ssot = load_ssot(Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")
    records = [json.loads(line) for line in Path(args.sample).read_text().splitlines() if line.strip()]
    for record in records:
        if record.get("label") not in CATEGORIES:
            print(f"invalid label {record.get('label')!r} in sample item {record.get('item_id')}", file=sys.stderr)
            return 2
    rows = [InputRow(row_index=i + 1, item_number=str(record.get("item_id")), post_text=record["text"])
            for i, record in enumerate(records)]

    lane_specs = [spec.strip() for spec in args.lanes.split(",") if spec.strip()]
    lane_reports = []
    for spec in lane_specs:
        route = parse_model_spec(spec, "ollama")
        results, _ = classify_batch(rows, ssot, max_workers=1, review_mode="trinity",
                                    model_name=f"{route.backend}://{route.model_name}")
        false_flags = missed = correct = 0
        for record, result in zip(records, results):
            flagged = "REVIEW_REQUIRED" in (result.flags or [])
            positive_label = record["label"] in POSITIVE
            if flagged and not positive_label:
                false_flags += 1
            if not flagged and positive_label:
                missed += 1
            if result.category == record["label"]:
                correct += 1
        lane_reports.append({
            "lane": route.version,
            "items": len(records),
            "agreement": round(correct / len(records), 3),
            "false_flag_rate": round(false_flags / len(records), 3),
            "miss_rate": round(missed / len(records), 3),
        })

    criteria = {}
    if args.criteria and Path(args.criteria).is_file():
        criteria = json.loads(Path(args.criteria).read_text())

    report = {
        "schema": "spot.check-sample-gate.v1",
        "sample": str(Path(args.sample).name),
        "items": len(records),
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lanes": lane_reports,
        "criteria": criteria,
        "passes": all(
            lane["miss_rate"] <= criteria.get("max_miss_rate", 1.0)
            and lane["false_flag_rate"] <= criteria.get("max_false_flag_rate", 1.0)
            for lane in lane_reports
        ) if criteria else None,
    }
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
