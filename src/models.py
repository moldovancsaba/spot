from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from typing import Literal, List

CANONICAL_CATEGORIES = {
    "Anti-Israel",
    "Anti-Judaism",
    "Classical Antisemitism",
    "Structural Antisemitism",
    "Conspiracy Theories",
    "Not Antisemitic",
}


@dataclass(frozen=True)
class InputRow:
    row_index: int
    item_number: str
    post_text: str


@dataclass
class ClassificationResult:
    row_index: int
    raw_category: str
    category: str
    confidence: float
    explanation: str
    flags: List[str]
    resolved_model_version: str | None = None
    model_votes: Dict[str, str] | None = None
    consensus_tier: str | None = None
    minority_label: str | None = None
    drafted_text: str | None = None
    judge_score: float | None = None
    judge_verdict: str | None = None
    fallback_events: List[str] | None = None


@dataclass(frozen=True)
class Taxonomy:
    version: str
    categories: List[str]
    fallback_category: str


@dataclass(frozen=True)
class Policy:
    prompt_version: str
    model_version: str
    expected_columns: List[str]
    supported_languages: List[str]
    review_modes: List[str]
    low_confidence_threshold: float


@dataclass(frozen=True)
class LaneRoute:
    backend: str
    model: str
    fallback_backend: str
    fallback_model: str


@dataclass(frozen=True)
class EvaluationDefaults:
    single_model: str
    ensemble_models: List[str]


@dataclass(frozen=True)
class SecurityDefaults:
    ollama_url: str
    allow_remote_ollama: bool


@dataclass(frozen=True)
class RuntimeDefaults:
    classifier: LaneRoute
    drafter: LaneRoute
    judge: LaneRoute
    evaluation: EvaluationDefaults
    security: SecurityDefaults


@dataclass(frozen=True)
class SSOT:
    ssot_version: str
    taxonomy: Taxonomy
    policy: Policy
    runtime: RuntimeDefaults


@dataclass(frozen=True)
class RunPolicy:
    ensemble_enabled: bool
    ensemble_models: List[str]
    consensus_strategy: Literal["majority", "unanimous", "weighted"]
    disagreement_mode: Literal["flag", "fail", "human_review"]
