#!/usr/bin/env python3
"""Per-language model bakeoff: evaluate a candidate lane model on a held-out gate and write a promotion record.

Owner decision D7: the trinity lane models are never final. A candidate is promoted only on measured gate
improvement over the incumbent, and every promotion names its predecessor as the rollback path.

Usage (repo root):
    SPOT_MLX_ADAPTER_PATH=... .venv/bin/python script/model_bakeoff.py \\
        --language de --lane primary \\
        --candidate ollama://qwen2.5:7b --incumbent ollama://gemma2:9b \\
        --gate runs/learning/train-v2-20261116/gate.jsonl \\
        --incumbent-eval models/registry/incumbent-eval.json [--promote]

Promotion records append to models/registry/promotions.jsonl (schema spot.promotion.v1).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def write_promotion(*, registry: Path, language: str, lane: str, candidate: str, incumbent: str | None,
                    country: str = "",
                    candidate_metrics: dict, incumbent_metrics: dict, promote: bool = False,
                    baseline: bool = False) -> dict:
    delta = {
        key: round(candidate_metrics.get(key, 0) - incumbent_metrics.get(key, 0), 4)
        for key in ("six_way_agreement_pct", "six_way_macro_f1", "binary_f1", "binary_recall")
        if key in candidate_metrics and key in incumbent_metrics
    }
    record = {
        "schema": "spot.promotion.v1",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "language": language,
        "country": country,
        "lane": lane,
        "candidate": candidate,
        "incumbent": incumbent,
        "candidate_metrics": candidate_metrics,
        "incumbent_metrics": incumbent_metrics,
        "delta": delta,
        "decision": "baseline" if baseline else ("promote" if promote else "rejected"),
        "rollback": incumbent,
    }
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", required=True)
    ap.add_argument("--country", default="")
    ap.add_argument("--lane", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--incumbent", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--incumbent-eval")
    ap.add_argument("--registry", default="models/registry/promotions.jsonl")
    ap.add_argument("--promote", action="store_true", help="record decision=promote; default rejects")
    ap.add_argument("--baseline", action="store_true", help="record the measured starting point of a lane (D7)")
    ap.add_argument("--skip-scoring", action="store_true", help="only write the record from --incumbent-eval and a provided --candidate-eval")
    ap.add_argument("--candidate-eval")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import importlib.util

    if not args.skip_scoring:
        spec = importlib.util.spec_from_file_location(
            "evaluate_adapter", str(Path(__file__).resolve().parents[1] / "script" / "evaluate_adapter.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"scoring candidate {args.candidate} on {args.gate}", file=sys.stderr)
        candidate_metrics = module.run_split(args.candidate, None, Path(args.gate), 0, 48)
    else:
        candidate_metrics = json.loads(Path(args.candidate_eval).read_text()) if args.candidate_eval else {}

    incumbent_metrics = {}
    if args.incumbent_eval:
        incumbent_metrics = json.loads(Path(args.incumbent_eval).read_text())

    record = write_promotion(
        registry=Path(args.registry), language=args.language, lane=args.lane,
        candidate=args.candidate, incumbent=args.incumbent or None,
        country=args.country,
        candidate_metrics=candidate_metrics, incumbent_metrics=incumbent_metrics,
        promote=args.promote, baseline=args.baseline,
    )
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
