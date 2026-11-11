#!/usr/bin/env python3
"""Deterministically rebuild the {spot} gold-set sample texts.

The accepted reference stores labels with sha256 hashes only, so post text is never committed. This script
reproduces exactly the sampling the reference was built from, letting any maintainer regenerate the texts
and verify the hashes match.

Usage:
    .venv/bin/python script/build_gold_sample.py --out /tmp/gold-sample --per-category 50 --seed 20261110
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

CATEGORIES = ["Anti-Israel", "Anti-Judaism", "Classical Antisemitism",
              "Structural Antisemitism", "Conspiracy Theories", "Not Antisemitic"]
ALIAS = {
    "anti israel": "Anti-Israel", "anti israeli": "Anti-Israel",
    "anti judaism": "Anti-Judaism",
    "classical antisemitism": "Classical Antisemitism", "holocaust denial": "Classical Antisemitism",
    "structural antisemitism": "Structural Antisemitism",
    "conspiracy theories": "Conspiracy Theories", "conspiracy theory": "Conspiracy Theories",
    "not antisemitic": "Not Antisemitic", "not antisemetic": "Not Antisemitic",
}


def normalise(value) -> str | None:
    if not isinstance(value, str):
        return None
    key = re.sub(r"\s+", " ", value.strip().lower().replace("-", " ").replace("_", " "))
    if key in ALIAS:
        return ALIAS[key]
    for category in CATEGORIES:
        if re.sub(r"\s+", " ", category.lower()) == key:
            return category
    return None


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="samples/sample_germany.xlsx")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-category", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261110)
    args = ap.parse_args()

    import openpyxl

    wb = openpyxl.load_workbook(args.source, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    buckets: dict[str, list[dict]] = {category: [] for category in CATEGORIES}
    seen: set[str] = set()
    for index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if len(row) < 3:
            continue
        item, text, raw = row[0], row[1], row[2]
        if not isinstance(text, str) or not text.strip():
            continue
        label = normalise(raw)
        if label is None:
            continue
        text = text.strip()
        digest = sha(text)
        if digest in seen:
            continue
        seen.add(digest)
        buckets[label].append({"source_row": index, "item_number": str(item), "post_text": text,
                               "text_sha256": digest, "source_label": label})
    wb.close()

    rng = random.Random(args.seed)
    sample: list[dict] = []
    for category in CATEGORIES:
        pool = buckets[category]
        rng.shuffle(pool)
        sample.extend(pool[: args.per_category])
    rng.shuffle(sample)
    for number, row in enumerate(sample, start=1):
        row["sample_id"] = f"S{number:04d}"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "sample_texts.jsonl").open("w", encoding="utf-8") as fh:
        for row in sample:
            fh.write(json.dumps({"sample_id": row["sample_id"], "text_sha256": row["text_sha256"],
                                 "post_text": row["post_text"]}, ensure_ascii=False) + "\n")
    print(json.dumps({"rows": len(sample), "out": str(out / "sample_texts.jsonl")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
