#!/usr/bin/env python3
"""Evaluate a base MLX model and/or a LoRA adapter against a held-out split.

This is the learning-loop measurement: does the adapter actually classify better than the base model on
rows it has never seen? Without this, "the system learns" is an assertion rather than a result.

Usage (from the repo root):
    .venv/bin/python script/evaluate_adapter.py \
        --model /path/to/mlx-model --split runs/learning/train-20261111/test.jsonl \
        --adapter runs/learning/adapters-20261111 --out runs/learning/eval-adapter.json

Each split line is a chat record whose assistant content is the reference label.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

POSITIVE = {"Anti-Israel", "Anti-Judaism", "Classical Antisemitism", "Structural Antisemitism", "Conspiracy Theories"}
CATEGORIES = sorted(POSITIVE | {"Not Antisemitic"})


def parse_category(text: str) -> str | None:
    match = re.search(r"\{.*?\}", text, re.S)
    if match:
        try:
            value = json.loads(match.group(0)).get("category")
            if value in CATEGORIES:
                return value
        except json.JSONDecodeError:
            pass
    for category in sorted(CATEGORIES, key=len, reverse=True):
        if category.lower() in text.lower():
            return category
    return None


def metrics(pairs: list[tuple[str, str | None]]) -> dict:
    scored = [(gold, predicted) for gold, predicted in pairs if predicted in CATEGORIES]
    if not scored:
        return {"rows": len(pairs), "scored": 0}
    agreement = sum(1 for gold, predicted in scored if gold == predicted) / len(scored)
    tp = fp = fn = 0
    for gold, predicted in scored:
        gold_pos, pred_pos = gold in POSITIVE, predicted in POSITIVE
        tp += gold_pos and pred_pos
        fp += (not gold_pos) and pred_pos
        fn += gold_pos and (not pred_pos)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    per_class = {}
    for category in CATEGORIES:
        support = sum(1 for gold, _ in scored if gold == category)
        correct = sum(1 for gold, predicted in scored if gold == category and predicted == category)
        predicted_n = sum(1 for _, predicted in scored if predicted == category)
        precision_c = correct / predicted_n if predicted_n else 0.0
        recall_c = correct / support if support else 0.0
        f1_c = 2 * precision_c * recall_c / (precision_c + recall_c) if precision_c + recall_c else 0.0
        per_class[category] = {"f1": round(f1_c, 3), "support": support}
    present = [v for v in per_class.values() if v["support"]]
    macro = sum(v["f1"] for v in present) / len(present) if present else 0.0
    return {
        "rows": len(pairs),
        "scored": len(scored),
        "unparsed": len(pairs) - len(scored),
        "six_way_agreement_pct": round(100 * agreement, 2),
        "six_way_macro_f1": round(macro, 4),
        "binary": {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)},
        "per_class": per_class,
    }


def run_split(model_path: str, adapter: str | None, split: Path, limit: int, max_tokens: int) -> dict:
    from mlx_lm import generate, load

    model, tokenizer = load(model_path, adapter_path=adapter) if adapter else load(model_path)
    pairs: list[tuple[str, str | None]] = []
    rows = [json.loads(line) for line in split.read_text().splitlines() if line.strip()][:limit]
    for index, record in enumerate(rows, 1):
        messages = record["messages"]
        gold = json.loads(messages[-1]["content"])["category"]
        prompt = tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=False)
        output = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
        pairs.append((gold, parse_category(output)))
        if index % 10 == 0:
            print(f"    {index}/{len(rows)}", file=sys.stderr, flush=True)
    return metrics(pairs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--adapter")
    ap.add_argument("--skip-base", action="store_true", help="Evaluate only the adapter (base numbers already known)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=48)
    ap.add_argument("--out")
    args = ap.parse_args()

    split = Path(args.split)
    rows = sum(1 for line in split.read_text().splitlines() if line.strip())
    limit = args.limit or rows

    result = {"split": str(split), "rows": limit}
    baseline = None
    if args.skip_base:
        result["base"] = "skipped"
    else:
        print(f"base model: {args.model}", file=sys.stderr)
        baseline = run_split(args.model, None, split, limit, args.max_tokens)
        result["base"] = baseline

    if args.adapter:
        print(f"adapter: {args.adapter}", file=sys.stderr)
        tuned = run_split(args.model, args.adapter, split, limit, args.max_tokens)
        result["adapter"] = tuned
        if baseline:
            result["delta"] = {
                "six_way_agreement_pct": round(tuned["six_way_agreement_pct"] - baseline["six_way_agreement_pct"], 2),
                "six_way_macro_f1": round(tuned["six_way_macro_f1"] - baseline["six_way_macro_f1"], 4),
                "binary_f1": round(tuned["binary"]["f1"] - baseline["binary"]["f1"], 3),
                "binary_recall": round(tuned["binary"]["recall"] - baseline["binary"]["recall"], 3),
            }

    print(json.dumps(result, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
