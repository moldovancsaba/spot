#!/usr/bin/env python3
"""Measure per-lane, per-category precision on a held-out gate and write the calibration table.

A model's self-reported confidence is not calibrated (the adopted adapter emits a fixed 0.9 prior).
Calibration replaces it per lane and category with the lane's measured precision on rows it has never
trained on. The table is versioned and recorded, and routing may then use real confidence.

Usage (repo root):
    SPOT_MLX_ADAPTER_PATH=... .venv/bin/python script/measure_calibration.py \
        --gate runs/learning/train-v2-20261116/gate.jsonl \
        --out models/calibration/calibration-v1.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

CATEGORIES = ["Anti-Israel", "Anti-Judaism", "Holocaust Denial", "Classical Antisemitism",
              "Latent Antisemitism", "Conspiracy Theories", "Not Antisemitic"]


def gate_text(record: dict) -> str:
    user = record["messages"][0]["content"] if record["messages"][0]["role"] == "user" else record["messages"][1]["content"]
    if "SOURCE_POST_JSON: " in user:
        return json.loads(user.split("SOURCE_POST_JSON: ", 1)[1])
    return user


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lanes", default="mlx://mlx-community/Apertus-8B-Instruct-2509-4bit,ollama://qwen2.5:7b,ollama://gemma2:9b")
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

    lanes = []
    for spec in args.lanes.split(","):
        route = parse_model_spec(spec.strip(), "ollama")
        lanes.append((route.backend, route.model_name, route.version))

    outcomes = {version: collections.defaultdict(lambda: collections.Counter()) for _, _, version in lanes}
    binary = {version: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for _, _, version in lanes}

    for index, record in enumerate(records, 1):
        gold = json.loads(record["messages"][-1]["content"])["category"]
        text = gate_text(record)
        for backend, model_name, version in lanes:
            try:
                result = _classify_with_backend(text, ssot, backend=backend, model_name=model_name)
                predicted = result.category
            except Exception as exc:
                predicted = f"<{type(exc).__name__}>"
            outcomes[version][gold][predicted] += 1
            gold_pos = gold != "Not Antisemitic"
            pred_pos = predicted not in ("Not Antisemitic",) and not predicted.startswith("<")
            if gold_pos and pred_pos:
                binary[version]["tp"] += 1
            elif gold_pos and not pred_pos:
                binary[version]["fn"] += 1
            elif pred_pos and not gold_pos:
                binary[version]["fp"] += 1
            else:
                binary[version]["tn"] += 1
        if index % 10 == 0:
            print(f"  {index}/{len(records)}", file=sys.stderr, flush=True)

    table: dict = {"schema": "spot.calibration.v1", "measured_rows": len(records),
                   "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "lanes": {}}
    for backend, model_name, version in lanes:
        lane: dict = {"binary": {}}
        tp, fp, fn, tn = (binary[version]["tp"], binary[version]["fp"], binary[version]["fn"], binary[version]["tn"])
        lane["binary"]["precision"] = round(tp / (tp + fp), 3) if tp + fp else 0.0
        lane["binary"]["recall"] = round(tp / (tp + fn), 3) if tp + fn else 0.0
        for category in CATEGORIES:
            counts = outcomes[version].get(category, {})
            total = sum(counts.values())
            correct = counts.get(category, 0)
            lane[category] = round(correct / total, 3) if total else None
        table["lanes"][version] = lane

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, indent=2))
    print(json.dumps(table, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
