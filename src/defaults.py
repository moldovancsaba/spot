from __future__ import annotations

import os
from pathlib import Path

from .ssot_loader import SSOTError, load_ssot


def _env(primary: str, legacy: str | None = None, default: str | None = None) -> str | None:
    if primary in os.environ:
        return os.environ[primary]
    return default


DEFAULT_SSOT_PATH = _env("SPOT_SSOT_PATH", None, "ssot/ssot.json") or "ssot/ssot.json"
_DEFAULT_SSOT = None
try:
    _DEFAULT_SSOT = load_ssot(Path(DEFAULT_SSOT_PATH))
except SSOTError:
    _DEFAULT_SSOT = None


DEFAULT_CLASSIFIER_BACKEND = _env(
    "SPOT_ROUTE_CLASSIFIER_BACKEND",
    _DEFAULT_SSOT.runtime.classifier.backend if _DEFAULT_SSOT else "mlx",
) or (_DEFAULT_SSOT.runtime.classifier.backend if _DEFAULT_SSOT else "mlx")
DEFAULT_CLASSIFIER_MODEL = _env(
    "SPOT_ROUTE_CLASSIFIER_MODEL",
    _DEFAULT_SSOT.runtime.classifier.model if _DEFAULT_SSOT else "mlx-community/Apertus-8B-Instruct-2509-4bit",
) or (_DEFAULT_SSOT.runtime.classifier.model if _DEFAULT_SSOT else "mlx-community/Apertus-8B-Instruct-2509-4bit")
DEFAULT_CLASSIFIER_FALLBACK_BACKEND = _env(
    "SPOT_ROUTE_CLASSIFIER_FALLBACK_BACKEND",
    _DEFAULT_SSOT.runtime.classifier.fallback_backend if _DEFAULT_SSOT else "ollama",
) or (_DEFAULT_SSOT.runtime.classifier.fallback_backend if _DEFAULT_SSOT else "ollama")
DEFAULT_CLASSIFIER_FALLBACK_MODEL = _env(
    "SPOT_ROUTE_CLASSIFIER_FALLBACK_MODEL",
    _DEFAULT_SSOT.runtime.classifier.fallback_model if _DEFAULT_SSOT else "qwen2.5:7b",
) or (_DEFAULT_SSOT.runtime.classifier.fallback_model if _DEFAULT_SSOT else "qwen2.5:7b")
DEFAULT_DRAFTER_BACKEND = _env(
    "SPOT_ROUTE_DRAFTER_BACKEND",
    _DEFAULT_SSOT.runtime.drafter.backend if _DEFAULT_SSOT else "ollama",
) or (_DEFAULT_SSOT.runtime.drafter.backend if _DEFAULT_SSOT else "ollama")
DEFAULT_DRAFTER_MODEL = _env(
    "SPOT_ROUTE_DRAFTER_MODEL",
    _DEFAULT_SSOT.runtime.drafter.model if _DEFAULT_SSOT else "granite4:350m",
) or (_DEFAULT_SSOT.runtime.drafter.model if _DEFAULT_SSOT else "granite4:350m")
DEFAULT_DRAFTER_FALLBACK_BACKEND = _env(
    "SPOT_ROUTE_DRAFTER_FALLBACK_BACKEND",
    _DEFAULT_SSOT.runtime.drafter.fallback_backend if _DEFAULT_SSOT else "ollama",
) or (_DEFAULT_SSOT.runtime.drafter.fallback_backend if _DEFAULT_SSOT else "ollama")
DEFAULT_DRAFTER_FALLBACK_MODEL = _env(
    "SPOT_ROUTE_DRAFTER_FALLBACK_MODEL",
    _DEFAULT_SSOT.runtime.drafter.fallback_model if _DEFAULT_SSOT else "gemma3:1b,llama3.2:1b",
) or (_DEFAULT_SSOT.runtime.drafter.fallback_model if _DEFAULT_SSOT else "gemma3:1b,llama3.2:1b")
DEFAULT_JUDGE_BACKEND = _env(
    "SPOT_ROUTE_JUDGE_BACKEND",
    _DEFAULT_SSOT.runtime.judge.backend if _DEFAULT_SSOT else "ollama",
) or (_DEFAULT_SSOT.runtime.judge.backend if _DEFAULT_SSOT else "ollama")
DEFAULT_JUDGE_MODEL = _env(
    "SPOT_ROUTE_JUDGE_MODEL",
    _DEFAULT_SSOT.runtime.judge.model if _DEFAULT_SSOT else "llama3.2:3b",
) or (_DEFAULT_SSOT.runtime.judge.model if _DEFAULT_SSOT else "llama3.2:3b")
DEFAULT_JUDGE_FALLBACK_BACKEND = _env(
    "SPOT_ROUTE_JUDGE_FALLBACK_BACKEND",
    _DEFAULT_SSOT.runtime.judge.fallback_backend if _DEFAULT_SSOT else "ollama",
) or (_DEFAULT_SSOT.runtime.judge.fallback_backend if _DEFAULT_SSOT else "ollama")
DEFAULT_JUDGE_FALLBACK_MODEL = _env(
    "SPOT_ROUTE_JUDGE_FALLBACK_MODEL",
    _DEFAULT_SSOT.runtime.judge.fallback_model if _DEFAULT_SSOT else "gemma2:2b",
) or (_DEFAULT_SSOT.runtime.judge.fallback_model if _DEFAULT_SSOT else "gemma2:2b")

