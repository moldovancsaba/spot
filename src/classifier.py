from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

from .models import CANONICAL_CATEGORIES, ClassificationResult, InputRow, SSOT
from .defaults import DEFAULT_ALLOW_REMOTE_OLLAMA, DEFAULT_OLLAMA_URL
from .lanes import format_model_version, load_lane_config, parse_model_spec


OLLAMA_URL = DEFAULT_OLLAMA_URL
OLLAMA_SEED = int(os.getenv("OLLAMA_SEED", "42"))
OLLAMA_TIMEOUT_SEC = int(os.getenv("OLLAMA_TIMEOUT_SEC", "20"))
OLLAMA_TEMPERATURE = 0
OLLAMA_TOP_P = 1
LANES = load_lane_config()
MAX_SOFT_SIGNAL_EVIDENCE = 3
SOFT_SIGNAL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "SOFT_SIGNAL_DUAL_LOYALTY": [
        re.compile(r"\bdual loyalty\b", re.IGNORECASE),
        re.compile(r"\bmore loyal to israel\b", re.IGNORECASE),
        re.compile(r"\bloyal to israel (?:than|over)\b", re.IGNORECASE),
        re.compile(r"\bnot loyal to (?:this|our) countr", re.IGNORECASE),
        re.compile(r"\bforeign allegiance\b", re.IGNORECASE),
    ],
    "SOFT_SIGNAL_COLLECTIVE_BLAME": [
        re.compile(r"\ball jews?\b", re.IGNORECASE),
        re.compile(r"\bthe jews?\s+(?:are|were|have|control|own|run|cause|caused|did)\b", re.IGNORECASE),
        re.compile(r"\bjews?\s+(?:control|own|run|caused|caused this|are responsible)\b", re.IGNORECASE),
        re.compile(r"\bjewish people\s+(?:are|were)?\s*responsible\b", re.IGNORECASE),
    ],
    "SOFT_SIGNAL_CODED_CONSPIRACY": [
        re.compile(r"\brothschilds?\b", re.IGNORECASE),
        re.compile(r"\bzionist occupied government\b", re.IGNORECASE),
        re.compile(r"\bjewish lobby\b", re.IGNORECASE),
        re.compile(r"\bglobalists?\s+(?:control|run|own|are behind)\b", re.IGNORECASE),
        re.compile(r"\bcabal\b", re.IGNORECASE),
    ],
    "SOFT_SIGNAL_DOGWHISTLE": [
        re.compile(r"\(\(\(.+?\)\)\)"),
        re.compile(r"\bholohoax\b", re.IGNORECASE),
        re.compile(r"\bzio\b", re.IGNORECASE),
        re.compile(r"\bkhazar(?:ian)?\b", re.IGNORECASE),
    ],
    "SOFT_SIGNAL_HOLOCAUST_MINIMIZATION": [
        re.compile(r"\b6 million (?:lie|myth)\b", re.IGNORECASE),
        re.compile(r"\bso[- ]called holocaust\b", re.IGNORECASE),
        re.compile(r"\bholocaust (?:was )?(?:exaggerated|inflated|overstated)\b", re.IGNORECASE),
        re.compile(r"\bholocaust denial\b", re.IGNORECASE),
    ],
}


def stable_row_hash(item_number: str, post_text: str) -> str:
    payload = json.dumps({"item_number": item_number, "post_text": post_text}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_inference_parameters(model_name: str | None = None, backend: str | None = None) -> dict:
    return {
        "backend": backend or LANES.classifier_backend,
        "model_name": model_name or LANES.classifier_model,
        "model_version": format_model_version(backend or LANES.classifier_backend, model_name or LANES.classifier_model),
        "temperature": OLLAMA_TEMPERATURE,
        "top_p": OLLAMA_TOP_P,
        "seed": OLLAMA_SEED,
        "stream": False,
        "format": "json",
        "timeout_sec": OLLAMA_TIMEOUT_SEC,
        "sampling_enabled": False,
    }


def strip_reasoning_artifacts(text: str) -> str:
    # Remove chain-of-thought style tags before parsing/returning.
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"</?analysis>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def sanitize_explanation(text: str) -> str:
    cleaned = strip_reasoning_artifacts(text)
    leakage_markers = [
        "Return exactly one JSON object",
        "Allowed categories:",
        "Required keys:",
        "Post text:",
        "You are a strict single-label classifier",
        "You are an internal drafter",
        "You are a strict quality judge",
    ]
    if any(marker.lower() in cleaned.lower() for marker in leakage_markers):
        return "Explanation redacted by SPOT policy because model output included internal prompt or control text."
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:700]


