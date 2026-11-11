#!/usr/bin/env python3
"""Build an MLX LoRA training set from the accepted {spot} reference.

The reference (`docs/evaluation/goldset_2026-11-11.jsonl`) stores labels plus text hashes, not post text,
so this script regenerates the sample from the approved workbook and the recorded seed, joins on hash, and
emits chat-format JSONL that `mlx_lm lora` can train on.

Usage (from the repo root):
    .venv/bin/python script/build_training_set.py \
        --out runs/learning/train-<date> --valid-fraction 0.2 --seed 20261111

Output: `train.jsonl`, `valid.jsonl`, `test.jsonl` and `manifest.json` (splits, hashes, class support).
Nothing is written outside --out.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

CATEGORIES = [
    "Anti-Israel",
    "Anti-Judaism",
    "Classical Antisemitism",
    "Structural Antisemitism",
    "Conspiracy Theories",
    "Not Antisemitic",
]

SYSTEM_PROMPT = """You classify the author's expressed position in a social-media post, in its original language.
Return one JSON object with exactly one category from: Anti-Israel, Anti-Judaism, Classical Antisemitism, Structural Antisemitism, Conspiracy Theories, Not Antisemitic.

Step 1. Is the author expressing an antisemitic position at all? Ordinary criticism of a government, army, war or
policy (including Israeli policy), news reporting, quotation of someone else's view, condemnation of antisemitism,
counterspeech, or a post without enough context is `Not Antisemitic`.

Step 2. If antisemitic, apply the FIRST rule that matches:
1. Holocaust denial or minimization, Nazi praise, an anti-Jewish slur, or a racial/genetic claim -> Classical Antisemitism
2. A claim of secret or coded Jewish control, manipulation, or collective plotting -> Conspiracy Theories
3. Antisemitic hostility carried BY an Israel/Zionism framing itself -> Anti-Israel
4. A claim that Jews systematically control, exclude others from, or receive unequal treatment within institutions
   or society, with no Israel/Zionism framing and no secret-plot claim -> Structural Antisemitism
5. Hostility directed at the Jewish religion or Jewish religious identity itself -> Anti-Judaism

Boundaries: mentioning Israel or Zionism does not make a post Anti-Israel; hostility must be carried by that framing.
"Jews run the banks/media/economy" with no Israel reference and no plot claim is Structural."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def regenerate_sample(workbook: Path, out_dir: Path, per_category: int, seed: int) -> Path:
    """Recreate the stratified sample from the approved workbook so post text never has to be committed."""
    subprocess.run(
        [sys.executable, "script/build_gold_sample.py",
         "--source", str(workbook), "--out", str(out_dir),
         "--per-category", str(per_category), "--seed", str(seed)],
        check=True, capture_output=True, text=True,
    )
    return out_dir


def read_workbook_rows(path: Path) -> dict[str, dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows: dict[str, dict] = {}
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if len(row) < 2 or not isinstance(row[1], str) or not row[1].strip():
            continue
        text = row[1].strip()
        rows[sha(text)] = {"row_index": idx, "item_number": str(row[0]), "post_text": text}
    wb.close()
    return rows


def chat_record(text: str, label: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"SOURCE_POST_JSON: {json.dumps(text, ensure_ascii=False)}"},
            {"role": "assistant", "content": json.dumps({"category": label}, ensure_ascii=False)},
        ]
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", default="docs/evaluation/goldset_2026-11-11.jsonl")
    ap.add_argument("--workbook", default="samples/sample_germany.xlsx")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-category", type=int, default=50)
    ap.add_argument("--sample-seed", type=int, default=20261110)
    ap.add_argument("--seed", type=int, default=20261111, help="split seed")
    ap.add_argument("--valid-fraction", type=float, default=0.2)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reference = {}
    for line in Path(args.reference).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            reference[row["text_sha256"]] = row["label"]

    with tempfile.TemporaryDirectory() as td:
        regenerate_sample(Path(args.workbook), Path(td) / "sample", args.per_category, args.sample_seed)
        texts = {}
        for line in (Path(td) / "sample" / "sample_texts.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                texts[row["text_sha256"]] = {"post_text": row["post_text"]}

    joined = []
    for h, meta in texts.items():
        label = reference.get(h)
        if label:
            joined.append({"hash": h, "text": meta["post_text"], "label": label})
    if not joined:
        print("no rows joined the reference; check the seed and workbook", file=sys.stderr)
        return 2

    joined.sort(key=lambda r: r["hash"])
    rng = random.Random(args.seed)
    rng.shuffle(joined)
    n_valid = max(1, int(len(joined) * args.valid_fraction))
    valid, rest = joined[:n_valid], joined[n_valid:]
    n_test = max(1, int(len(rest) * args.valid_fraction))
    test, train = rest[:n_test], rest[n_test:]

    def write(name: str, rows: list[dict]) -> None:
        with (out / name).open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(chat_record(row["text"], row["label"]), ensure_ascii=False) + "\n")

    write("train.jsonl", train)
    write("valid.jsonl", valid)
    write("test.jsonl", test)

    import collections

    manifest = {
        "reference": args.reference,
        "workbook": args.workbook,
        "split_seed": args.seed,
        "rows_total": len(joined),
        "splits": {"train": len(train), "valid": len(valid), "test": len(test)},
        "class_support": dict(collections.Counter(r["label"] for r in joined)),
        "note": "Rows join the accepted reference on sha256 of the normalised post text. No post text is committed.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
