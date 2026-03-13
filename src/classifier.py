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


def _build_prompt(text: str, categories: List[str], fallback: str) -> str:
    cats = json.dumps(categories, ensure_ascii=False)
    return (
        "You are a strict single-label classifier for antisemitism taxonomy. "
        "Preprocess text internally before classification: normalize whitespace, remove non-semantic noise, and handle typos. "
        "Return exactly one JSON object and no other text. "
        "Required keys: category, confidence, explanation, flags. "
        f"Allowed categories: {cats}. "
        f"If uncertain or no clear evidence, use fallback '{fallback}'. "
        "For empty or missing text, set fallback, include EMPTY_TEXT and SKIPPED flags. "
        "For very short or nonsensical text, include NONSENSICAL_OR_SHORT flag. "
        "confidence must be float [0,1]. flags must be array of uppercase tokens.\n"
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
            "Remote Ollama URL is blocked by default. Use a local loopback URL or set TEV_ALLOW_REMOTE_OLLAMA=1."
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
    route_chain = [
        (LANES.drafter_backend, LANES.drafter_model),
        (LANES.drafter_fallback_backend, LANES.drafter_fallback_model),
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
    prompt = _build_prompt(text, ssot.taxonomy.categories, ssot.taxonomy.fallback_category)
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
    explanation = explanation[:700]

    return ClassificationResult(
        row_index=-1,
        raw_category=raw_category,
        category=category,
        confidence=confidence,
        explanation=explanation,
        flags=flags,
        resolved_model_version=format_model_version(backend, model_name),
    )


def _sanitize_flags(flags: List[str], text: str) -> List[str]:
    sanitized = sorted(set(flags))
    if text.strip() != "":
        sanitized = [f for f in sanitized if f not in {"EMPTY_TEXT", "SKIPPED"}]
    if len(text.strip()) > 30:
        sanitized = [f for f in sanitized if f != "NONSENSICAL_OR_SHORT"]
    return sanitized


def _apply_review_mode(result: ClassificationResult, ssot: SSOT, review_mode: str) -> ClassificationResult:
    flags = list(result.flags)
    low_conf = result.confidence < ssot.policy.low_confidence_threshold
    if low_conf:
        flags.append("LOW_CONFIDENCE")

    if review_mode == "full":
        flags.append("REVIEW_REQUIRED")
    elif review_mode == "partial" and low_conf:
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
        resolved_model_version=result.resolved_model_version,
        model_votes=result.model_votes,
        consensus_tier=result.consensus_tier,
        minority_label=result.minority_label,
        drafted_text=result.drafted_text,
        judge_score=result.judge_score,
        judge_verdict=result.judge_verdict,
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
            resolved_model_version=primary_route.version,
            drafted_text="",
        )
        return _apply_review_mode(result, ssot, review_mode)

    drafted_text, drafter_flags = run_drafter(text)
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
        except Exception:
            result = ClassificationResult(
                row_index=-1,
                raw_category="",
                category="Not Antisemitic",
                confidence=0.5,
                explanation="Model request failed or timed out; fallback category applied.",
                flags=["MODEL_REQUEST_FAILED", "CLASSIFIER_FALLBACK_FAILED"],
                resolved_model_version=primary_route.version,
            )
    result.row_index = row.row_index
    result.raw_category = result.raw_category or ""
    result.drafted_text = drafted_text
    result.flags = _sanitize_flags(result.flags + drafter_flags, text)
    enforced_category, enforced_flags = _enforce_taxonomy(result.category, result.flags)
    result.category = enforced_category
    result.flags = enforced_flags
    if not result.category:
        result.category = "Not Antisemitic"
        result.flags.append("EMPTY_CATEGORY_RECOVERED")
    return _apply_review_mode(result, ssot, review_mode)


def classify_batch(
    rows: List[InputRow],
    ssot: SSOT,
    max_workers: int,
    review_mode: str,
    model_name: str = "",
    progress_callback: Callable[[int, int], None] | None = None,
    progress_every: int = 100,
) -> Tuple[List[ClassificationResult], List[str]]:
    hashes = [stable_row_hash(r.item_number, r.post_text) for r in rows]
    total = len(rows)
    results: List[ClassificationResult] = [None] * total  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(classify_row, row, ssot, review_mode, model_name): idx
            for idx, row in enumerate(rows)
        }
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
            completed += 1
            if progress_callback and (completed % progress_every == 0 or completed == total):
                progress_callback(completed, total)
    return results, hashes