def _build_prompt(text: str, categories: List[str], fallback: str, soft_signal_flags: List[str]) -> str:
    cats = json.dumps(categories, ensure_ascii=False)
    soft_flags = json.dumps(sorted(set(soft_signal_flags)), ensure_ascii=False)
    return (
        "You are a strict single-label classifier for antisemitism taxonomy. "
        "Preprocess text internally before classification: normalize whitespace, remove non-semantic noise, and handle typos. "
        "Return exactly one JSON object and no other text. "
        "Required keys: category, confidence, explanation, flags, soft_signal_score, soft_signal_flags, soft_signal_evidence. "
        f"Allowed categories: {cats}. "
        f"Allowed soft_signal_flags: {soft_flags}. "
        f"If uncertain or no clear evidence, use fallback '{fallback}'. "
        "For empty or missing text, set fallback, include EMPTY_TEXT and SKIPPED flags. "
        "For very short or nonsensical text, include NONSENSICAL_OR_SHORT flag. "
        "confidence must be float [0,1]. flags must be array of uppercase tokens. "
        "soft_signal_score must be float [0,1]. soft_signal_flags must be an array of allowed tokens only. "
        "soft_signal_evidence must be an array of exact short quoted phrases from the post text that justify each soft signal. "
        "If no soft antisemitic signal is present, use soft_signal_score 0, soft_signal_flags [], soft_signal_evidence [].\n"
        f"Post text:\n{text}"
    )


def _build_drafter_prompt(text: str) -> str:
    return (
        "You are an internal drafter. Return only JSON with keys: normalized_text, intent, constraints. "
        "Normalize whitespace, remove non-semantic noise, keep original meaning.\n"
        f"Input:\n{text}"
    )


def _build_judge_prompt(text: str, category: str, flags: List[str]) -> str:
    return (
        "You are a strict quality judge. Return only JSON with keys: score, verdict, judge_flags. "
        "score must be 0..1. verdict in {PASS,REVIEW,FAIL}. Do not include reasoning tags.\n"
        f"Text:\n{text}\nChosen category: {category}\nFlags: {flags}"
    )


def _assert_local_ollama_url() -> None:
    if DEFAULT_ALLOW_REMOTE_OLLAMA:
        return
    parsed = urllib.parse.urlparse(OLLAMA_URL)
    hostname = (parsed.hostname or "").strip().lower()
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(
            "Remote Ollama URL is blocked by default. Use a local loopback URL or set SPOT_ALLOW_REMOTE_OLLAMA=1."
        )


def _ollama_generate_json(model_name: str, prompt: str, timeout: int = OLLAMA_TIMEOUT_SEC) -> dict:
    _assert_local_ollama_url()
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": OLLAMA_TEMPERATURE, "top_p": OLLAMA_TOP_P, "seed": OLLAMA_SEED, "num_ctx": 4096},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    txt = strip_reasoning_artifacts(str(raw.get("response", "")))
    return json.loads(txt) if txt else {}


def _extract_last_json_object(text: str) -> dict:
    candidate = text.strip()
    if not candidate:
        return {}
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    for idx in range(len(candidate) - 1, -1, -1):
        if candidate[idx] != "{":
            continue
        try:
            return json.loads(candidate[idx:])
        except json.JSONDecodeError:
            continue
    return {}


