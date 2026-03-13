from __future__ import annotations

import json
from pathlib import Path

from .models import (
    CANONICAL_CATEGORIES,
    EvaluationDefaults,
    LaneRoute,
    Policy,
    RuntimeDefaults,
    SSOT,
    SecurityDefaults,
    Taxonomy,
)


class SSOTError(RuntimeError):
    pass


SUPPORTED_BACKENDS = {"ollama", "mlx"}


def _build_lane_route(raw: dict, lane_name: str) -> LaneRoute:
    try:
        route = LaneRoute(
            backend=str(raw["backend"]).strip(),
            model=str(raw["model"]).strip(),
            fallback_backend=str(raw["fallback_backend"]).strip(),
            fallback_model=str(raw["fallback_model"]).strip(),
        )
    except Exception as exc:  # noqa: BLE001
        raise SSOTError(f"Runtime route '{lane_name}' is missing required keys: {exc}") from exc

    if route.backend not in SUPPORTED_BACKENDS:
        raise SSOTError(f"Runtime route '{lane_name}' backend must be one of {sorted(SUPPORTED_BACKENDS)}")
    if route.fallback_backend not in SUPPORTED_BACKENDS:
        raise SSOTError(
            f"Runtime route '{lane_name}' fallback_backend must be one of {sorted(SUPPORTED_BACKENDS)}"
        )
    if not route.model:
        raise SSOTError(f"Runtime route '{lane_name}' model cannot be empty")
    if not route.fallback_model:
        raise SSOTError(f"Runtime route '{lane_name}' fallback_model cannot be empty")
    return route


def load_ssot(path: Path) -> SSOT:
    if not path.exists():
        raise SSOTError(f"SSOT not found at {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SSOTError(f"Invalid SSOT JSON: {exc}") from exc

    try:
        taxonomy = raw["taxonomy"]
        policy = raw["policy"]
        runtime = raw["runtime"]
        ssot = SSOT(
            ssot_version=str(raw["ssot_version"]),
            taxonomy=Taxonomy(
                version=str(taxonomy["version"]),
                categories=list(taxonomy["categories"]),
                fallback_category=str(taxonomy["fallback_category"]),
            ),
            policy=Policy(
                prompt_version=str(policy["prompt_version"]),
                model_version=str(policy["model_version"]),
                expected_columns=list(policy["expected_columns"]),
                supported_languages=list(policy["supported_languages"]),
                review_modes=list(policy["review_modes"]),
                low_confidence_threshold=float(policy["low_confidence_threshold"]),
            ),
            runtime=RuntimeDefaults(
                classifier=_build_lane_route(runtime["classifier"], "classifier"),
                drafter=_build_lane_route(runtime["drafter"], "drafter"),
                judge=_build_lane_route(runtime["judge"], "judge"),
                evaluation=EvaluationDefaults(
                    single_model=str(runtime["evaluation"]["single_model"]).strip(),
                    ensemble_models=[str(model).strip() for model in runtime["evaluation"]["ensemble_models"]],
                ),
                security=SecurityDefaults(
                    ollama_url=str(runtime["security"]["ollama_url"]).strip(),
                    allow_remote_ollama=bool(runtime["security"]["allow_remote_ollama"]),
                ),
            ),
        )
    except KeyError as exc:
        raise SSOTError(f"SSOT missing required keys: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise SSOTError(f"SSOT parse failure: {exc}") from exc

    if ssot.taxonomy.fallback_category != "Not Antisemitic":
        raise SSOTError("SSOT fallback_category must be 'Not Antisemitic' for MVP")
    if ssot.taxonomy.fallback_category not in ssot.taxonomy.categories:
        raise SSOTError("Fallback category must exist in taxonomy categories")
    if not ssot.taxonomy.categories:
        raise SSOTError("Taxonomy categories cannot be empty")

    required_modes = {"full", "partial", "none"}
    if not required_modes.issubset(set(ssot.policy.review_modes)):
        raise SSOTError("review_modes must include full, partial, none")
    if set(ssot.taxonomy.categories) != CANONICAL_CATEGORIES:
        raise SSOTError(
            "SSOT taxonomy must exactly match canonical closed set for MVP integrity enforcement"
        )
    if ssot.policy.model_version != f"{ssot.runtime.classifier.backend}:{ssot.runtime.classifier.model}":
        raise SSOTError("policy.model_version must match the primary classifier route in runtime.classifier")
    if not ssot.runtime.evaluation.single_model:
        raise SSOTError("runtime.evaluation.single_model cannot be empty")
    if len(ssot.runtime.evaluation.ensemble_models) != 3:
        raise SSOTError("runtime.evaluation.ensemble_models must contain exactly 3 models")
    if not ssot.runtime.security.ollama_url:
        raise SSOTError("runtime.security.ollama_url cannot be empty")

    return ssot
