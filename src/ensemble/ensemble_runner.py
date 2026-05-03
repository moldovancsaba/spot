from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Callable, Dict, List, Tuple

from ..classifier import classify_row, run_judge, stable_row_hash
from ..lanes import parse_model_spec
from ..models import ClassificationResult, InputRow, RunPolicy, SSOT
from .consensus import resolve_consensus


def _merge_flags(*flag_lists: List[str]) -> List[str]:
    merged: set[str] = set()
    for flag_list in flag_lists:
        merged.update(flag_list)
    return sorted(merged)


def run_ensemble_batch(
    rows: List[InputRow],
    ssot: SSOT,
    review_mode: str,
    max_workers: int,
    run_policy: RunPolicy,
    progress_callback: Callable[[int, int], None] | None = None,
    progress_every: int = 100,
) -> Tuple[List[ClassificationResult], List[str], Dict[str, Dict[str, int]], Dict[str, int], Dict[str, int]]:
    row_hashes = [stable_row_hash(r.item_number, r.post_text) for r in rows]
    resolved_versions = {
        model_spec: parse_model_spec(model_spec, "ollama").version for model_spec in run_policy.ensemble_models
    }
    per_model_distribution: Dict[str, Counter] = {version: Counter() for version in resolved_versions.values()}
    consensus_distribution: Counter = Counter()
    consensus_tiers: Counter = Counter()
    stats_lock = Lock()

    def classify_one(row: InputRow) -> ClassificationResult:
        model_results: List[ClassificationResult] = []
        vote_map: Dict[str, str] = {}
        for model_spec in run_policy.ensemble_models:
            model_version = resolved_versions[model_spec]
            mr = classify_row(row=row, ssot=ssot, review_mode=review_mode, model_name=model_spec)
            model_results.append(mr)
            vote_map[model_version] = mr.category
            with stats_lock:
                per_model_distribution[model_version][mr.category] += 1

        final_category, consensus_tier, consensus_flags, votes = resolve_consensus(
            [m.category for m in model_results], run_policy
        )
        with stats_lock:
            consensus_distribution[final_category] += 1
            consensus_tiers[consensus_tier] += 1

        minority_label = None
        if consensus_tier in {"MEDIUM", "LOW"}:
            minority_candidates = [label for label, count in votes.items() if label != final_category and count > 0]
            if minority_candidates:
                minority_label = ",".join(sorted(minority_candidates))

        base = model_results[0]
        soft_signal_score = max((result.soft_signal_score or 0.0) for result in model_results)
        soft_signal_flags = sorted(
            {
                flag
                for result in model_results
                for flag in (result.soft_signal_flags or [])
            }
        )
        soft_signal_evidence = list(
            dict.fromkeys(
                evidence
                for result in model_results
                for evidence in (result.soft_signal_evidence or [])
            )
        )[:3]
        merged_flags = _merge_flags(base.flags, consensus_flags, [f"CONSENSUS_{consensus_tier}"])
        judge_score = None
        judge_verdict = None
        judge_flags: List[str] = []
        fallback_events = list(base.fallback_events or [])
        if consensus_tier in {"MEDIUM", "LOW"}:
            judge_score, judge_verdict, judge_flags = run_judge(
                text=row.post_text,
                category=final_category,
                flags=merged_flags,
            )
            if "JUDGE_FALLBACK" in judge_flags:
                fallback_events.append("JUDGE_ROUTE_FALLBACK")
            if "JUDGE_UNAVAILABLE" in judge_flags:
                fallback_events.append("JUDGE_UNAVAILABLE")
        # Keep earlier flags and append judge flags; never replace existing flags.
        merged_flags = _merge_flags(merged_flags, judge_flags)
        return ClassificationResult(
            row_index=row.row_index,
            raw_category=base.raw_category,
            category=final_category,
            confidence=base.confidence,
            explanation=base.explanation,
            flags=merged_flags,
            soft_signal_score=soft_signal_score,
            soft_signal_flags=soft_signal_flags,
            soft_signal_evidence=soft_signal_evidence,
            resolved_model_version=base.resolved_model_version,
            model_votes=vote_map,
            consensus_tier=consensus_tier,
            minority_label=minority_label,
            judge_score=judge_score,
            judge_verdict=judge_verdict,
            fallback_events=sorted(set(fallback_events)),
        )

    total = len(rows)
    results: List[ClassificationResult] = [None] * total  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {pool.submit(classify_one, row): idx for idx, row in enumerate(rows)}
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
            completed += 1
            if progress_callback and (completed % progress_every == 0 or completed == total):
                progress_callback(completed, total)

    return (
        results,
        row_hashes,
        {k: dict(v) for k, v in per_model_distribution.items()},
        dict(consensus_distribution),
        dict(consensus_tiers),
    )
