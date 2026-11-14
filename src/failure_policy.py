"""Shared safety gates for inference, review and downstream consumers."""

ANALYSIS_FAILURE_FLAGS = frozenset({
    "ANALYSIS_FAILED", "CATEGORY_MISSING", "TAXONOMY_VIOLATION",
    "MODEL_REQUEST_FAILED", "CLASSIFIER_FALLBACK_FAILED", "EMPTY_TEXT", "SKIPPED",
})
MANDATORY_REVIEW_FLAGS = ANALYSIS_FAILURE_FLAGS | frozenset({
    "AMBIGUOUS", "MISSING_CONTEXT", "UNCLEAR_CONTEXT", "CLASSIFIER_FALLBACK", "UNSTRUCTURED_MODEL_OUTPUT", "DRAFTER_UNAVAILABLE",
    "UNGROUNDED_MODEL_SIGNAL", "DRAFTER_FALLBACK", "SECOND_PASS_UNAVAILABLE", "JUDGE_UNAVAILABLE",
    "SECOND_PASS_CATEGORY_OVERRIDDEN", "DRAFTER_CONTENT_CHANGED", "INVALID_MODEL_METADATA",
})


def requires_safety_review(flags, fallback_events=None) -> bool:
    return bool(set(flags or []) & MANDATORY_REVIEW_FLAGS or fallback_events)


# Flags that make a row ineligible for certificate-based review clearance. A soft antisemitism signal is
# evidence of problematic content; clearing it without a human defeats the purpose of detecting it.
CERTIFICATE_BLOCKING_FLAGS = frozenset({"SOFT_SIGNAL_REVIEW"})

def certificate_clearance_disabled() -> bool:
    """True when the operator has turned off certificate-based review clearance.

    SPOT_DISABLE_AUTO_CLEAR=1 is the safest posture: every row reaches a human, no row is ever cleared
    by model agreement alone. It exists because the independent-consensus certificate rests on two
    models; where both share a blind spot, their agreement is not evidence.
    """
    import os

    return os.getenv("SPOT_DISABLE_AUTO_CLEAR", "0").strip().lower() in {"1", "true", "yes", "on"}


ANY_POSITIVE_REVIEW_THRESHOLD = 0.30
ANY_POSITIVE_REVIEW_FLAG = "ANY_POSITIVE_ANALYSIS"


def any_positive_analysis(result, threshold: float = ANY_POSITIVE_REVIEW_THRESHOLD) -> bool:
    """True when any analysis branch assigned a positive category at or above the threshold.

    Safety routing consequence: a row that ANY model called antisemitic must be reviewed by a human,
    even when the aggregate/final label is `Not Antisemitic`. Measured on 300 rows, rows carrying no
    review flag contained 53% missed positives and 60% of all false negatives, so the aggregate label
    alone is not a trustworthy clearance.
    """
    import math

    from .models import CANONICAL_CATEGORIES

    positives = set(CANONICAL_CATEGORIES) - {"Not Antisemitic"}

    def as_positive(entry) -> bool:
        if not isinstance(entry, dict):
            return False
        if entry.get("category") not in positives:
            return False
        try:
            score = float(entry.get("confidence"))
        except (TypeError, ValueError):
            return False
        return math.isfinite(score) and score >= threshold

    trace = getattr(result, "audit_trace", None) or {}
    branches = [trace.get("initial"), trace.get("alternate")]
    for entry in list(branches):
        attempts = entry.get("attempts") if isinstance(entry, dict) else None
        if isinstance(attempts, dict):
            branches.append(attempts.get("initial_response"))
            branches.append(attempts.get("retry_response"))
    branches.append({"category": getattr(result, "category", None), "confidence": getattr(result, "confidence", None)})
    return any(as_positive(entry) for entry in branches)


def review_policy_mode() -> str:
    """How aggressively rows are routed to human review.

    all        - every row requires review (maximum recall, maximum workload)
    certificate- clear only with a complete independent-consensus proof (the strict precedent)
    suspicious - clear a row only when nothing about it is suspicious (default)

    SPOT_DISABLE_AUTO_CLEAR=1 forces `all`, so the safest posture remains reachable with one switch.
    """
    import os

    if os.getenv("SPOT_DISABLE_AUTO_CLEAR", "0").strip().lower() in {"1", "true", "yes", "on"}:
        return "all"
    mode = os.getenv("SPOT_REVIEW_POLICY", "suspicious").strip().lower()
    return mode if mode in {"all", "certificate", "suspicious"} else "suspicious"


def audit_sample_percent() -> int:
    """Percentage of otherwise-cleared rows that are still routed to review.

    This is the recall safety net: a cleared row is never visible to a human, so a deterministic sample of
    cleared rows keeps the miss rate measurable and feeds labelled negatives back into learning.
    """
    import os

    try:
        value = int(os.getenv("SPOT_AUDIT_SAMPLE_PCT", "10") or "0")
    except ValueError:
        return 0
    return max(0, min(value, 100))


