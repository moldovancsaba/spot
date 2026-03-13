from __future__ import annotations

import os
from pathlib import Path

from .ssot_loader import SSOTError, load_ssot


DEFAULT_SSOT_PATH = os.getenv("DEFAULT_SSOT_PATH", "ssot/ssot.json")
_DEFAULT_SSOT = None
try:
    _DEFAULT_SSOT = load_ssot(Path(DEFAULT_SSOT_PATH))
except SSOTError:
    _DEFAULT_SSOT = None


DEFAULT_CLASSIFIER_BACKEND = os.getenv(
    "TEV_ROUTE_CLASSIFIER_BACKEND",
    _DEFAULT_SSOT.runtime.classifier.backend if _DEFAULT_SSOT else "mlx",
)
DEFAULT_CLASSIFIER_MODEL = os.getenv(
    "TEV_ROUTE_CLASSIFIER_MODEL",
    _DEFAULT_SSOT.runtime.classifier.model if _DEFAULT_SSOT else "mlx-community/Apertus-8B-Instruct-2509-4bit",
)
DEFAULT_CLASSIFIER_FALLBACK_BACKEND = os.getenv(
    "TEV_ROUTE_CLASSIFIER_FALLBACK_BACKEND",
    _DEFAULT_SSOT.runtime.classifier.fallback_backend if _DEFAULT_SSOT else "ollama",
)
DEFAULT_CLASSIFIER_FALLBACK_MODEL = os.getenv(
    "TEV_ROUTE_CLASSIFIER_FALLBACK_MODEL",
    _DEFAULT_SSOT.runtime.classifier.fallback_model if _DEFAULT_SSOT else "qwen2.5:7b",
)
DEFAULT_DRAFTER_BACKEND = os.getenv(
    "TEV_ROUTE_DRAFTER_BACKEND",
    _DEFAULT_SSOT.runtime.drafter.backend if _DEFAULT_SSOT else "ollama",
)
DEFAULT_DRAFTER_MODEL = os.getenv(
    "TEV_ROUTE_DRAFTER_MODEL",
    _DEFAULT_SSOT.runtime.drafter.model if _DEFAULT_SSOT else "gemma3:1b",
)
DEFAULT_DRAFTER_FALLBACK_BACKEND = os.getenv(
    "TEV_ROUTE_DRAFTER_FALLBACK_BACKEND",
    _DEFAULT_SSOT.runtime.drafter.fallback_backend if _DEFAULT_SSOT else "ollama",
)
DEFAULT_DRAFTER_FALLBACK_MODEL = os.getenv(
    "TEV_ROUTE_DRAFTER_FALLBACK_MODEL",
    _DEFAULT_SSOT.runtime.drafter.fallback_model if _DEFAULT_SSOT else "llama3.2:1b",
)
DEFAULT_JUDGE_BACKEND = os.getenv(
    "TEV_ROUTE_JUDGE_BACKEND",
    _DEFAULT_SSOT.runtime.judge.backend if _DEFAULT_SSOT else "ollama",
)
DEFAULT_JUDGE_MODEL = os.getenv(
    "TEV_ROUTE_JUDGE_MODEL",
    _DEFAULT_SSOT.runtime.judge.model if _DEFAULT_SSOT else "llama3.2:3b",
)
DEFAULT_JUDGE_FALLBACK_BACKEND = os.getenv(
    "TEV_ROUTE_JUDGE_FALLBACK_BACKEND",
    _DEFAULT_SSOT.runtime.judge.fallback_backend if _DEFAULT_SSOT else "ollama",
)
DEFAULT_JUDGE_FALLBACK_MODEL = os.getenv(
    "TEV_ROUTE_JUDGE_FALLBACK_MODEL",
    _DEFAULT_SSOT.runtime.judge.fallback_model if _DEFAULT_SSOT else "gemma2:2b",
)

DEFAULT_OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    _DEFAULT_SSOT.runtime.security.ollama_url if _DEFAULT_SSOT else "http://127.0.0.1:11434/api/generate",
)
DEFAULT_ALLOW_REMOTE_OLLAMA = os.getenv(
    "TEV_ALLOW_REMOTE_OLLAMA",
    "1" if (_DEFAULT_SSOT and _DEFAULT_SSOT.runtime.security.allow_remote_ollama) else "0",
).strip() == "1"

DEFAULT_SINGLE_MODEL = os.getenv(
    "DEFAULT_SINGLE_MODEL",
    _DEFAULT_SSOT.runtime.evaluation.single_model
    if _DEFAULT_SSOT
    else "mlx://mlx-community/Apertus-8B-Instruct-2509-4bit",
)
DEFAULT_ENSEMBLE_MODELS = os.getenv(
    "DEFAULT_ENSEMBLE_MODELS",
    ",".join(_DEFAULT_SSOT.runtime.evaluation.ensemble_models)
    if _DEFAULT_SSOT
    else "ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b",
)
DEFAULT_INPUT_PATH = os.getenv("DEFAULT_INPUT_PATH", "samples/sample_germany.xlsx")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "de")
DEFAULT_REVIEW_MODE = os.getenv("DEFAULT_REVIEW_MODE", "partial")
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "500"))
DEFAULT_MAX_WORKERS = int(os.getenv("DEFAULT_MAX_WORKERS", "1"))
DEFAULT_PROGRESS_EVERY = int(os.getenv("DEFAULT_PROGRESS_EVERY", "10"))
