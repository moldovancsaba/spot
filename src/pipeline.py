from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from collections import Counter
from pathlib import Path
from threading import Lock
from typing import Optional

from . import PIPELINE_VERSION
from .classifier import classify_batch, get_inference_parameters
from .classifier import stable_row_hash
from .defaults import DEFAULT_LOCKED_SSOT_PATH, DEFAULT_PRODUCTION_MODE
from .ensemble.ensemble_runner import run_ensemble_batch
from .excel_io import (
    extract_assigned_categories,
    read_input_rows,
    validate_no_null_assigned_category,
    write_output,
)
from .models import CANONICAL_CATEGORIES, ClassificationResult, RunPolicy
from .ssot_loader import SSOTError, load_ssot
from .lanes import TASK_ROUTING, format_model_version, load_lane_config, parse_model_spec
from backend.services.artifact_manifest_service import write_artifact_manifest


class ConfigError(RuntimeError):
    pass


STATE_PROGRESS = {
    "PENDING": 0,
    "VALIDATING": 10,
    "PROCESSING": 60,
    "WRITING": 90,
    "COMPLETED": 100,
    "FAILED": 100,
}


def _language_allowed(run_language: str, supported_languages: list[str]) -> bool:
    language = str(run_language).strip()
    if not language:
        return False
    allowed = {str(item).strip() for item in supported_languages if str(item).strip()}
    if "*" in allowed:
        return True
    return language in allowed


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _git_commit_hash() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def _write_progress(
    run_dir: Path,
    run_id: str,
    state: str,
    message: str = "",
    started_at: str | None = None,
    completed_at: str | None = None,
    total_rows: int | None = None,
    processed_rows: int | None = None,
) -> None:
    progress_percentage = STATE_PROGRESS.get(state, 0)
    if state == "PROCESSING" and total_rows and processed_rows is not None:
        # Persist lifecycle-stage progress into the [10..90] processing window for run artifacts.
        # Operator-facing dashboards should use row-based progress metrics instead of this staged value.
        stage_ratio = max(0.0, min(1.0, processed_rows / total_rows))
        progress_percentage = round(10 + (stage_ratio * 80), 1)

    run_dir.mkdir(parents=True, exist_ok=True)
    progress = {
        "run_id": run_id,
        "state": state,
        "message": message,
        "started_at": started_at,
        "completed_at": completed_at,
        "total_rows": total_rows,
        "processed_rows": processed_rows,
        "progress_percentage": progress_percentage,
    }
    (run_dir / "progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    with (run_dir / "logs.txt").open("a", encoding="utf-8") as f:
        f.write(f"[{state}] {message}\n")


def _write_processing_stats(
    *,
    run_dir: Path,
    run_id: str,
    started_at: str,
    total_rows: int,
    processed_rows: int,
    threat_rows: int,
    review_required_rows: int,
    judged_rows: int,
    second_pass_candidates: int | None = None,
    second_pass_completed: int | None = None,
    second_pass_overrides: int | None = None,
) -> None:
    started_dt = datetime.fromisoformat(started_at)
    now_dt = datetime.now(UTC)
    elapsed_seconds = max((now_dt - started_dt).total_seconds(), 0.0)
    avg_seconds_per_row = round(elapsed_seconds / processed_rows, 4) if processed_rows > 0 else None
    threat_rate = round(threat_rows / processed_rows, 4) if processed_rows > 0 else 0.0
    projected_threat_rows = int(round(threat_rate * total_rows)) if processed_rows > 0 and total_rows > 0 else None
    payload = {
        "run_id": run_id,
        "started_at": started_at,
        "updated_at": now_dt.isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "processed_rows": processed_rows,
        "total_rows": total_rows,
        "avg_seconds_per_row": avg_seconds_per_row,
        "threat_rows_detected": threat_rows,
        "threat_rate": threat_rate,
        "projected_threat_rows": projected_threat_rows,
        "review_required_rows_detected": review_required_rows,
        "judged_rows": judged_rows,
        "second_pass_candidates": second_pass_candidates,
        "second_pass_completed": second_pass_completed,
        "second_pass_overrides": second_pass_overrides,
    }
    (run_dir / "processing_stats.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_integrity_report(
    run_dir: Path,
    run_id: str,
    timestamp: str,
    ssot,
    review_mode: str,
    run_language: str,
    total_rows: int,
    processed_rows: int,
    results,
    schema_warnings,
    canonical_set_validation_passed: bool,
    canonical_set_exact_match: bool,
    code_version: str,
    model_specs,
    model_versions,
    per_model_distribution,
    consensus_distribution,
    consensus_tier_summary,
) -> None:
    cat_dist = Counter(r.category for r in results)
    flag_dist = Counter(flag for r in results for flag in r.flags)
    resolved_routes = [parse_model_spec(spec, load_lane_config().classifier_backend) for spec in model_specs]
    primary_route = resolved_routes[0]
    inference_parameters = [
        get_inference_parameters(model_name=route.model_name, backend=route.backend) for route in resolved_routes
    ]
    resolved_policy = {
        "review_mode": review_mode,
        "run_language": run_language,
        "low_confidence_threshold": ssot.policy.low_confidence_threshold,
    }
    report = {
        "run_id": run_id,
        "timestamp": timestamp,
        "ssot_version": ssot.ssot_version,
        "policy_profile": ssot.policy.prompt_version,
        "resolved_policy": resolved_policy,
        "task_routing": TASK_ROUTING,
        "lane_config": load_lane_config().__dict__,
        "model_name": primary_route.model_name,
        "model_version": primary_route.version,
        "configured_primary_model_version": ssot.policy.model_version,
        "inference_parameters": inference_parameters,
        "code_version": code_version,
        "model_specs": model_specs,
        "resolved_model_versions": model_versions,
        "total_rows": total_rows,
        "total_processed": processed_rows,
        "category_distribution": dict(cat_dist),
        "per_model_distribution": per_model_distribution,
        "consensus_distribution": consensus_distribution,
        "consensus_confidence_summary": consensus_tier_summary,
        "disagreement_count": flag_dist.get("DISAGREEMENT", 0),
        "fallback_event_count": sum(len(r.fallback_events or []) for r in results),
        "soft_signal_row_count": sum(1 for r in results if (r.soft_signal_flags or []) or (r.soft_signal_score or 0) > 0),
        "soft_signal_flag_distribution": dict(
            Counter(flag for r in results for flag in (r.soft_signal_flags or []))
        ),
        "minority_report_count": sum(1 for r in results if r.minority_label),
        "taxonomy_violation_count": flag_dist.get("TAXONOMY_VIOLATION", 0),
        "empty_text_count": flag_dist.get("EMPTY_TEXT", 0),
        "empty_category_recovered_count": flag_dist.get("EMPTY_CATEGORY_RECOVERED", 0),
        "skipped_count": flag_dist.get("SKIPPED", 0),
        "low_confidence_count": flag_dist.get("LOW_CONFIDENCE", 0),
        "schema_warnings": schema_warnings,
        "canonical_set_validation_passed": canonical_set_validation_passed,
        "canonical_set_exact_match": canonical_set_exact_match,
    }
    (run_dir / "integrity_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _validate_production_model_policy(
    *,
    ssot,
    model_specs: list[str],
    ensemble_enabled: bool,
) -> None:
    if not DEFAULT_PRODUCTION_MODE:
        return

    allowed_single_specs = {
        f"{ssot.runtime.classifier.backend}://{ssot.runtime.classifier.model}",
        f"{ssot.runtime.classifier.fallback_backend}://{ssot.runtime.classifier.fallback_model}",
    }
    allowed_ensemble_specs = set(ssot.runtime.evaluation.ensemble_models)

    if ensemble_enabled:
        if set(model_specs) != allowed_ensemble_specs:
            raise ConfigError(
                "Production mode only allows the SSOT-defined ensemble model set for disagreement paths and evaluation."
            )
        return

    if len(model_specs) != 1 or model_specs[0] not in allowed_single_specs:
        raise ConfigError("Production mode only allows the SSOT-defined classifier primary or fallback route.")


def _validate_production_lane_policy(*, ssot, lane_config) -> None:
    if not DEFAULT_PRODUCTION_MODE:
        return
    expected = {
        "classifier_backend": ssot.runtime.classifier.backend,
        "classifier_model": ssot.runtime.classifier.model,
        "classifier_fallback_backend": ssot.runtime.classifier.fallback_backend,
        "classifier_fallback_model": ssot.runtime.classifier.fallback_model,
        "drafter_backend": ssot.runtime.drafter.backend,
        "drafter_model": ssot.runtime.drafter.model,
        "drafter_fallback_backend": ssot.runtime.drafter.fallback_backend,
        "drafter_fallback_model": ssot.runtime.drafter.fallback_model,
        "judge_backend": ssot.runtime.judge.backend,
        "judge_model": ssot.runtime.judge.model,
        "judge_fallback_backend": ssot.runtime.judge.fallback_backend,
        "judge_fallback_model": ssot.runtime.judge.fallback_model,
    }
    actual = lane_config.__dict__
    mismatches = sorted(key for key, value in expected.items() if actual.get(key) != value)
    if mismatches:
        raise ConfigError(f"Production mode requires SSOT-aligned lane routing. Mismatched keys: {mismatches}")


def _validate_production_ssot_path(ssot_path: Path) -> None:
    if not DEFAULT_PRODUCTION_MODE:
        return
    locked_path = Path(DEFAULT_LOCKED_SSOT_PATH).resolve()
    if ssot_path.resolve() != locked_path:
        raise ConfigError(f"Production mode requires the locked SSOT path: {locked_path}")


def _write_disagreement_report(run_dir: Path, results, row_hashes: list[str]) -> None:
    disagreements = []
    for result, row_hash in zip(results, row_hashes, strict=False):
        if result.consensus_tier not in {"MEDIUM", "LOW"}:
            continue
        disagreements.append(
            {
                "row_index": result.row_index,
                "row_hash": row_hash,
                "final_category": result.category,
                "consensus_tier": result.consensus_tier,
                "minority_label": result.minority_label,
                "model_votes": result.model_votes or {},
                "judge_score": result.judge_score,
                "judge_verdict": result.judge_verdict,
                "fallback_events": sorted(set(result.fallback_events or [])),
                "flags": sorted(set(result.flags)),
            }
        )

    if disagreements:
        (run_dir / "disagreement_report.json").write_text(
            json.dumps({"rows": disagreements}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_artifact_manifest(run_dir: Path) -> None:
    write_artifact_manifest(run_dir=run_dir, sha256_file=_sha256_file)


def _serialize_result(result: ClassificationResult) -> dict:
    return {
        "row_index": result.row_index,
        "raw_category": result.raw_category,
        "category": result.category,
        "confidence": result.confidence,
        "explanation": result.explanation,
        "flags": list(result.flags),
        "soft_signal_score": result.soft_signal_score,
        "soft_signal_flags": list(result.soft_signal_flags or []),
        "soft_signal_evidence": list(result.soft_signal_evidence or []),
        "resolved_model_version": result.resolved_model_version,
        "model_votes": dict(result.model_votes or {}),
        "consensus_tier": result.consensus_tier,
        "minority_label": result.minority_label,
        "drafted_text": result.drafted_text,
        "judge_score": result.judge_score,
        "judge_verdict": result.judge_verdict,
        "fallback_events": list(result.fallback_events or []),
    }


def _deserialize_result(payload: dict) -> ClassificationResult:
    return ClassificationResult(
        row_index=int(payload["row_index"]),
        raw_category=str(payload.get("raw_category") or ""),
        category=str(payload.get("category") or ""),
        confidence=float(payload.get("confidence") or 0.0),
        explanation=str(payload.get("explanation") or ""),
        flags=[str(item) for item in payload.get("flags", [])],
        soft_signal_score=(float(payload["soft_signal_score"]) if payload.get("soft_signal_score") is not None else None),
        soft_signal_flags=[str(item) for item in payload.get("soft_signal_flags", [])],
        soft_signal_evidence=[str(item) for item in payload.get("soft_signal_evidence", [])],
        resolved_model_version=(str(payload["resolved_model_version"]) if payload.get("resolved_model_version") else None),
        model_votes={str(key): str(value) for key, value in dict(payload.get("model_votes") or {}).items()} or None,
        consensus_tier=(str(payload["consensus_tier"]) if payload.get("consensus_tier") else None),
        minority_label=(str(payload["minority_label"]) if payload.get("minority_label") else None),
        drafted_text=(str(payload["drafted_text"]) if payload.get("drafted_text") is not None else None),
        judge_score=(float(payload["judge_score"]) if payload.get("judge_score") is not None else None),
        judge_verdict=(str(payload["judge_verdict"]) if payload.get("judge_verdict") else None),
        fallback_events=[str(item) for item in payload.get("fallback_events", [])] or None,
    )


def _append_result_checkpoint(checkpoint_path: Path, *, result_index: int, row_hash: str, result: ClassificationResult) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "result_index": result_index,
                    "row_hash": row_hash,
                    "result": _serialize_result(result),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _persist_canonical_run_row(
    *,
    canonical_runs_dir: Path | None,
    canonical_run_id: str | None,
    canonical_upload_id: str | None,
    canonical_attempt_id: str | None,
    result: ClassificationResult,
    row_hash: str,
) -> None:
    if canonical_runs_dir is None or not canonical_run_id:
        return
    from backend.services.ops_db_service import upsert_run_rows

    upsert_run_rows(
        runs_dir=canonical_runs_dir,
        run_id=canonical_run_id,
        upload_id=canonical_upload_id,
        attempt_id=canonical_attempt_id,
        rows=[
            {
                "row_index": result.row_index,
                "row_hash": row_hash,
                "assigned_category": result.category,
                "confidence_score": result.confidence,
                "explanation": result.explanation,
                "flags": list(result.flags),
                "fallback_events": list(result.fallback_events or []),
                "soft_signal_score": result.soft_signal_score,
                "soft_signal_flags": list(result.soft_signal_flags or []),
                "soft_signal_evidence": list(result.soft_signal_evidence or []),
                "judge_score": result.judge_score,
                "judge_verdict": result.judge_verdict,
                "consensus_tier": result.consensus_tier,
                "minority_label": result.minority_label,
                "model_votes": dict(result.model_votes or {}),
                "drafted_text": result.drafted_text,
                "review_required": "REVIEW_REQUIRED" in (result.flags or []),
            }
        ],
    )


def _load_result_checkpoint(checkpoint_path: Path, expected_row_hashes: list[str]) -> dict[int, ClassificationResult]:
    completed: dict[int, ClassificationResult] = {}
    if not checkpoint_path.exists():
        return completed
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            result_index = int(payload.get("result_index"))
        except Exception:
            continue
        if result_index < 0 or result_index >= len(expected_row_hashes):
            continue
        if str(payload.get("row_hash") or "") != expected_row_hashes[result_index]:
            continue
        result_payload = payload.get("result")
        if not isinstance(result_payload, dict):
            continue
        try:
            completed[result_index] = _deserialize_result(result_payload)
        except Exception:
            continue
    return completed


def _load_committed_canonical_results(
    *,
    canonical_runs_dir: Path | None,
    canonical_run_id: str | None,
    row_hashes: list[str],
    rows: list[InputRow],
) -> dict[int, ClassificationResult]:
    if canonical_runs_dir is None or not canonical_run_id:
        return {}
    from backend.services.ops_db_service import fetch_run_rows

    committed_by_row_index = {
        int(row.get("row_index") or 0): row
        for row in fetch_run_rows(runs_dir=canonical_runs_dir, run_id=canonical_run_id)
    }
    restored: dict[int, ClassificationResult] = {}
    for idx, input_row in enumerate(rows):
        committed = committed_by_row_index.get(int(input_row.row_index))
        if not committed:
            continue
        committed_hash = str(committed.get("row_hash") or "")
        if committed_hash and committed_hash != row_hashes[idx]:
            continue
        assigned_category = str(committed.get("assigned_category") or "")
        if not assigned_category:
            continue
        restored[idx] = ClassificationResult(
            row_index=int(committed.get("row_index") or input_row.row_index),
            raw_category=assigned_category,
            category=assigned_category,
            confidence=float(committed.get("confidence_score") or 0.0),
            explanation=str(committed.get("explanation") or ""),
            flags=[str(item) for item in committed.get("flags") or []],
            soft_signal_score=committed.get("soft_signal_score"),
            soft_signal_flags=[str(item) for item in committed.get("soft_signal_flags") or []],
            soft_signal_evidence=[str(item) for item in committed.get("soft_signal_evidence") or []],
            resolved_model_version=None,
            model_votes=dict(committed.get("model_votes") or {}) or None,
            consensus_tier=(str(committed.get("consensus_tier")) if committed.get("consensus_tier") else None),
            minority_label=(str(committed.get("minority_label")) if committed.get("minority_label") else None),
            drafted_text=(str(committed.get("drafted_text")) if committed.get("drafted_text") is not None else None),
            judge_score=(float(committed["judge_score"]) if committed.get("judge_score") is not None else None),
            judge_verdict=(str(committed.get("judge_verdict")) if committed.get("judge_verdict") else None),
            fallback_events=[str(item) for item in committed.get("fallback_events") or []] or None,
        )
    return restored


def run_classification(
    input_path: Path,
    output_path: Path,
    run_id: str,
    run_language: str,
    review_mode: str,
    ssot_path: Path,
    runs_dir: Path,
    max_workers: int = 4,
    limit: Optional[int] = None,
    ensemble_enabled: bool = False,
    ensemble_models: Optional[list[str]] = None,
    consensus_strategy: str = "majority",
    disagreement_mode: str = "human_review",
    progress_every: int = 100,
    resume_existing: bool = False,
    canonical_runs_dir: Path | None = None,
    canonical_run_id: str | None = None,
    canonical_upload_id: str | None = None,
    canonical_attempt_id: str | None = None,
    canonical_segment_id: str | None = None,
) -> None:
    run_dir = runs_dir / run_id
    started_at = _now_iso()
    completed_at: str | None = None
    total_rows = 0
    processing_stats = {
        "threat_rows": 0,
        "review_required_rows": 0,
        "judged_rows": 0,
        "second_pass_candidates": 0,
        "second_pass_completed": 0,
        "second_pass_overrides": 0,
    }
    processing_stats_lock = Lock()
    completed_rows_counter = 0
    try:
        _write_progress(run_dir, run_id, "PENDING", started_at=started_at)
        _write_progress(run_dir, run_id, "VALIDATING", started_at=started_at)
        _validate_production_ssot_path(ssot_path)
        ssot = load_ssot(ssot_path)

        if review_mode not in ssot.policy.review_modes:
            raise ConfigError(
                f"Invalid review_mode '{review_mode}'. Expected one of: {ssot.policy.review_modes}"
            )
        if not _language_allowed(run_language, ssot.policy.supported_languages):
            raise ConfigError(
                f"Invalid run_language '{run_language}'. Expected one of: {ssot.policy.supported_languages}"
            )

        rows = read_input_rows(input_path, ssot)
        total_rows = len(rows)
        if limit is not None:
            rows = rows[:limit]
            total_rows = len(rows)

        if not rows:
            raise SSOTError("No rows available after filtering.")

        row_hashes = [stable_row_hash(row.item_number, row.post_text) for row in rows]
        checkpoint_path = run_dir / "result_checkpoint.jsonl"
        results: list[ClassificationResult | None] = [None] * total_rows
        if resume_existing:
            committed_results = _load_committed_canonical_results(
                canonical_runs_dir=canonical_runs_dir,
                canonical_run_id=canonical_run_id,
                row_hashes=row_hashes,
                rows=rows,
            )
            for idx, result in committed_results.items():
                results[idx] = result
            checkpoint_results = _load_result_checkpoint(checkpoint_path, row_hashes)
            for idx, result in checkpoint_results.items():
                if results[idx] is not None:
                    continue
                results[idx] = result
                _persist_canonical_run_row(
                    canonical_runs_dir=canonical_runs_dir,
                    canonical_run_id=canonical_run_id,
                    canonical_upload_id=canonical_upload_id,
                    canonical_attempt_id=canonical_attempt_id,
                    result=result,
                    row_hash=row_hashes[idx],
                )
        completed_rows_counter = sum(1 for result in results if result is not None)
        if canonical_runs_dir is not None and canonical_segment_id and completed_rows_counter > 0:
            from backend.services.ops_db_service import update_segment_progress

            update_segment_progress(
                runs_dir=canonical_runs_dir,
                segment_id=canonical_segment_id,
                processed_rows=completed_rows_counter,
            )
        for result in [result for result in results if result is not None]:
            processing_stats["threat_rows"] += 1 if result.category != "Not Antisemitic" else 0
            processing_stats["review_required_rows"] += 1 if "REVIEW_REQUIRED" in (result.flags or []) else 0
            processing_stats["judged_rows"] += 1 if result.judge_verdict or result.judge_score is not None else 0
            processing_stats["second_pass_candidates"] += 1 if any(
                flag in (result.flags or [])
                for flag in ["SECOND_PASS_RECHECK", "SECOND_PASS_CONFIRMED", "SECOND_PASS_DISAGREEMENT", "SECOND_PASS_UNAVAILABLE"]
            ) else 0
            processing_stats["second_pass_completed"] += 1 if any(
                flag in (result.flags or [])
                for flag in ["SECOND_PASS_CONFIRMED", "SECOND_PASS_DISAGREEMENT"]
            ) else 0
            processing_stats["second_pass_overrides"] += 1 if "SECOND_PASS_CATEGORY_OVERRIDDEN" in (result.flags or []) else 0

        _write_progress(
            run_dir,
            run_id,
            "PROCESSING",
            started_at=started_at,
            total_rows=total_rows,
            processed_rows=completed_rows_counter,
        )
        _write_processing_stats(
            run_dir=run_dir,
            run_id=run_id,
            started_at=started_at,
            total_rows=total_rows,
            processed_rows=completed_rows_counter,
            threat_rows=int(processing_stats["threat_rows"]),
            review_required_rows=int(processing_stats["review_required_rows"]),
            judged_rows=int(processing_stats["judged_rows"]),
            second_pass_candidates=int(processing_stats["second_pass_candidates"]),
            second_pass_completed=int(processing_stats["second_pass_completed"]),
            second_pass_overrides=int(processing_stats["second_pass_overrides"]),
        )

        remaining_indices = [idx for idx, result in enumerate(results) if result is None]
        remaining_rows = [rows[idx] for idx in remaining_indices]

        def _row_completed(done: int, total: int, local_idx: int, latest_result, row_hash: str) -> None:
            nonlocal completed_rows_counter
            global_idx = remaining_indices[local_idx]
            with processing_stats_lock:
                results[global_idx] = latest_result
                completed_rows_counter += 1
                _append_result_checkpoint(checkpoint_path, result_index=global_idx, row_hash=row_hash, result=latest_result)
                _persist_canonical_run_row(
                    canonical_runs_dir=canonical_runs_dir,
                    canonical_run_id=canonical_run_id,
                    canonical_upload_id=canonical_upload_id,
                    canonical_attempt_id=canonical_attempt_id,
                    result=latest_result,
                    row_hash=row_hash,
                )
                if latest_result.category != "Not Antisemitic":
                    processing_stats["threat_rows"] += 1
                if "REVIEW_REQUIRED" in (latest_result.flags or []):
                    processing_stats["review_required_rows"] += 1
                if latest_result.judge_verdict or latest_result.judge_score is not None:
                    processing_stats["judged_rows"] += 1
                if any(
                    flag in (latest_result.flags or [])
                    for flag in ["SECOND_PASS_RECHECK", "SECOND_PASS_CONFIRMED", "SECOND_PASS_DISAGREEMENT", "SECOND_PASS_UNAVAILABLE"]
                ):
                    processing_stats["second_pass_candidates"] += 1
                if any(flag in (latest_result.flags or []) for flag in ["SECOND_PASS_CONFIRMED", "SECOND_PASS_DISAGREEMENT"]):
                    processing_stats["second_pass_completed"] += 1
                if "SECOND_PASS_CATEGORY_OVERRIDDEN" in (latest_result.flags or []):
                    processing_stats["second_pass_overrides"] += 1
                if canonical_runs_dir is not None and canonical_segment_id:
                    from backend.services.ops_db_service import update_segment_progress

                    update_segment_progress(
                        runs_dir=canonical_runs_dir,
                        segment_id=canonical_segment_id,
                        processed_rows=completed_rows_counter,
                    )
            _write_progress(
                run_dir,
                run_id,
                "PROCESSING",
                message=f"Processed {completed_rows_counter}/{total_rows} rows",
                started_at=started_at,
                total_rows=total_rows,
                processed_rows=completed_rows_counter,
            )
            with processing_stats_lock:
                _write_processing_stats(
                    run_dir=run_dir,
                    run_id=run_id,
                    started_at=started_at,
                    total_rows=total_rows,
                    processed_rows=completed_rows_counter,
                    threat_rows=int(processing_stats["threat_rows"]),
                    review_required_rows=int(processing_stats["review_required_rows"]),
                    judged_rows=int(processing_stats["judged_rows"]),
                    second_pass_candidates=int(processing_stats["second_pass_candidates"]),
                    second_pass_completed=int(processing_stats["second_pass_completed"]),
                    second_pass_overrides=int(processing_stats["second_pass_overrides"]),
                )
        lane_config = load_lane_config()
        _validate_production_lane_policy(ssot=ssot, lane_config=lane_config)
        requested_model_specs = (
            ensemble_models
            if (ensemble_enabled and ensemble_models)
            else [f"{lane_config.classifier_backend}://{lane_config.classifier_model}"]
        )
        resolved_model_routes = [
            parse_model_spec(spec, lane_config.classifier_backend, lane_config.classifier_model)
            for spec in requested_model_specs
        ]
        model_specs = [route.spec for route in resolved_model_routes]
        model_versions = [route.version for route in resolved_model_routes]
        _validate_production_model_policy(
            ssot=ssot,
            model_specs=model_specs,
            ensemble_enabled=ensemble_enabled,
        )
        run_policy = RunPolicy(
            ensemble_enabled=ensemble_enabled,
            ensemble_models=model_specs,
            consensus_strategy=consensus_strategy,  # type: ignore[arg-type]
            disagreement_mode=disagreement_mode,  # type: ignore[arg-type]
        )
        if run_policy.ensemble_enabled:
            if len(run_policy.ensemble_models) != 3:
                raise ConfigError("Ensemble mode requires exactly 3 local models for MVP consensus.")
            if run_policy.consensus_strategy != "majority":
                raise ConfigError("MVP ensemble supports consensus_strategy='majority' only.")
            per_model_distribution: dict = {}
            consensus_distribution: dict = {}
            consensus_tier_summary: dict = {}
            if remaining_rows:
                (
                    remaining_results,
                    _remaining_hashes,
                    per_model_distribution,
                    consensus_distribution,
                    consensus_tier_summary,
                ) = run_ensemble_batch(
                    rows=remaining_rows,
                    ssot=ssot,
                    review_mode=review_mode,
                    max_workers=max_workers,
                    run_policy=run_policy,
                    row_completion_callback=_row_completed,
                    progress_callback=None,
                    progress_every=progress_every,
                )
                for local_idx, result in enumerate(remaining_results):
                    results[remaining_indices[local_idx]] = result
            else:
                existing_results = [result for result in results if result is not None]
                per_model_distribution = {}
                consensus_distribution = dict(Counter(r.category for r in existing_results))
                consensus_tier_summary = dict(Counter((r.consensus_tier or "HIGH") for r in existing_results))
        else:
            if remaining_rows:
                remaining_results, _remaining_hashes = classify_batch(
                    remaining_rows,
                    ssot,
                    max_workers=max_workers,
                    review_mode=review_mode,
                    model_name=run_policy.ensemble_models[0],
                    row_completion_callback=_row_completed,
                    progress_callback=None,
                    progress_every=progress_every,
                )
                for local_idx, result in enumerate(remaining_results):
                    results[remaining_indices[local_idx]] = result
            final_results = [result for result in results if result is not None]
            per_model_distribution = {model_versions[0]: dict(Counter(r.category for r in final_results))}
            consensus_distribution = dict(Counter(r.category for r in final_results))
            consensus_tier_summary = dict(Counter((r.consensus_tier or "HIGH") for r in final_results))

        if any(result is None for result in results):
            missing = [idx for idx, result in enumerate(results) if result is None][:10]
            raise RuntimeError(f"Missing final classification results for rows: {missing}")
        results = [result for result in results if result is not None]

        # Hard guardrail: exactly one valid canonical category per row.
        for r in results:
            if r.consensus_tier is None:
                r.consensus_tier = "HIGH"
            if r.model_votes is None:
                primary_model = model_versions[0] if model_versions else ssot.policy.model_version
                r.model_votes = {primary_model: r.category}
            if not r.category:
                r.category = "Not Antisemitic"
                r.flags = sorted(set(r.flags + ["EMPTY_CATEGORY_RECOVERED"]))
            if r.category not in CANONICAL_CATEGORIES:
                r.category = "Not Antisemitic"
                r.flags = sorted(set(r.flags + ["TAXONOMY_VIOLATION"]))
            if r.category not in CANONICAL_CATEGORIES:
                raise RuntimeError(f"Final category assertion failed on row {r.row_index}: {r.category}")

        _write_progress(run_dir, run_id, "WRITING", started_at=started_at, total_rows=total_rows)
        write_output(
            input_path=input_path,
            output_path=output_path,
            ssot=ssot,
            run_id=run_id,
            run_language=run_language,
            review_mode=review_mode,
            pipeline_version=PIPELINE_VERSION,
            results=results,
            row_hashes=row_hashes,
        )
        validate_no_null_assigned_category(output_path, expected_rows=[r.row_index for r in results])
        detected_categories = extract_assigned_categories(output_path, expected_rows=[r.row_index for r in results])
        canonical_set_validation_passed = detected_categories.issubset(CANONICAL_CATEGORIES)
        canonical_set_exact_match = detected_categories == CANONICAL_CATEGORIES
        if not canonical_set_validation_passed:
            raise RuntimeError(
                f"Canonical set validation failed. Detected non-canonical categories: {sorted(detected_categories - CANONICAL_CATEGORIES)}"
            )
        run_output_path = run_dir / "output.xlsx"
        if output_path.resolve() != run_output_path.resolve():
            shutil.copy2(output_path, run_output_path)

        policy_payload = {
            "run_id": run_id,
            "ssot_version": ssot.ssot_version,
            "taxonomy_version": ssot.taxonomy.version,
            "model_name": resolved_model_routes[0].model_name,
            "model_version": resolved_model_routes[0].version,
            "configured_primary_model_version": format_model_version(
                lane_config.classifier_backend, lane_config.classifier_model
            ),
            "inference_parameters": [
                get_inference_parameters(model_name=route.model_name, backend=route.backend)
                for route in resolved_model_routes
            ],
            "ensemble_enabled": run_policy.ensemble_enabled,
            "ensemble_models": run_policy.ensemble_models,
            "resolved_model_versions": model_versions,
            "production_mode": DEFAULT_PRODUCTION_MODE,
            "consensus_strategy": run_policy.consensus_strategy,
            "disagreement_mode": run_policy.disagreement_mode,
            "prompt_version": ssot.policy.prompt_version,
            "pipeline_version": PIPELINE_VERSION,
            "task_routing": TASK_ROUTING,
            "lane_config": lane_config.__dict__,
            "review_mode": review_mode,
            "run_language": run_language,
            "code_version": _git_commit_hash(),
        }
        (run_dir / "policy.json").write_text(json.dumps(policy_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        completed_at = _now_iso()
        _write_disagreement_report(run_dir=run_dir, results=results, row_hashes=row_hashes)

        _write_integrity_report(
            run_dir=run_dir,
            run_id=run_id,
            timestamp=completed_at,
            ssot=ssot,
            review_mode=review_mode,
            run_language=run_language,
            total_rows=len(rows),
            processed_rows=len(results),
            results=results,
            schema_warnings=[],
            canonical_set_validation_passed=canonical_set_validation_passed,
            canonical_set_exact_match=canonical_set_exact_match,
            code_version=_git_commit_hash(),
            model_specs=model_specs,
            model_versions=model_versions,
            per_model_distribution=per_model_distribution,
            consensus_distribution=consensus_distribution,
            consensus_tier_summary=consensus_tier_summary,
        )
        _write_progress(
            run_dir,
            run_id,
            "COMPLETED",
            started_at=started_at,
            completed_at=completed_at,
            total_rows=total_rows,
        )
        _write_processing_stats(
            run_dir=run_dir,
            run_id=run_id,
            started_at=started_at,
            total_rows=total_rows,
            processed_rows=len(results),
            threat_rows=sum(1 for r in results if r.category != "Not Antisemitic"),
            review_required_rows=sum(1 for r in results if "REVIEW_REQUIRED" in (r.flags or [])),
            judged_rows=sum(1 for r in results if r.judge_verdict or r.judge_score is not None),
            second_pass_candidates=sum(
                1
                for r in results
                if any(
                    flag in (r.flags or [])
                    for flag in ["SECOND_PASS_RECHECK", "SECOND_PASS_CONFIRMED", "SECOND_PASS_DISAGREEMENT", "SECOND_PASS_UNAVAILABLE"]
                )
            ),
            second_pass_completed=sum(
                1
                for r in results
                if any(flag in (r.flags or []) for flag in ["SECOND_PASS_CONFIRMED", "SECOND_PASS_DISAGREEMENT"])
            ),
            second_pass_overrides=sum(1 for r in results if "SECOND_PASS_CATEGORY_OVERRIDDEN" in (r.flags or [])),
        )
        _write_artifact_manifest(run_dir)
    except Exception as exc:
        completed_at = _now_iso()
        _write_progress(
            run_dir,
            run_id,
            "FAILED",
            str(exc),
            started_at=started_at,
            completed_at=completed_at,
            total_rows=total_rows,
            processed_rows=completed_rows_counter,
        )
        _write_artifact_manifest(run_dir)
        raise
