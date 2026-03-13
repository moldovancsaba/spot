from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple

from ..models import RunPolicy


def resolve_consensus(categories: List[str], policy: RunPolicy) -> Tuple[str, str, List[str], Dict[str, int]]:
    counts = Counter(categories)
    winner, winner_count = counts.most_common(1)[0]
    flags: List[str] = []

    if len(counts) == 1 and winner_count == 3:
        tier = "HIGH"
    elif winner_count == 2:
        tier = "MEDIUM"
        flags.append("DISAGREEMENT")
    else:
        tier = "LOW"
        flags.extend(["DISAGREEMENT", "HUMAN_REVIEW_REQUIRED"])

    if policy.disagreement_mode == "human_review" and tier != "HIGH":
        flags.append("REVIEW_REQUIRED")
    if policy.disagreement_mode == "fail" and tier == "LOW":
        flags.append("CONSENSUS_FAILURE")

    return winner, tier, sorted(set(flags)), dict(counts)