def _extract_confidence_from_text(text: str, default: float = 0.5) -> float:
    decimal_matches = re.findall(r"(?<!\d)(0\.\d+|1\.0+)(?!\d)", text)
    matches = decimal_matches or re.findall(r"\b(score|confidence)\s*[:=]?\s*(0|1)\b", text, flags=re.IGNORECASE)
    if not matches:
        return default
    try:
        if isinstance(matches[0], tuple):
            value = float(matches[0][1])
        else:
            value = float(matches[0])
    except ValueError:
        return default
    return min(max(value, 0.0), 1.0)


def _sanitize_soft_signal_flags(flags: list[str], ssot: SSOT) -> list[str]:
    allowed = set(ssot.policy.soft_signal_flags)
    normalized = []
    for flag in flags:
        token = str(flag).strip().upper()
        if token in allowed:
            normalized.append(token)
    return sorted(set(normalized))


def _extract_evidence_snippet(text: str, start: int, end: int, radius: int = 36) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet[:180]


def _heuristic_soft_signals(text: str, ssot: SSOT) -> tuple[list[str], list[str]]:
    found_flags: list[str] = []
    evidence: list[str] = []
    for flag_name, patterns in SOFT_SIGNAL_PATTERNS.items():
        if flag_name not in set(ssot.policy.soft_signal_flags):
            continue
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            found_flags.append(flag_name)
            evidence.append(_extract_evidence_snippet(text, match.start(), match.end()))
            break
    return sorted(set(found_flags)), evidence[:MAX_SOFT_SIGNAL_EVIDENCE]


def _sanitize_soft_signal_evidence(evidence: list[str], text: str) -> list[str]:
    sanitized: list[str] = []
    lowered = text.lower()
    for item in evidence:
        snippet = re.sub(r"\s+", " ", str(item).strip().strip('"').strip("'"))
        if not snippet:
            continue
        probe = snippet.lower()
        if probe in lowered:
            sanitized.append(snippet[:180])
            continue
        for token in re.findall(r"[A-Za-z0-9()'-]{4,}", probe):
            if token in lowered:
                sanitized.append(snippet[:180])
                break
    return list(dict.fromkeys(sanitized))[:MAX_SOFT_SIGNAL_EVIDENCE]


def _extract_category_from_text(text: str) -> str:
    t = text.lower()
    if "not antisemitic" in t or "non-antisemitic" in t or "non antisemitic" in t:
        return "Not Antisemitic"
    if "anti-israel" in t or "anti israel" in t:
        return "Anti-Israel"
    if "anti-judaism" in t or "anti judaism" in t:
        return "Anti-Judaism"
    if "classical antisemitism" in t or "holocaust denial" in t:
        return "Classical Antisemitism"
    if "structural antisemitism" in t:
        return "Structural Antisemitism"
    if "conspiracy theor" in t:
        return "Conspiracy Theories"
    return "Not Antisemitic"


def _extract_verdict_from_text(text: str) -> str:
    t = text.lower()
    if "fail" in t:
        return "FAIL"
    if "pass" in t:
        return "PASS"
    return "REVIEW"


