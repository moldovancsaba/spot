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


def enforce_result_safety(result):
    from .models import CANONICAL_CATEGORIES

    flags = set(result.flags or [])
    if result.category not in CANONICAL_CATEGORIES:
        result.category = "Not Antisemitic"
        flags.update({"TAXONOMY_VIOLATION", "ANALYSIS_FAILED"})
    if flags & ANALYSIS_FAILURE_FLAGS:
        flags.add("ANALYSIS_FAILED")
        result.confidence = 0.0
    if requires_safety_review(flags, result.fallback_events) and not validated_auto_consensus(result):
        flags.add("REVIEW_REQUIRED")
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
    if 'AUTO_RESOLVED_CONSENSUS' not in flags or trace.get('automatic_resolution',{}).get('policy') != 'independent-consensus-v1':
        return False
    if flags & MANDATORY_REVIEW_FLAGS or set(get('fallback_events') or []) - {'SECOND_PASS_ALT_ROUTE'}:
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
