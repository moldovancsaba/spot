#!/usr/bin/env python3
"""Measure candidate lane models (small resident candidates vs current lanes) on the held-out gate.

The gate is the arbiter for any lane swap: a smaller model may only replace a larger one on measured,
recorded performance - never on a memory argument alone.

Usage (repo root):
    .venv/bin/python script/measure_lanes.py --gate runs/learning/train-v2-20261116/gate.jsonl \
        --lanes "ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.2:3b,ollama://gemma2:2b,ollama://gemma3:1b"
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

POSITIVE = {"Anti-Israel", "Anti-Judaism", "Holocaust Denial", "Classical Antisemitism",
            "Structural Antisemitism", "Conspiracy Theories"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--lanes", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.classifier import _classify_with_backend
    from src.lanes import parse_model_spec
    from src.ssot_loader import load_ssot

    ssot = load_ssot(Path(__file__).resolve().parents[1] / "ssot" / "ssot.json")
    records = [json.loads(line) for line in Path(args.gate).read_text().splitlines() if line.strip()]
    if args.limit:
        records = records[: args.limit]

    def gate_text(record: dict) -> str:
        user = record["messages"][0]["content"] if record["messages"][0]["role"] == "user" else record["messages"][1]["content"]
        if "SOURCE_POST_JSON: " in user:
            return json.loads(user.split("SOURCE_POST_JSON: ", 1)[1])
        return user

    report = {"gate_rows": len(records)}
    for spec in [lane.strip() for lane in args.lanes.split(",") if lane.strip()]:
        route = parse_model_spec(spec, "ollama")
        correct = tp = fp = fn = tn = 0
        for index, record in enumerate(records, 1):
            gold = json.loads(record["messages"][-1]["content"])["category"]
            try:
                result = _classify_with_backend(gate_text(record), ssot, backend=route.backend,
                                                model_name=route.model_name)
                predicted = result.category
            except Exception as exc:
                predicted = f"<{type(exc).__name__}>"
            if predicted == gold:
                correct += 1
            gold_pos, pred_pos = gold in POSITIVE, predicted in POSITIVE
            tp += gold_pos and pred_pos
            fp += pred_pos and not gold_pos
            fn += gold_pos and not pred_pos
            tn += (not gold_pos) and (not pred_pos)
            if index % 25 == 0:
                print(f"  {route.version}: {index}/{len(records)}", file=sys.stderr, flush=True)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[route.version] = {
            "agreement": round(correct / len(records), 3),
            "binary_precision": round(precision, 3),
            "binary_recall": round(recall, 3),
            "binary_f1": round(f1, 3),
        }
        print(json.dumps({route.version: report[route.version]}), file=sys.stderr, flush=True)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