def audit_sampled(*, source_sha256: str | None, row_index: int) -> bool:
    """Deterministic audit selection, stable across reruns of the same row."""
    pct = audit_sample_percent()
    if pct <= 0 or not source_sha256:
        return False
    import hashlib

    digest = hashlib.sha256(f"{source_sha256}:{row_index}".encode()).hexdigest()
    return int(digest[:8], 16) % 100 < pct


def enforce_result_safety(result):
    from .models import CANONICAL_CATEGORIES

    flags = set(result.flags or [])
    if result.category not in CANONICAL_CATEGORIES:
        result.category = "Not Antisemitic"
        flags.update({"TAXONOMY_VIOLATION", "ANALYSIS_FAILED"})
    if flags & ANALYSIS_FAILURE_FLAGS:
        flags.add("ANALYSIS_FAILED")
        result.confidence = 0.0
    mode = review_policy_mode()
    suspicious = requires_safety_review(flags, result.fallback_events) or any_positive_analysis(result)
    certificate = mode != "all" and validated_auto_consensus(result)

    if mode == "all":
        flags.add("REVIEW_REQUIRED")
    elif suspicious:
        # Any suspicion outranks model agreement: a negative aggregate is not evidence of a clean row.
        flags.add("REVIEW_REQUIRED")
        if any_positive_analysis(result):
            flags.add(ANY_POSITIVE_REVIEW_FLAG)
    elif mode == "certificate" and not certificate:
        flags.add("REVIEW_REQUIRED")
    else:
        # Nothing suspicious and (in certificate mode) a complete proof: the row may clear, but a
        # deterministic audit sample still reaches a human so misses stay measurable.
        trace = getattr(result, "audit_trace", None) or {}
        source_key = trace.get("source_sha256")
        if source_key is None:
            # The trace is not always attached when safety runs; the drafted text is stable per row, so it
            # still gives a deterministic, reproducible sample.
            import hashlib as _hashlib

            drafted = getattr(result, "drafted_text", None) or ""
            source_key = _hashlib.sha256(drafted.encode()).hexdigest() if drafted else None
        if audit_sampled(source_sha256=source_key, row_index=getattr(result, "row_index", 0)):
            flags.add("REVIEW_REQUIRED")
            flags.add("AUDIT_SAMPLE")
    result.flags = sorted(flags)
    return result


def validated_auto_consensus(value) -> bool:
    """A marker alone never authorizes bypassing review; verify the complete stored proof."""
    import math
    import hashlib
    from .models import CANONICAL_CATEGORIES
    get = value.get if isinstance(value, dict) else lambda key, default=None: getattr(value, key, default)
    flags = set(get('flags') or [])
    trace = get('audit_trace') or {}
    if certificate_clearance_disabled():
        return False
    if 'AUTO_RESOLVED_CONSENSUS' not in flags or trace.get('automatic_resolution',{}).get('policy') != 'independent-consensus-v1':
        return False
    if flags & MANDATORY_REVIEW_FLAGS or set(get('fallback_events') or []) - {'SECOND_PASS_ALT_ROUTE'}:
        return False
    if flags & CERTIFICATE_BLOCKING_FLAGS:
        return False
    first, second = trace.get('initial') or {}, trace.get('alternate') or {}
    category = get('assigned_category') or get('category')
    if not trace.get('judge_model') or trace['judge_model'] in {first.get('model'),second.get('model')}:
        return False
    if category not in CANONICAL_CATEGORIES or not first.get('model') or not second.get('model') or first['model'] == second['model']:
        return False
    source = ' '.join(str(get('post_text') or get('drafted_text') or '').split()).lower()
    original_source = ' '.join(str(get('post_text') or get('drafted_text') or '').split())
    if not source or trace.get('source_sha256') != hashlib.sha256(original_source.encode()).hexdigest():
        return False
    try:
        for branch in (first,second):
            score = float(branch['confidence'])
            if branch.get('category') != category or not math.isfinite(score) or score < .85 or score > 1 or set(branch.get('flags') or []) & MANDATORY_REVIEW_FLAGS or branch.get('fallback_events'):
                return False
            if category != 'Not Antisemitic' and not any(' '.join(str(q).split()).lower() in source and str(q).strip() for q in branch.get('soft_signal_evidence') or []):
                return False
        confidence = float(get('confidence_score') if get('confidence_score') is not None else get('confidence'))
        judge = float(get('judge_score'))
        if not math.isfinite(confidence) or not .85 <= confidence <= min(first['confidence'],second['confidence']):
            return False
        return get('judge_verdict') == trace.get('judge_verdict') == 'PASS' and math.isfinite(judge) and .85 <= judge <= 1 and judge == trace.get('judge_score') and not trace.get('judge_flags')
    except (ValueError,TypeError,KeyError):
        return False
