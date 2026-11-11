#!/usr/bin/env python3
"""Score candidate classification outputs against the accepted {spot} reference.

The reference is `docs/evaluation/goldset_2026-11-11.jsonl` — an owner-accepted, provisional,
NOT human-adjudicated label set. Rows are joined by `text_sha256`, so post text is never stored in git.

Usage (from the repo root):
    .venv/bin/python script/score_reference.py --pred runs/foo.jsonl [more.jsonl ...]

Candidate JSONL rows must contain `text_sha256` and `predicted`.
Exit code 0 on success; 2 if no rows joined.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

CATEGORIES = [
    "Anti-Israel",
    "Anti-Judaism",
    "Classical Antisemitism",
    "Structural Antisemitism",
    "Conspiracy Theories",
    "Not Antisemitic",
]
POSITIVE = set(CATEGORIES[:-1])
DEFAULT_REFERENCE = "docs/evaluation/goldset_2026-11-11.jsonl"


def load_reference(path: Path) -> dict[str, dict]:
    ref: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ref[row["text_sha256"]] = row
    return ref


def macro_f1(pairs: list[tuple[str, str]]) -> tuple[float, dict]:
    tp = collections.Counter()
    fp = collections.Counter()
    fn = collections.Counter()
    for gold, predicted in pairs:
        if predicted == gold:
            tp[gold] += 1
        else:
            fn[gold] += 1
            if predicted:
                fp[predicted] += 1
    per_class = {}
    for category in CATEGORIES:
        precision = tp[category] / (tp[category] + fp[category]) if tp[category] + fp[category] else 0.0
        recall = tp[category] / (tp[category] + fn[category]) if tp[category] + fn[category] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[category] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp[category] + fn[category],
        }
    macro = sum(entry["f1"] for entry in per_class.values()) / len(per_class)
    return round(macro, 4), per_class


def binary_metrics(pairs: list[tuple[str, str]]) -> dict:
    tp = fp = fn = tn = 0
    for gold, predicted in pairs:
        gold_pos, pred_pos = gold in POSITIVE, predicted in POSITIVE
        tp += gold_pos and pred_pos
        fp += (not gold_pos) and pred_pos
        fn += gold_pos and (not pred_pos)
        tn += (not gold_pos) and (not pred_pos)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def score(reference: dict[str, dict], candidate: Path) -> dict | None:
    pairs: list[tuple[str, str]] = []
    unmatched = 0
    for line in candidate.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ref = reference.get(row.get("text_sha256"))
        if ref is None:
            unmatched += 1
            continue
        predicted = row.get("predicted")
        if predicted is None:
            continue
        pairs.append((ref["label"], predicted))
    if not pairs:
        return None
    macro, per_class = macro_f1(pairs)
    agreement = sum(1 for gold, predicted in pairs if gold == predicted) / len(pairs)
    return {
        "candidate": candidate.name,
        "rows_scored": len(pairs),
        "rows_unmatched": unmatched,
        "six_way_agreement_pct": round(100 * agreement, 2),
        "six_way_macro_f1": macro,
        "binary": binary_metrics(pairs),
        "per_class": per_class,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", default=DEFAULT_REFERENCE)
    ap.add_argument("--pred", nargs="+", required=True)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = ap.parse_args()

    reference = load_reference(Path(args.reference))
    results = [r for r in (score(reference, Path(p)) for p in args.pred) if r]
    if not results:
        print("no candidate rows joined the reference", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"reference": args.reference, "results": results}, indent=2))
        return 0

    print(f"reference: {args.reference}  ({len(reference)} labelled rows)")
    print(f"{'candidate':34}{'n':>5}{'6way%':>7}{'macroF1':>9}{'binP':>7}{'binR':>7}{'binF1':>7}")
    for r in results:
        b = r["binary"]
        print(f"{r['candidate'][:33]:34}{r['rows_scored']:>5}{r['six_way_agreement_pct']:>7}"
              f"{r['six_way_macro_f1']:>9}{b['precision']:>7}{b['recall']:>7}{b['f1']:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