DEFAULT_OLLAMA_URL = _env(
    "SPOT_OLLAMA_URL",
    None,
    _DEFAULT_SSOT.runtime.security.ollama_url if _DEFAULT_SSOT else "http://127.0.0.1:11434/api/generate",
) or (_DEFAULT_SSOT.runtime.security.ollama_url if _DEFAULT_SSOT else "http://127.0.0.1:11434/api/generate")
DEFAULT_ALLOW_REMOTE_OLLAMA = (
    _env(
        "SPOT_ALLOW_REMOTE_OLLAMA",
        None,
        "1" if (_DEFAULT_SSOT and _DEFAULT_SSOT.runtime.security.allow_remote_ollama) else "0",
    )
    or "0"
).strip() == "1"
DEFAULT_PRODUCTION_MODE = (_env("SPOT_PRODUCTION_MODE", None, "0") or "0").strip() == "1"
DEFAULT_LOCKED_SSOT_PATH = _env("SPOT_LOCKED_SSOT_PATH", None, DEFAULT_SSOT_PATH) or DEFAULT_SSOT_PATH

DEFAULT_SINGLE_MODEL = _env(
    "SPOT_SINGLE_MODEL",
    None,
    _DEFAULT_SSOT.runtime.evaluation.single_model
    if _DEFAULT_SSOT
    else "mlx://mlx-community/Apertus-8B-Instruct-2509-4bit",
) or (
    _DEFAULT_SSOT.runtime.evaluation.single_model
    if _DEFAULT_SSOT
    else "mlx://mlx-community/Apertus-8B-Instruct-2509-4bit"
)
DEFAULT_ENSEMBLE_MODELS = _env(
    "SPOT_ENSEMBLE_MODELS",
    None,
    ",".join(_DEFAULT_SSOT.runtime.evaluation.ensemble_models)
    if _DEFAULT_SSOT
    else "ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b",
) or (
    ",".join(_DEFAULT_SSOT.runtime.evaluation.ensemble_models)
    if _DEFAULT_SSOT
    else "ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b"
)
DEFAULT_INPUT_PATH = _env("SPOT_INPUT_PATH", None, "samples/sample_germany.xlsx") or "samples/sample_germany.xlsx"
DEFAULT_LANGUAGE = _env("SPOT_LANGUAGE", None, "de") or "de"
DEFAULT_REVIEW_MODE = _env("SPOT_REVIEW_MODE", None, "partial") or "partial"
DEFAULT_LIMIT = int(_env("SPOT_LIMIT", None, "500") or "500")
DEFAULT_MAX_WORKERS = int(_env("SPOT_MAX_WORKERS", None, "1") or "1")
DEFAULT_PROGRESS_EVERY = int(_env("SPOT_PROGRESS_EVERY", None, "10") or "10")
