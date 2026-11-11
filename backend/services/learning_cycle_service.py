"""Continuous learning cycle for {spot}.

{spot} is not a one-shot classifier: every reviewed row is evidence, and the service must keep turning
that evidence into governed, auditable learning output without a human remembering to run a CLI command.

One cycle does four things and writes nothing outside `runs/<run>/learning/`:

1. **Feedback summary** - what humans decided (confirmed / false alarm / unresolved), by category, and how
   many rows are now eligible as training evidence.
2. **Drift measurement** - scores the run's canonical labels against the frozen reference
   (`docs/evaluation/goldset_2026-11-11.jsonl`) on the rows that overlap it, so quality is measured every
   cycle instead of once.
3. **Training bundle export** - hands eligible reviewed rows to the existing bounded
   `{trinity}` / `{train}` export seam, so learning material accumulates automatically.
4. **Cycle record** - an immutable report plus one line appended to `registry.jsonl`, so the sequence of
   cycles is itself auditable and later cycles can be compared with earlier ones.

The cycle never mutates classification state, never retrains, and never changes the governed contract. It
produces evidence; adopting a model or threshold remains an explicit, documented decision.
"""
from __future__ import annotations

import collections
import hashlib
import json
import time
from pathlib import Path
from typing import Any

CATEGORIES = [
    "Anti-Israel",
    "Anti-Judaism",
    "Classical Antisemitism",
    "Structural Antisemitism",
    "Conspiracy Theories",
    "Not Antisemitic",
]
DEFAULT_REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "goldset_2026-11-11.jsonl"


def _digest_reference(reference_path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not reference_path.is_file():
        return labels
    for line in reference_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("text_sha256") and row.get("label"):
                labels[row["text_sha256"]] = row["label"]
    return labels


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _macro_f1(pairs: list[tuple[str, str]]) -> tuple[float, dict[str, dict]]:
    tp: collections.Counter = collections.Counter()
    fp: collections.Counter = collections.Counter()
    fn: collections.Counter = collections.Counter()
    for gold, predicted in pairs:
        if predicted == gold:
            tp[gold] += 1
        else:
            fn[gold] += 1
            if predicted:
                fp[predicted] += 1
    per_class: dict[str, dict] = {}
    for category in CATEGORIES:
        precision = tp[category] / (tp[category] + fp[category]) if tp[category] + fp[category] else 0.0
        recall = tp[category] / (tp[category] + fn[category]) if tp[category] + fn[category] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[category] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp[category] + fn[category],
        }
    # Macro over classes actually present in this overlap. Averaging absent classes in would make a
    # single-row sample look catastrophic, which is a measurement artefact rather than drift.
    present = [entry for entry in per_class.values() if entry["support"]]
    macro = sum(entry["f1"] for entry in present) / len(present) if present else 0.0
    return round(macro, 4), per_class


def feedback_summary(*, run_id: str, rows: list[dict[str, Any]]) -> dict:
    outcomes: collections.Counter = collections.Counter()
    eligible: list[int] = []
    for row in rows:
        decision = row.get("review_decision")
        if decision in {"confirm", "adjust"}:
            outcomes[decision] += 1
            if not set(row.get("flags") or []) & {"ANALYSIS_FAILED", "TAXONOMY_VIOLATION"} and not row.get("fallback_events"):
                eligible.append(int(row["row_index"]))
        elif row.get("review_state") == "reviewed":
            outcomes["other_reviewed"] += 1
        else:
            outcomes["unreviewed"] += 1
    return {
        "run_id": run_id,
        "rows_total": len(rows),
        "decisions": dict(outcomes),
        "training_eligible_rows": len(eligible),
        "training_eligible_row_indices": eligible[:5000],
    }


def drift_measurement(*, rows: list[dict[str, Any]], reference: dict[str, str]) -> dict:
    pairs: list[tuple[str, str]] = []
    for row in rows:
        text = str(row.get("post_text") or "")
        if not text:
            continue
        expected = reference.get(_sha(text)) or reference.get(_sha(text.strip()))
        predicted = row.get("assigned_category")
        if expected and predicted:
            pairs.append((expected, str(predicted)))
    if not pairs:
        return {"rows_scored": 0, "note": "no canonical rows overlap the frozen reference"}
    agreement = sum(1 for gold, predicted in pairs if gold == predicted) / len(pairs)
    macro, per_class = _macro_f1(pairs)
    return {
        "rows_scored": len(pairs),
        "agreement_pct": round(100 * agreement, 2),
        "macro_f1": macro,
        "per_class": per_class,
    }


def run_learning_cycle(
    *,
    runs_dir: Path,
    run_id: str,
    output_dir: Path | None = None,
    reference_path: Path = DEFAULT_REFERENCE,
    company_id: str = "spot-local",
    export_bundles: bool = True,
) -> dict:
    from backend.services.ops_db_service import fetch_run_rows

    rows = fetch_run_rows(runs_dir=runs_dir, run_id=run_id)
    feedback = feedback_summary(run_id=run_id, rows=rows)
    drift = drift_measurement(rows=rows, reference=_digest_reference(reference_path))

    bundle: dict[str, Any] = {"exported": 0, "skipped": 0, "error": None}
    if export_bundles and feedback["training_eligible_row_indices"]:
        try:
            from src.trinity_spot_bundle import export_trinity_spot_training_bundles

            directory = (output_dir or (runs_dir / run_id / "learning")) / "bundles"
            directory.mkdir(parents=True, exist_ok=True)
            summary = export_trinity_spot_training_bundles(
                runs_dir=runs_dir,
                run_id=run_id,
                company_id=company_id,
                output_dir=directory,
                row_indices=feedback["training_eligible_row_indices"],
            )
            bundle = {"exported": summary.exported_count, "skipped": summary.skipped_count,
                      "error": None, "output_dir": str(directory)}
        except Exception as exc:  # noqa: BLE001 - a cycle must never fail the service
            bundle = {"exported": 0, "skipped": 0, "error": f"{type(exc).__name__}: {exc}"[:200]}

    directory = output_dir or (runs_dir / run_id / "learning")
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "cycle_id": f"{int(time.time())}-{run_id}",
        "created_at": int(time.time()),
        "reference": str(reference_path),
        "feedback": feedback,
        "drift": drift,
        "bundles": bundle,
        "policy": {
            "mutates_classification": False,
            "retrains": False,
            "changes_contract": False,
        },
    }
    (directory / "latest_cycle.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
    with (directory / "registry.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: record[k] for k in ("cycle_id", "created_at", "drift", "bundles")},
                            ensure_ascii=False) + "\n")
    return record


def list_cycles(*, runs_dir: Path, run_id: str, limit: int = 50) -> list[dict]:
    path = runs_dir / run_id / "learning" / "registry.jsonl"
    if not path.is_file():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines[-max(1, min(limit, 500)):]]


def runs_with_rows(*, runs_dir: Path, limit: int = 5) -> list[str]:
    """Most recent runs that actually carry canonical rows, newest first."""
    from backend.services.ops_db_service import _connect

    with _connect(runs_dir) as conn:
        rows = conn.execute(
            "SELECT r.run_id, COUNT(rr.row_index) AS n FROM runs r "
            "JOIN run_rows rr ON rr.run_id = r.run_id GROUP BY r.run_id "
            "ORDER BY COALESCE(r.created_at, 0) DESC LIMIT ?",
            (max(1, min(limit, 25)),),
        ).fetchall()
    return [row["run_id"] for row in rows if row["n"]]
