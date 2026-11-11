"""Explain exception routing without changing classification evidence or human decisions."""
from __future__ import annotations

import math
from src.excel_io import stable_row_hash
from src.failure_policy import MANDATORY_REVIEW_FLAGS, validated_auto_consensus
from src.models import CANONICAL_CATEGORIES


def recovered_drafter_rejection(row: dict) -> bool:
    flags = set(row.get('flags') or [])
    events = set(row.get('fallback_events') or [])
    source = str(row.get('post_text') or '')
    # Historical drafter rejection returned the original text before classification.
    # Only acknowledge recovery when lineage and the actual classifier input verify it.
    return bool(source.strip() and 'DRAFTER_CONTENT_CHANGED' in flags and 'DRAFTER_OUTPUT_REJECTED' in events
                and row.get('source_row_hash') == stable_row_hash(str(row.get('item_number') or ''), source)
                and ' '.join(str(row.get('drafted_text') or '').split()) == ' '.join(source.split()))


def exception_reasons(row: dict, policy) -> list[str]:
    if validated_auto_consensus(row):
        return []
    flags = set(row.get('flags') or [])
    events = set(row.get('fallback_events') or [])
    if recovered_drafter_rejection(row):
        flags -= {'DRAFTER_CONTENT_CHANGED', 'DRAFTER_FALLBACK'}
        events -= {'DRAFTER_OUTPUT_REJECTED', 'DRAFTER_ROUTE_FALLBACK'}
    reasons = set(flags & MANDATORY_REVIEW_FLAGS)
    reasons.update(events)
    if row.get('assigned_category') not in CANONICAL_CATEGORIES:
        reasons.add('INVALID_CATEGORY')
    if not str(row.get('post_text') or '').strip():
        reasons.add('EMPTY_TEXT')
    try:
        score = float(row.get('confidence_score'))
        if not math.isfinite(score) or not 0 <= score <= 1 or score < policy.low_confidence_threshold:
            reasons.add('LOW_CONFIDENCE')
    except (ValueError, TypeError):
        reasons.add('LOW_CONFIDENCE')
    if row.get('soft_signal_flags') or float(row.get('soft_signal_score') or 0) >= policy.soft_signal_review_threshold or 'SOFT_SIGNAL_REVIEW' in flags:
        reasons.add('SOFT_SIGNAL_REVIEW')
    reasons.update(flags & {'SECOND_PASS_DISAGREEMENT', 'SECOND_PASS_JUDGE_FAIL', 'SECOND_PASS_JUDGE_REVIEW', 'NONSENSICAL_OR_SHORT', 'LOW_CONFIDENCE'})
    if str(row.get('judge_verdict') or '').upper() in {'FAIL', 'REVIEW'}:
        reasons.add('JUDGE_REVIEW')
    return sorted(reasons)
