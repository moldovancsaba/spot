from __future__ import annotations

from dataclasses import dataclass

from .defaults import (
    DEFAULT_CLASSIFIER_BACKEND,
    DEFAULT_CLASSIFIER_FALLBACK_BACKEND,
    DEFAULT_CLASSIFIER_FALLBACK_MODEL,
    DEFAULT_CLASSIFIER_MODEL,
    DEFAULT_DRAFTER_BACKEND,
    DEFAULT_DRAFTER_FALLBACK_BACKEND,
    DEFAULT_DRAFTER_FALLBACK_MODEL,
    DEFAULT_DRAFTER_MODEL,
    DEFAULT_JUDGE_BACKEND,
    DEFAULT_JUDGE_FALLBACK_BACKEND,
    DEFAULT_JUDGE_FALLBACK_MODEL,
    DEFAULT_JUDGE_MODEL,
)


@dataclass(frozen=True)
class LaneConfig:
    classifier_backend: str
    classifier_model: str
    classifier_fallback_backend: str
    classifier_fallback_model: str
    drafter_backend: str
    drafter_model: str
    drafter_fallback_backend: str
    drafter_fallback_model: str
    judge_backend: str
    judge_model: str
    judge_fallback_backend: str
    judge_fallback_model: str


@dataclass(frozen=True)
class ModelRoute:
    backend: str
    model_name: str

    @property
    def spec(self) -> str:
        return f"{self.backend}://{self.model_name}"

    @property
    def version(self) -> str:
        return format_model_version(self.backend, self.model_name)


TASK_ROUTING = {
    "taxonomy_classify": "classifier",
    "classify_intent": "drafter",
    "extract_fields": "drafter",
    "context_pack": "drafter",
    "retrieval_query_build": "drafter",
    "edit_pattern_cluster": "drafter",
    "answer_score": "judge",
    "quality_gate": "judge",
}


def format_model_version(backend: str, model_name: str) -> str:
    return f"{backend}:{model_name}"


def parse_model_spec(spec: str, default_backend: str, default_model: str | None = None) -> ModelRoute:
    normalized = spec.strip()
    if not normalized:
        if default_model is None:
            raise ValueError("Model spec cannot be empty without a default model")
        return ModelRoute(default_backend, default_model)
    if "://" in normalized:
        backend, model_name = normalized.split("://", 1)
        backend = backend.strip()
        model_name = model_name.strip()
        if backend not in {"ollama", "mlx"}:
            raise ValueError(f"Unsupported backend '{backend}' in model spec '{spec}'")
        if not model_name:
            raise ValueError(f"Model spec '{spec}' is missing a model name")
        return ModelRoute(backend, model_name)
    if default_backend == "mlx" and ":" in normalized:
        # Preserve historical Ollama tags such as qwen2.5:7b when MLX is the primary classifier runtime.
        return ModelRoute("ollama", normalized)
    return ModelRoute(default_backend, normalized)


def load_lane_config() -> LaneConfig:
    return LaneConfig(
        classifier_backend=DEFAULT_CLASSIFIER_BACKEND,
        classifier_model=DEFAULT_CLASSIFIER_MODEL,
        classifier_fallback_backend=DEFAULT_CLASSIFIER_FALLBACK_BACKEND,
        classifier_fallback_model=DEFAULT_CLASSIFIER_FALLBACK_MODEL,
        drafter_backend=DEFAULT_DRAFTER_BACKEND,
        drafter_model=DEFAULT_DRAFTER_MODEL,
        drafter_fallback_backend=DEFAULT_DRAFTER_FALLBACK_BACKEND,
        drafter_fallback_model=DEFAULT_DRAFTER_FALLBACK_MODEL,
        judge_backend=DEFAULT_JUDGE_BACKEND,
        judge_model=DEFAULT_JUDGE_MODEL,
        judge_fallback_backend=DEFAULT_JUDGE_FALLBACK_BACKEND,
        judge_fallback_model=DEFAULT_JUDGE_FALLBACK_MODEL,
    )