def _mlx_generate_json(model_name: str, prompt: str, timeout: int = OLLAMA_TIMEOUT_SEC) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "mlx_lm",
        "generate",
        "--model",
        model_name,
        "--prompt",
        prompt,
        "--max-tokens",
        "512",
        "--temp",
        "0",
        "--top-p",
        "1.0",
        "--seed",
        str(OLLAMA_SEED),
    ]
    try:
        raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError("MLX backend selected but mlx_lm is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"MLX generate failed: {exc.output[-400:]}") from exc
    txt = strip_reasoning_artifacts(raw)
    txt = txt.replace("\r", "\n")
    txt = re.sub(r"^\s*Fetching .*?$", "", txt, flags=re.MULTILINE)
    txt = re.sub(r"^=+\n|\n=+$", "", txt).strip()
    txt = re.sub(r"\nPrompt:.*$", "", txt, flags=re.DOTALL).strip()
    obj = _extract_last_json_object(txt)
    return obj if obj else {"raw_text": txt}


def _generate_json(backend: str, model_name: str, prompt: str, timeout: int = OLLAMA_TIMEOUT_SEC) -> dict:
    if backend == "ollama":
        return _ollama_generate_json(model_name, prompt, timeout=timeout)
    if backend == "mlx":
        return _mlx_generate_json(model_name, prompt, timeout=timeout)
    raise RuntimeError(f"Unsupported backend '{backend}'. Expected one of: ollama, mlx.")


def run_drafter(text: str) -> tuple[str, List[str]]:
    if not text.strip():
        return text, []
    flags: List[str] = []
    fallback_models = [
        model.strip() for model in LANES.drafter_fallback_model.split(",") if model.strip()
    ]
    route_chain = [(LANES.drafter_backend, LANES.drafter_model)] + [
        (LANES.drafter_fallback_backend, model_name) for model_name in fallback_models
    ]
    for backend, model_name in route_chain:
        try:
            obj = _generate_json(backend, model_name, _build_drafter_prompt(text))
            normalized = str(obj.get("normalized_text", "")).strip()
            if not normalized and obj.get("raw_text"):
                normalized = str(obj.get("raw_text", "")).strip()
            if normalized:
                return normalized, flags
        except Exception:
            flags.append("DRAFTER_FALLBACK")
            continue
    flags.append("DRAFTER_UNAVAILABLE")
    return text, flags


def run_judge(text: str, category: str, flags: List[str]) -> tuple[float | None, str | None, List[str]]:
    out_flags: List[str] = []
    route_chain = [
        (LANES.judge_backend, LANES.judge_model),
        (LANES.judge_fallback_backend, LANES.judge_fallback_model),
    ]
    for backend, model_name in route_chain:
        try:
            obj = _generate_json(backend, model_name, _build_judge_prompt(text, category, flags))
            score = float(obj.get("score", _extract_confidence_from_text(str(obj.get("raw_text", "")), 0.5)))
            score = min(max(score, 0.0), 1.0)
            verdict = str(
                obj.get("verdict", _extract_verdict_from_text(str(obj.get("raw_text", ""))))
            ).strip().upper()
            if verdict not in {"PASS", "REVIEW", "FAIL"}:
                verdict = "REVIEW"
            judge_flags = [str(f).strip().upper() for f in obj.get("judge_flags", []) if str(f).strip()]
            return score, verdict, judge_flags + out_flags
        except Exception:
            out_flags.append("JUDGE_FALLBACK")
            continue
    return None, None, out_flags + ["JUDGE_UNAVAILABLE"]


def normalize_label(raw_label: str) -> Optional[str]:
    if not raw_label:
        return "Not Antisemitic"

    label = raw_label.strip().lower()
    label = label.replace("-", " ")
    label = " ".join(label.split())

    mapping = {
        "anti israel": "Anti-Israel",
        "anti judaism": "Anti-Judaism",
        "classical antisemitism": "Classical Antisemitism",
        "classical antisemitic": "Classical Antisemitism",
        "structural antisemitism": "Structural Antisemitism",
        "conspiracy theories": "Conspiracy Theories",
        "conspiracy theory": "Conspiracy Theories",
        "not antisemitic": "Not Antisemitic",
        "not antisemetic": "Not Antisemitic",
        "holocaust denial": "Classical Antisemitism",
    }

    return mapping.get(label)


def _enforce_taxonomy(raw_label: str, flags: List[str]) -> Tuple[str, List[str]]:
    normalized = normalize_label(raw_label)
    next_flags = list(flags)
    if normalized not in CANONICAL_CATEGORIES:
        normalized = "Not Antisemitic"
        next_flags.append("TAXONOMY_VIOLATION")
    return normalized, next_flags


def _classify_with_backend(text: str, ssot: SSOT, backend: str, model_name: str) -> ClassificationResult:
    prompt = _build_prompt(
        text,
        ssot.taxonomy.categories,
        ssot.taxonomy.fallback_category,
        ssot.policy.soft_signal_flags,
    )
    obj = _generate_json(backend, model_name, prompt)

    raw_text = str(obj.get("raw_text", ""))
    raw_category = str(obj.get("category", _extract_category_from_text(raw_text)))
    flags = [str(f).strip().upper() for f in obj.get("flags", []) if str(f).strip()][:8]
    if raw_text and "category" not in obj:
        flags.append("UNSTRUCTURED_MODEL_OUTPUT")
    category, flags = _enforce_taxonomy(raw_category, flags)

    try:
        confidence = float(obj.get("confidence", _extract_confidence_from_text(raw_text, 0.5)))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(max(confidence, 0.0), 1.0)

    explanation = str(obj.get("explanation", "")).strip()
    if not explanation:
        if raw_text:
            explanation = "Model returned unstructured output; category was derived via deterministic normalization and taxonomy enforcement."
        else:
            explanation = "No explanation returned by model."
    explanation = sanitize_explanation(explanation)
    model_soft_flags = _sanitize_soft_signal_flags(list(obj.get("soft_signal_flags", [])), ssot)
    heuristic_soft_flags, heuristic_evidence = _heuristic_soft_signals(text, ssot)
    soft_signal_flags = sorted(set(model_soft_flags + heuristic_soft_flags))
    model_evidence = _sanitize_soft_signal_evidence(list(obj.get("soft_signal_evidence", [])), text)
    soft_signal_evidence = list(dict.fromkeys(model_evidence + heuristic_evidence))[:MAX_SOFT_SIGNAL_EVIDENCE]
    try:
        soft_signal_score = float(obj.get("soft_signal_score", 0.0))
    except (TypeError, ValueError):
        soft_signal_score = 0.0
    soft_signal_score = min(max(soft_signal_score, 0.0), 1.0)
    if heuristic_soft_flags:
        soft_signal_score = max(soft_signal_score, 0.55 if len(heuristic_soft_flags) == 1 else 0.7)

    return ClassificationResult(
        row_index=-1,
        raw_category=raw_category,
        category=category,
        confidence=confidence,
        explanation=explanation,
        flags=flags,
        soft_signal_score=soft_signal_score,
        soft_signal_flags=soft_signal_flags,
        soft_signal_evidence=soft_signal_evidence,
        resolved_model_version=format_model_version(backend, model_name),
    )


def _sanitize_flags(flags: List[str], text: str) -> List[str]:
    sanitized = sorted(set(flags))
    if text.strip() != "":
        sanitized = [f for f in sanitized if f not in {"EMPTY_TEXT", "SKIPPED"}]
    if len(text.strip()) > 30:
        sanitized = [f for f in sanitized if f != "NONSENSICAL_OR_SHORT"]
    return sanitized


def _normalize_backend_result(
    *,
    row: InputRow,
    drafted_text: str,
    result: ClassificationResult,
    text: str,
) -> ClassificationResult:
    result.row_index = row.row_index
    result.raw_category = result.raw_category or ""
    result.drafted_text = drafted_text
    result.flags = _sanitize_flags(result.flags, text)
    enforced_category, enforced_flags = _enforce_taxonomy(result.category, result.flags)
    result.category = enforced_category
    result.flags = enforced_flags
    if not result.category:
        result.category = "Not Antisemitic"
        result.flags.append("EMPTY_CATEGORY_RECOVERED")
    result.fallback_events = sorted(set(result.fallback_events or []))
    return result


def _should_run_targeted_second_pass(result: ClassificationResult, ssot: SSOT) -> bool:
    if "MODEL_REQUEST_FAILED" in (result.flags or []):
        return True
    if "CLASSIFIER_FALLBACK_FAILED" in (result.flags or []):
        return True
    if "CLASSIFIER_FALLBACK" in (result.flags or []):
        return True
    if "LOW_CONFIDENCE" in (result.flags or []):
        return True
    if "SOFT_SIGNAL_REVIEW" in (result.flags or []):
        return True
    if result.category != "Not Antisemitic" and float(result.confidence or 0.0) < 0.9:
        return True
    if (result.soft_signal_score or 0.0) >= ssot.policy.soft_signal_review_threshold:
        return True
    return False


def _alternate_classifier_route(model_name: str = ""):
    primary_route = parse_model_spec(model_name, LANES.classifier_backend, LANES.classifier_model)
    fallback_route = parse_model_spec(
        "",
        LANES.classifier_fallback_backend,
        LANES.classifier_fallback_model,
    )
    if primary_route.version == fallback_route.version:
        return primary_route, False
    return fallback_route, True


def _judge_rank(verdict: str | None) -> int:
    if verdict == "PASS":
        return 2
    if verdict == "REVIEW":
        return 1
    if verdict == "FAIL":
        return 0
    return -1


def _adjudicate_targeted_row(
    row: InputRow,
    initial_result: ClassificationResult,
    ssot: SSOT,
    review_mode: str,
    model_name: str = "",
) -> ClassificationResult:
    if not _should_run_targeted_second_pass(initial_result, ssot):
        return initial_result

    text = row.post_text.strip()
    drafted_text = initial_result.drafted_text or text
    merged_flags = list(initial_result.flags or [])
    fallback_events = list(initial_result.fallback_events or [])
    model_votes = dict(initial_result.model_votes or {})
    if initial_result.resolved_model_version:
        model_votes.setdefault(initial_result.resolved_model_version, initial_result.category)

    alternate_result: ClassificationResult | None = None
    alternate_route, used_alternate = _alternate_classifier_route(model_name)
    if used_alternate and text:
        try:
            alternate_result = _classify_with_backend(
                drafted_text,
                ssot,
                backend=alternate_route.backend,
                model_name=alternate_route.model_name,
            )
            alternate_result = _normalize_backend_result(
                row=row,
                drafted_text=drafted_text,
                result=alternate_result,
                text=text,
            )
            merged_flags.append("SECOND_PASS_RECHECK")
            if alternate_result.resolved_model_version:
                model_votes[alternate_result.resolved_model_version] = alternate_result.category
            fallback_events.append("SECOND_PASS_ALT_ROUTE")
        except Exception:
            merged_flags.append("SECOND_PASS_UNAVAILABLE")
            fallback_events.append("SECOND_PASS_UNAVAILABLE")

    selected_result = initial_result
    judge_score = initial_result.judge_score
    judge_verdict = initial_result.judge_verdict
    judge_flags: list[str] = []

    if alternate_result and alternate_result.category == initial_result.category:
        merged_flags.append("SECOND_PASS_CONFIRMED")
        selected_result = ClassificationResult(
            row_index=initial_result.row_index,
            raw_category=initial_result.raw_category,
            category=initial_result.category,
            confidence=max(initial_result.confidence, alternate_result.confidence),
            explanation=initial_result.explanation if len(initial_result.explanation) >= len(alternate_result.explanation) else alternate_result.explanation,
            flags=initial_result.flags,
            soft_signal_score=max(initial_result.soft_signal_score or 0.0, alternate_result.soft_signal_score or 0.0),
            soft_signal_flags=sorted(set((initial_result.soft_signal_flags or []) + (alternate_result.soft_signal_flags or []))),
            soft_signal_evidence=list(dict.fromkeys((initial_result.soft_signal_evidence or []) + (alternate_result.soft_signal_evidence or [])))[:MAX_SOFT_SIGNAL_EVIDENCE],
            resolved_model_version=initial_result.resolved_model_version,
            model_votes=model_votes,
            consensus_tier=initial_result.consensus_tier,
            minority_label=initial_result.minority_label,
            drafted_text=drafted_text,
            judge_score=initial_result.judge_score,
            judge_verdict=initial_result.judge_verdict,
            fallback_events=sorted(set(fallback_events + (alternate_result.fallback_events or []))),
        )
        judge_score, judge_verdict, judge_flags = run_judge(text=text, category=selected_result.category, flags=sorted(set(merged_flags)))
    elif alternate_result and alternate_result.category != initial_result.category:
        merged_flags.append("SECOND_PASS_DISAGREEMENT")
        initial_judge_score, initial_judge_verdict, initial_judge_flags = run_judge(
            text=text,
            category=initial_result.category,
            flags=sorted(set(merged_flags)),
        )
        alternate_judge_score, alternate_judge_verdict, alternate_judge_flags = run_judge(
            text=text,
            category=alternate_result.category,
            flags=sorted(set(merged_flags)),
        )
        judge_flags = sorted(set(initial_judge_flags + alternate_judge_flags))
        initial_rank = _judge_rank(initial_judge_verdict)
        alternate_rank = _judge_rank(alternate_judge_verdict)
        if alternate_rank > initial_rank or (
            alternate_rank == initial_rank and (alternate_judge_score or 0.0) > (initial_judge_score or 0.0)
        ):
            selected_result = alternate_result
            judge_score = alternate_judge_score
            judge_verdict = alternate_judge_verdict
            merged_flags.append("SECOND_PASS_CATEGORY_OVERRIDDEN")
        else:
            judge_score = initial_judge_score
            judge_verdict = initial_judge_verdict
        merged_flags.append("REVIEW_REQUIRED")
        fallback_events.extend(alternate_result.fallback_events or [])
    else:
        judge_score, judge_verdict, judge_flags = run_judge(
            text=text,
            category=selected_result.category,
            flags=sorted(set(merged_flags)),
        )

    if judge_verdict in {"REVIEW", "FAIL"}:
        merged_flags.append("REVIEW_REQUIRED")
    if judge_verdict == "FAIL":
        merged_flags.append("SECOND_PASS_JUDGE_FAIL")
    if judge_verdict == "REVIEW":
        merged_flags.append("SECOND_PASS_JUDGE_REVIEW")
    if "JUDGE_FALLBACK" in judge_flags:
        fallback_events.append("JUDGE_ROUTE_FALLBACK")
    if "JUDGE_UNAVAILABLE" in judge_flags:
        fallback_events.append("JUDGE_UNAVAILABLE")

    adjudicated = ClassificationResult(
        row_index=selected_result.row_index,
        raw_category=selected_result.raw_category,
        category=selected_result.category,
        confidence=selected_result.confidence,
        explanation=selected_result.explanation,
        flags=sorted(set(merged_flags + judge_flags + (selected_result.flags or []))),
        soft_signal_score=selected_result.soft_signal_score,
        soft_signal_flags=selected_result.soft_signal_flags,
        soft_signal_evidence=selected_result.soft_signal_evidence,
        resolved_model_version=selected_result.resolved_model_version,
        model_votes=model_votes or None,
        consensus_tier=selected_result.consensus_tier,
        minority_label=selected_result.minority_label,
        drafted_text=drafted_text,
        judge_score=judge_score,
        judge_verdict=judge_verdict,
        fallback_events=sorted(set(fallback_events)),
    )
    return _apply_review_mode(adjudicated, ssot, review_mode)


def _apply_review_mode(result: ClassificationResult, ssot: SSOT, review_mode: str) -> ClassificationResult:
    flags = list(result.flags)
    low_conf = result.confidence < ssot.policy.low_confidence_threshold
    soft_signal_score = result.soft_signal_score or 0.0
    soft_signal_flags = sorted(set(result.soft_signal_flags or []))
    soft_signal_evidence = list(result.soft_signal_evidence or [])
    if low_conf:
        flags.append("LOW_CONFIDENCE")
    soft_signal_review = bool(soft_signal_flags) or soft_signal_score >= ssot.policy.soft_signal_review_threshold
    if soft_signal_review:
        flags.append("SOFT_SIGNAL_REVIEW")

    if review_mode == "full":
        flags.append("REVIEW_REQUIRED")
    elif review_mode == "partial" and (low_conf or soft_signal_review):
        flags.append("REVIEW_REQUIRED")

    if not result.explanation.strip():
        result.explanation = "No explanation generated by model; fallback audit explanation applied."
        flags.append("EXPLANATION_FALLBACK")

    return ClassificationResult(
        row_index=result.row_index,
        raw_category=result.raw_category,
        category=result.category,
        confidence=result.confidence,
        explanation=result.explanation,
        flags=sorted(set(flags)),
        soft_signal_score=soft_signal_score,
        soft_signal_flags=soft_signal_flags,
        soft_signal_evidence=soft_signal_evidence,
        resolved_model_version=result.resolved_model_version,
        model_votes=result.model_votes,
        consensus_tier=result.consensus_tier,
        minority_label=result.minority_label,
        drafted_text=result.drafted_text,
        judge_score=result.judge_score,
        judge_verdict=result.judge_verdict,
        fallback_events=result.fallback_events,
    )


def classify_row(row: InputRow, ssot: SSOT, review_mode: str, model_name: str = "") -> ClassificationResult:
    text = row.post_text.strip()
    primary_route = parse_model_spec(model_name, LANES.classifier_backend, LANES.classifier_model)

    if text == "":
        result = ClassificationResult(
            row_index=row.row_index,
            raw_category="",
            category=ssot.taxonomy.fallback_category,
            confidence=0.51,
            explanation="Empty post text: skipped semantic analysis; fallback category applied per SSOT.",
            flags=["EMPTY_TEXT", "SKIPPED"],
            soft_signal_score=0.0,
            soft_signal_flags=[],
            soft_signal_evidence=[],
            resolved_model_version=primary_route.version,
            drafted_text="",
            fallback_events=["EMPTY_TEXT_FALLBACK"],
        )
        return _apply_review_mode(result, ssot, review_mode)

    drafted_text, drafter_flags = run_drafter(text)
    fallback_events: List[str] = []
    if "DRAFTER_FALLBACK" in drafter_flags:
        fallback_events.append("DRAFTER_ROUTE_FALLBACK")
    if "DRAFTER_UNAVAILABLE" in drafter_flags:
        fallback_events.append("DRAFTER_UNAVAILABLE")
    try:
        result = _classify_with_backend(
            drafted_text,
            ssot,
            backend=primary_route.backend,
            model_name=primary_route.model_name,
        )
    except Exception:
        try:
            fallback_route = parse_model_spec(
                "",
                LANES.classifier_fallback_backend,
                LANES.classifier_fallback_model,
            )
            result = _classify_with_backend(
                drafted_text,
                ssot,
                backend=fallback_route.backend,
                model_name=fallback_route.model_name,
            )
            result.flags = sorted(set(result.flags + ["CLASSIFIER_FALLBACK"]))
            fallback_events.append("CLASSIFIER_ROUTE_FALLBACK")
        except Exception:
            result = ClassificationResult(
                row_index=-1,
                raw_category="",
                category="Not Antisemitic",
                confidence=0.5,
                explanation="Model request failed or timed out; fallback category applied.",
                flags=["MODEL_REQUEST_FAILED", "CLASSIFIER_FALLBACK_FAILED"],
                soft_signal_score=0.0,
                soft_signal_flags=[],
                soft_signal_evidence=[],
                resolved_model_version=primary_route.version,
                fallback_events=["CLASSIFIER_FALLBACK_FAILED"],
            )
    result.flags = result.flags + drafter_flags
    result.fallback_events = sorted(set((result.fallback_events or []) + fallback_events))
    result = _normalize_backend_result(row=row, drafted_text=drafted_text, result=result, text=text)
    return _apply_review_mode(result, ssot, review_mode)


def classify_batch(
    rows: List[InputRow],
    ssot: SSOT,
    max_workers: int,
    review_mode: str,
    model_name: str = "",
    progress_callback: Callable[[int, int, ClassificationResult], None] | None = None,
    row_completion_callback: Callable[[int, int, int, ClassificationResult, str], None] | None = None,
    progress_every: int = 100,
) -> Tuple[List[ClassificationResult], List[str]]:
    hashes = [stable_row_hash(r.item_number, r.post_text) for r in rows]
    total = len(rows)
    results: List[ClassificationResult] = [None] * total  # type: ignore[list-item]

    def classify_one(row: InputRow) -> ClassificationResult:
        initial_result = classify_row(row, ssot, review_mode, model_name)
        return _adjudicate_targeted_row(row, initial_result, ssot, review_mode, model_name)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(classify_one, row): idx
            for idx, row in enumerate(rows)
        }
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
            completed += 1
            if row_completion_callback:
                row_completion_callback(completed, total, idx, results[idx], hashes[idx])
            if progress_callback and (completed % progress_every == 0 or completed == total):
                progress_callback(completed, total, results[idx])
    return results, hashes
