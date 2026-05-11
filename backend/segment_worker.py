from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.ops_db_service import (
    block_remaining_segments,
    build_run_segment_summary,
    claim_next_segment,
    complete_segment,
    fail_segment,
    fetch_upload_rows_for_segment,
    list_run_segments,
    reconcile_run_segments,
    reset_run_segments,
    summarize_run_rows,
)
from backend.services.excel_service import ensure_upload_rows_materialized
from backend.services.artifact_manifest_service import write_artifact_manifest
from src.excel_io import build_segment_input_workbook_from_entries, ensure_output_columns, merge_segment_output, write_row_manifest
from src.pipeline import _sha256_file, rebuild_output_from_canonical


PYTHON_BIN = Path(os.getenv("SPOT_NATIVE_PYTHON_BIN") or sys.executable)
STOP_REQUESTED = False
CURRENT_CHILD: subprocess.Popen[str] | None = None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="{spot} background segment worker")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--upload-id", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", required=True)
    parser.add_argument("--review-mode", required=True)
    parser.add_argument("--ssot", required=True, type=Path)
    parser.add_argument("--runs-dir", required=True, type=Path)
    parser.add_argument("--max-workers", default="1")
    parser.add_argument("--progress-every", default="25")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--attempt-id", default=None)
    return parser


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_control(run_dir: Path) -> dict:
    return _safe_read_json(run_dir / "control.json") or {}


def _shutdown_mode(run_dir: Path) -> str:
    control = _read_control(run_dir)
    if bool(control.get("shutdown_requested")):
        return str(control.get("shutdown_mode") or "suspend").lower()
    if bool(control.get("cancelled") or control.get("stopped_at")):
        return "cancel"
    return ""


def _append_log(run_dir: Path, message: str) -> None:
    with (run_dir / "logs.txt").open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _write_progress(
    *,
    run_dir: Path,
    run_id: str,
    state: str,
    started_at: str,
    total_rows: int,
    processed_rows: int,
    message: str = "",
    completed_at: str | None = None,
) -> None:
    progress_percentage = 0.0
    if total_rows > 0:
        progress_percentage = round((processed_rows / total_rows) * 100.0, 2)
    payload = {
        "run_id": run_id,
        "state": state,
        "message": message,
        "started_at": started_at,
        "completed_at": completed_at,
        "total_rows": total_rows,
        "processed_rows": processed_rows,
        "progress_percentage": progress_percentage,
    }
    _write_json(run_dir / "progress.json", payload)


def _write_processing_stats(
    *,
    run_dir: Path,
    run_id: str,
    started_at: str,
    total_rows: int,
    processed_rows: int,
    threat_rows: int | None,
    review_required_rows: int | None,
    judged_rows: int | None,
    second_pass_candidates: int | None = None,
    second_pass_completed: int | None = None,
    second_pass_overrides: int | None = None,
) -> None:
    started_dt = datetime.fromisoformat(started_at)
    now_dt = datetime.now(UTC)
    elapsed_seconds = max((now_dt - started_dt).total_seconds(), 0.0)
    avg_seconds_per_row = round(elapsed_seconds / processed_rows, 4) if processed_rows > 0 else None
    threat_rate = round(threat_rows / processed_rows, 4) if processed_rows > 0 and threat_rows is not None else None
    projected_threat_rows = (
        int(round(threat_rate * total_rows))
        if processed_rows > 0 and total_rows > 0 and threat_rate is not None
        else None
    )
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
    _write_json(run_dir / "processing_stats.json", payload)


def _current_runtime_stats(*, runs_dir: Path, run_id: str, effective_run_state: str) -> dict:
    segment_summary = build_run_segment_summary(
        runs_dir=runs_dir,
        run_id=run_id,
        effective_run_state=effective_run_state,
    )
    canonical_summary = summarize_run_rows(runs_dir=runs_dir, run_id=run_id)
    return {
        "segment_summary": segment_summary,
        "processed_rows": int(segment_summary.get("processed_rows") or 0),
        "threat_rows": int(canonical_summary.get("threat_rows_detected") or 0),
        "review_required_rows": int(canonical_summary.get("review_required_rows_detected") or 0),
        "judged_rows": int(canonical_summary.get("judged_rows") or 0),
        "second_pass_candidates": int(canonical_summary.get("second_pass_candidates") or 0),
        "second_pass_completed": int(canonical_summary.get("second_pass_completed") or 0),
        "second_pass_overrides": int(canonical_summary.get("second_pass_overrides") or 0),
    }


def _copy_parent_policy(segment_policy_path: Path, run_dir: Path, run_id: str) -> None:
    policy = _safe_read_json(segment_policy_path) or {}
    policy["run_id"] = run_id
    _write_json(run_dir / "policy.json", policy)


def _merge_counter_values(target: dict, source: dict) -> dict:
    for key, value in source.items():
        if isinstance(value, dict):
            nested = target.setdefault(key, {})
            if isinstance(nested, dict):
                _merge_counter_values(nested, value)
            continue
        if isinstance(value, (int, float)):
            target[key] = target.get(key, 0) + value
    return target


def _write_integrity_report(run_dir: Path, run_id: str, total_rows: int, segment_reports: list[dict]) -> None:
    if not segment_reports:
        payload = {
            "run_id": run_id,
            "timestamp": _now_iso(),
            "total_rows": total_rows,
            "total_processed": 0,
            "category_distribution": {},
            "canonical_set_validation_passed": False,
            "canonical_set_exact_match": False,
            "schema_warnings": ["No segment integrity reports were produced."],
        }
        _write_json(run_dir / "integrity_report.json", payload)
        return
    first = segment_reports[0]
    merged = {
        "run_id": run_id,
        "timestamp": _now_iso(),
        "ssot_version": first.get("ssot_version"),
        "policy_profile": first.get("policy_profile"),
        "resolved_policy": first.get("resolved_policy"),
        "task_routing": first.get("task_routing"),
        "lane_config": first.get("lane_config"),
        "model_name": first.get("model_name"),
        "model_version": first.get("model_version"),
        "configured_primary_model_version": first.get("configured_primary_model_version"),
        "inference_parameters": first.get("inference_parameters"),
        "code_version": first.get("code_version"),
        "model_specs": first.get("model_specs"),
        "resolved_model_versions": first.get("resolved_model_versions"),
        "total_rows": total_rows,
        "total_processed": 0,
        "category_distribution": {},
        "per_model_distribution": {},
        "consensus_distribution": {},
        "consensus_confidence_summary": {},
        "disagreement_count": 0,
        "fallback_event_count": 0,
        "soft_signal_row_count": 0,
        "soft_signal_flag_distribution": {},
        "minority_report_count": 0,
        "taxonomy_violation_count": 0,
        "empty_text_count": 0,
        "empty_category_recovered_count": 0,
        "skipped_count": 0,
        "low_confidence_count": 0,
        "schema_warnings": [],
        "canonical_set_validation_passed": True,
        "canonical_set_exact_match": True,
    }
    for report in segment_reports:
        merged["total_processed"] += int(report.get("total_processed") or 0)
        for key in [
            "category_distribution",
            "per_model_distribution",
            "consensus_distribution",
            "consensus_confidence_summary",
            "soft_signal_flag_distribution",
        ]:
            if isinstance(report.get(key), dict):
                _merge_counter_values(merged[key], report[key])
        for key in [
            "disagreement_count",
            "fallback_event_count",
            "soft_signal_row_count",
            "minority_report_count",
            "taxonomy_violation_count",
            "empty_text_count",
            "empty_category_recovered_count",
            "skipped_count",
            "low_confidence_count",
        ]:
            merged[key] += int(report.get(key) or 0)
        merged["schema_warnings"].extend(report.get("schema_warnings") or [])
        merged["canonical_set_validation_passed"] = bool(merged["canonical_set_validation_passed"] and report.get("canonical_set_validation_passed", False))
        merged["canonical_set_exact_match"] = bool(merged["canonical_set_exact_match"] and report.get("canonical_set_exact_match", False))
    merged["schema_warnings"] = sorted(set(str(item) for item in merged["schema_warnings"] if str(item).strip()))
    _write_json(run_dir / "integrity_report.json", merged)


def _write_disagreement_report(run_dir: Path, collected_rows: list[dict]) -> None:
    if not collected_rows:
        return
    _write_json(run_dir / "disagreement_report.json", {"rows": collected_rows})


def _write_artifact_manifest(run_dir: Path) -> None:
    write_artifact_manifest(run_dir=run_dir, sha256_file=_sha256_file)


def _append_segment_assignment_manifest(
    *,
    run_dir: Path,
    run_id: str,
    upload_id: str,
    segment_id: str,
    segment_index: int,
    row_start: int,
    row_end: int,
    entries: list[dict],
) -> None:
    manifest_path = run_dir / "segment_assignment_manifest.jsonl"
    existing_keys: set[tuple[int, str]] = set()
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
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
                existing_keys.add((int(payload.get("row_index") or 0), str(payload.get("segment_id") or "")))
            except Exception:
                continue

    with manifest_path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            row_key = (int(entry.get("row_index") or 0), segment_id)
            if row_key in existing_keys:
                continue
            handle.write(
                json.dumps(
                    {
                        "run_id": run_id,
                        "upload_id": upload_id,
                        "segment_id": segment_id,
                        "segment_index": segment_index,
                        "segment_row_start": row_start,
                        "segment_row_end": row_end,
                        **entry,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _collect_segment_artifacts(segments_dir: Path) -> tuple[list[dict], list[dict], Path | None]:
    reports: list[dict] = []
    disagreements: list[dict] = []
    first_policy_path: Path | None = None
    if not segments_dir.exists():
        return reports, disagreements, first_policy_path
    for segment_dir in sorted(path for path in segments_dir.iterdir() if path.is_dir()):
        runs_root = segment_dir / "runs"
        if not runs_root.exists():
            continue
        for child_run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            integrity = _safe_read_json(child_run_dir / "integrity_report.json")
            if integrity:
                reports.append(integrity)
            disagreement = _safe_read_json(child_run_dir / "disagreement_report.json") or {}
            if disagreement.get("rows"):
                disagreements.extend(disagreement["rows"])
            policy_path = child_run_dir / "policy.json"
            if first_policy_path is None and policy_path.exists():
                first_policy_path = policy_path
    return reports, disagreements, first_policy_path


def _segment_run_id(run_id: str, segment_index: int) -> str:
    return f"{run_id}-segment-{segment_index:05d}"


def _reset_segment_attempt_artifacts(
    *,
    segment_dir: Path,
    segment_runs_dir: Path,
    segment_run_id: str,
    preserve_child_run: bool = False,
) -> None:
    segment_output_path = segment_dir / "output.xlsx"
    segment_log_path = segment_dir / "worker.log"
    child_run_dir = segment_runs_dir / segment_run_id

    if segment_output_path.exists():
        segment_output_path.unlink()
    if segment_log_path.exists():
        segment_log_path.unlink()
    if child_run_dir.exists() and not preserve_child_run:
        shutil.rmtree(child_run_dir, ignore_errors=True)


def _should_resume_segment_attempt(*, resume_existing: bool, committed_processed_rows: int) -> bool:
    return bool(resume_existing and committed_processed_rows > 0)


def _rebuild_segment_output_from_canonical(
    *,
    runs_dir: Path,
    run_id: str,
    upload_id: str,
    segment_id: str,
    segment_run_id: str,
    segment_input_path: Path,
    segment_output_path: Path,
    segment_dir: Path,
    row_start: int,
    row_end: int,
    row_count: int,
    language: str,
    review_mode: str,
    ssot_path: Path,
) -> int:
    segment_dir.mkdir(parents=True, exist_ok=True)
    if not segment_input_path.exists():
        stored_rows = fetch_upload_rows_for_segment(
            runs_dir=runs_dir,
            upload_id=upload_id,
            row_start=row_start,
            row_end=row_end,
        )
        if len(stored_rows) != row_count:
            raise RuntimeError(
                f"Segment {segment_id} expected {row_count} stored rows but found {len(stored_rows)}."
            )
        manifest_entries = build_segment_input_workbook_from_entries(segment_input_path, stored_rows)
        write_row_manifest(segment_dir / "row_manifest.jsonl", manifest_entries)
    rebuilt_rows = rebuild_output_from_canonical(
        input_path=segment_input_path,
        output_path=segment_output_path,
        run_id=segment_run_id,
        run_language=language,
        review_mode=review_mode,
        ssot_path=ssot_path,
        canonical_runs_dir=runs_dir,
        canonical_run_id=run_id,
    )
    if rebuilt_rows < row_count:
        raise RuntimeError(
            f"Segment {segment_id} canonical rebuild produced {rebuilt_rows}/{row_count} rows."
        )
    return rebuilt_rows


def _handle_stop(signum, _frame) -> None:  # noqa: ANN001
    del signum
    global STOP_REQUESTED
    STOP_REQUESTED = True


def main() -> int:
    global CURRENT_CHILD
    args = _parser().parse_args()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    run_dir = args.runs_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = run_dir / "_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    started_at = _now_iso()
    total_rows = 0
    completed_rows = 0
    completed_threat_rows = 0
    completed_review_required_rows = 0
    completed_judged_rows = 0
    completed_second_pass_candidates = 0
    completed_second_pass_completed = 0
    completed_second_pass_overrides = 0

    if args.resume_existing:
        reconcile_run_segments(runs_dir=args.runs_dir, run_id=args.run_id, target_state="QUEUED")
        reconcile_message = "Resuming existing queued segments"
    else:
        reset_run_segments(runs_dir=args.runs_dir, run_id=args.run_id)
        reconcile_message = "Waiting for queued segments"
    runtime_stats = _current_runtime_stats(runs_dir=args.runs_dir, run_id=args.run_id, effective_run_state="PROCESSING")
    summary = runtime_stats["segment_summary"]
    total_rows = int(summary.get("total_rows") or 0)
    completed_rows = int(runtime_stats["processed_rows"] or 0)
    completed_threat_rows = int(runtime_stats["threat_rows"] or 0)
    completed_review_required_rows = int(runtime_stats["review_required_rows"] or 0)
    completed_judged_rows = int(runtime_stats["judged_rows"] or 0)
    completed_second_pass_candidates = int(runtime_stats["second_pass_candidates"] or 0)
    completed_second_pass_completed = int(runtime_stats["second_pass_completed"] or 0)
    completed_second_pass_overrides = int(runtime_stats["second_pass_overrides"] or 0)
    _append_log(run_dir, f"[STARTING] Segment worker booted for {args.run_id}")
    _write_progress(
        run_dir=run_dir,
        run_id=args.run_id,
        state="PROCESSING",
        started_at=started_at,
        total_rows=total_rows,
        processed_rows=completed_rows,
        message=reconcile_message,
    )
    _write_processing_stats(
        run_dir=run_dir,
        run_id=args.run_id,
        started_at=started_at,
        total_rows=total_rows,
        processed_rows=completed_rows,
        threat_rows=completed_threat_rows,
        review_required_rows=completed_review_required_rows,
        judged_rows=completed_judged_rows,
        second_pass_candidates=completed_second_pass_candidates,
        second_pass_completed=completed_second_pass_completed,
        second_pass_overrides=completed_second_pass_overrides,
    )

    try:
        while True:
            if STOP_REQUESTED:
                raise KeyboardInterrupt("stop requested")
            segment = claim_next_segment(runs_dir=args.runs_dir, run_id=args.run_id, worker_id=args.run_id)
            if not segment:
                break

            segment_id = str(segment["segment_id"])
            segment_index = int(segment["segment_index"])
            segment_row_count = int(segment["row_count"])
            segment_dir = segments_dir / segment_id
            segment_dir.mkdir(parents=True, exist_ok=True)
            segment_input_path = segment_dir / "input.xlsx"
            segment_output_path = segment_dir / "output.xlsx"
            segment_runs_dir = segment_dir / "runs"
            segment_run_id = _segment_run_id(args.run_id, segment_index)
            segment_log_path = segment_dir / "worker.log"
            child_run_dir = segment_runs_dir / segment_run_id
            checkpoint_path = child_run_dir / "result_checkpoint.jsonl"
            resumed_segment_rows = min(int(segment.get("processed_rows") or 0), segment_row_count)
            resume_segment_attempt = _should_resume_segment_attempt(
                resume_existing=args.resume_existing,
                committed_processed_rows=resumed_segment_rows,
            )

            _reset_segment_attempt_artifacts(
                segment_dir=segment_dir,
                segment_runs_dir=segment_runs_dir,
                segment_run_id=segment_run_id,
                preserve_child_run=resume_segment_attempt,
            )
            stored_rows = fetch_upload_rows_for_segment(
                runs_dir=args.runs_dir,
                upload_id=args.upload_id,
                row_start=int(segment["row_start"]),
                row_end=int(segment["row_end"]),
            )
            if len(stored_rows) != segment_row_count:
                materialized_count = ensure_upload_rows_materialized(
                    runs_dir=args.runs_dir,
                    ssot_path=args.ssot,
                    upload_id=args.upload_id,
                    fallback_input_path=args.input,
                )
                _append_log(
                    run_dir,
                    f"[BACKFILL] Rebuilt {materialized_count} stored upload rows for legacy upload {args.upload_id}",
                )
                stored_rows = fetch_upload_rows_for_segment(
                    runs_dir=args.runs_dir,
                    upload_id=args.upload_id,
                    row_start=int(segment["row_start"]),
                    row_end=int(segment["row_end"]),
                )
                if len(stored_rows) != segment_row_count:
                    raise RuntimeError(
                        f"Segment {segment_id} expected {segment_row_count} stored rows but found {len(stored_rows)}."
                    )
            segment_manifest_entries = build_segment_input_workbook_from_entries(
                segment_input_path,
                stored_rows,
            )
            write_row_manifest(segment_dir / "row_manifest.jsonl", segment_manifest_entries)
            _append_segment_assignment_manifest(
                run_dir=run_dir,
                run_id=args.run_id,
                upload_id=args.upload_id,
                segment_id=segment_id,
                segment_index=segment_index,
                row_start=int(segment["row_start"]),
                row_end=int(segment["row_end"]),
                entries=segment_manifest_entries,
            )
            cmd = [
                str(PYTHON_BIN),
                "-m",
                "src.cli",
                "classify",
                "--input",
                str(segment_input_path),
                "--output",
                str(segment_output_path),
                "--run-id",
                segment_run_id,
                "--language",
                args.language,
                "--review-mode",
                args.review_mode,
                "--ssot",
                str(args.ssot),
                "--runs-dir",
                str(segment_runs_dir),
                "--max-workers",
                str(args.max_workers),
                "--progress-every",
                str(args.progress_every),
                "--canonical-runs-dir",
                str(args.runs_dir),
                "--canonical-run-id",
                args.run_id,
                "--canonical-upload-id",
                args.upload_id,
                "--canonical-segment-id",
                segment_id,
            ]
            if args.attempt_id:
                cmd.extend(["--canonical-attempt-id", str(args.attempt_id)])
            if args.limit is not None:
                cmd.extend(["--limit", str(args.limit)])
            if resume_segment_attempt:
                cmd.append("--resume-existing")
            with segment_log_path.open("w", encoding="utf-8") as log_handle:
                CURRENT_CHILD = subprocess.Popen(
                    cmd,
                    cwd=PROJECT_ROOT,
                    stdout=log_handle,
                    stderr=log_handle,
                    text=True,
                )
                if resume_segment_attempt:
                    resume_basis = "committed state + checkpoint" if checkpoint_path.exists() else "committed state"
                    _append_log(
                        run_dir,
                        f"[PROCESSING] Resumed {segment_id} from {resume_basis} ({resumed_segment_rows}/{segment_row_count} rows)",
                    )
                else:
                    _append_log(run_dir, f"[PROCESSING] Claimed {segment_id} ({segment_row_count} rows)")
                while CURRENT_CHILD.poll() is None:
                    if STOP_REQUESTED:
                        CURRENT_CHILD.terminate()
                        break
                    runtime_stats = _current_runtime_stats(
                        runs_dir=args.runs_dir,
                        run_id=args.run_id,
                        effective_run_state="PROCESSING",
                    )
                    segment_summary = runtime_stats["segment_summary"]
                    active_segment = segment_summary.get("active_segment") or {}
                    child_processed_rows = min(int(active_segment.get("processed_rows") or 0), segment_row_count)
                    aggregate_processed_rows = int(runtime_stats["processed_rows"] or 0)
                    aggregate_threat_rows = int(runtime_stats["threat_rows"] or 0)
                    aggregate_review_required_rows = int(runtime_stats["review_required_rows"] or 0)
                    aggregate_judged_rows = int(runtime_stats["judged_rows"] or 0)
                    aggregate_second_pass_candidates = int(runtime_stats["second_pass_candidates"] or 0)
                    aggregate_second_pass_completed = int(runtime_stats["second_pass_completed"] or 0)
                    aggregate_second_pass_overrides = int(runtime_stats["second_pass_overrides"] or 0)
                    _write_progress(
                        run_dir=run_dir,
                        run_id=args.run_id,
                        state="PROCESSING",
                        started_at=started_at,
                        total_rows=total_rows,
                        processed_rows=aggregate_processed_rows,
                        message=f"Processing segment {segment_index} ({child_processed_rows}/{segment_row_count} rows in current segment)",
                    )
                    _write_processing_stats(
                        run_dir=run_dir,
                        run_id=args.run_id,
                        started_at=started_at,
                        total_rows=total_rows,
                        processed_rows=aggregate_processed_rows,
                        threat_rows=aggregate_threat_rows,
                        review_required_rows=aggregate_review_required_rows,
                        judged_rows=aggregate_judged_rows,
                        second_pass_candidates=aggregate_second_pass_candidates,
                        second_pass_completed=aggregate_second_pass_completed,
                        second_pass_overrides=aggregate_second_pass_overrides,
                    )
                    time.sleep(0.5)
                return_code = CURRENT_CHILD.wait()
                CURRENT_CHILD = None

            if STOP_REQUESTED:
                shutdown_mode = _shutdown_mode(run_dir)
                if shutdown_mode == "suspend":
                    reconcile_run_segments(runs_dir=args.runs_dir, run_id=args.run_id, target_state="QUEUED")
                    _append_log(run_dir, f"[INTERRUPTED] Supervisor suspend requested while processing {segment_id}")
                else:
                    fail_segment(runs_dir=args.runs_dir, segment_id=segment_id, error_message="Run cancelled by operator.", state="CANCELLED")
                raise KeyboardInterrupt("stop requested")

            if return_code != 0:
                runtime_stats = _current_runtime_stats(
                    runs_dir=args.runs_dir,
                    run_id=args.run_id,
                    effective_run_state="PROCESSING",
                )
                active_segment = runtime_stats["segment_summary"].get("active_segment") or {}
                committed_segment_rows = min(int(active_segment.get("processed_rows") or resumed_segment_rows), segment_row_count)
                if committed_segment_rows >= segment_row_count:
                    rebuilt_rows = _rebuild_segment_output_from_canonical(
                        runs_dir=args.runs_dir,
                        run_id=args.run_id,
                        upload_id=args.upload_id,
                        segment_id=segment_id,
                        segment_run_id=segment_run_id,
                        segment_input_path=segment_input_path,
                        segment_output_path=segment_output_path,
                        segment_dir=segment_dir,
                        row_start=int(segment["row_start"]),
                        row_end=int(segment["row_end"]),
                        row_count=segment_row_count,
                        language=args.language,
                        review_mode=args.review_mode,
                        ssot_path=args.ssot,
                    )
                    _append_log(
                        run_dir,
                        f"[RECOVERED] Rebuilt output for {segment_id} from canonical state after child failure ({rebuilt_rows}/{segment_row_count} rows)",
                    )
                    return_code = 0
                else:
                    error_message = segment_log_path.read_text(encoding="utf-8")[-4000:] if segment_log_path.exists() else "Segment classify subprocess failed."
                    fail_segment(runs_dir=args.runs_dir, segment_id=segment_id, error_message=error_message, state="FAILED")
                    raise RuntimeError(f"Segment {segment_id} failed.")
            if return_code == 0:
                complete_segment(runs_dir=args.runs_dir, segment_id=segment_id)

            runtime_stats = _current_runtime_stats(runs_dir=args.runs_dir, run_id=args.run_id, effective_run_state="PROCESSING")
            completed_rows = int(runtime_stats["processed_rows"] or completed_rows)
            completed_threat_rows = int(runtime_stats["threat_rows"] or 0)
            completed_review_required_rows = int(runtime_stats["review_required_rows"] or 0)
            completed_judged_rows = int(runtime_stats["judged_rows"] or 0)
            completed_second_pass_candidates = int(runtime_stats["second_pass_candidates"] or 0)
            completed_second_pass_completed = int(runtime_stats["second_pass_completed"] or 0)
            completed_second_pass_overrides = int(runtime_stats["second_pass_overrides"] or 0)
            _write_progress(
                run_dir=run_dir,
                run_id=args.run_id,
                state="PROCESSING",
                started_at=started_at,
                total_rows=total_rows,
                processed_rows=completed_rows,
                message=f"Completed segment {segment_index}",
            )
            _write_processing_stats(
                run_dir=run_dir,
                run_id=args.run_id,
                started_at=started_at,
                total_rows=total_rows,
                processed_rows=completed_rows,
                threat_rows=completed_threat_rows,
                review_required_rows=completed_review_required_rows,
                judged_rows=completed_judged_rows,
                second_pass_candidates=completed_second_pass_candidates,
                second_pass_completed=completed_second_pass_completed,
                second_pass_overrides=completed_second_pass_overrides,
            )

        if args.output.exists():
            args.output.unlink()
        shutil.copy2(args.input, args.output)
        ensure_output_columns(args.output)
        for segment in list_run_segments(runs_dir=args.runs_dir, run_id=args.run_id):
            segment_id = str(segment["segment_id"])
            segment_dir = segments_dir / segment_id
            segment_input_path = segment_dir / "input.xlsx"
            segment_output_path = segment_dir / "output.xlsx"
            segment_run_id = _segment_run_id(args.run_id, int(segment["segment_index"]))
            segment_row_count = int(segment["row_count"] or 0)
            segment_processed_rows = min(max(int(segment["processed_rows"] or 0), 0), segment_row_count)
            if (
                str(segment["state"] or "") == "COMPLETED"
                and not segment_output_path.exists()
                and segment_row_count > 0
                and segment_processed_rows >= segment_row_count
            ):
                rebuilt_rows = _rebuild_segment_output_from_canonical(
                    runs_dir=args.runs_dir,
                    run_id=args.run_id,
                    upload_id=args.upload_id,
                    segment_id=segment_id,
                    segment_run_id=segment_run_id,
                    segment_input_path=segment_input_path,
                    segment_output_path=segment_output_path,
                    segment_dir=segment_dir,
                    row_start=int(segment["row_start"]),
                    row_end=int(segment["row_end"]),
                    row_count=segment_row_count,
                    language=args.language,
                    review_mode=args.review_mode,
                    ssot_path=args.ssot,
                )
                _append_log(
                    run_dir,
                    f"[RECOVERED] Rebuilt missing output for completed {segment_id} from canonical state ({rebuilt_rows}/{segment_row_count} rows)",
                )
            if segment_output_path.exists():
                merge_segment_output(segment_output_path, args.output)

        segment_reports, disagreement_rows, first_policy_path = _collect_segment_artifacts(segments_dir)
        if first_policy_path and first_policy_path.exists():
            _copy_parent_policy(first_policy_path, run_dir, args.run_id)
        _write_integrity_report(run_dir, args.run_id, total_rows, segment_reports)
        _write_disagreement_report(run_dir, disagreement_rows)
        completed_at = _now_iso()
        _write_progress(
            run_dir=run_dir,
            run_id=args.run_id,
            state="COMPLETED",
            started_at=started_at,
            total_rows=total_rows,
            processed_rows=completed_rows,
            completed_at=completed_at,
            message="All queued segments completed",
        )
        _append_log(run_dir, f"[COMPLETED] {completed_rows}/{total_rows} rows processed")
        _write_artifact_manifest(run_dir)
        return 0
    except KeyboardInterrupt:
        shutdown_mode = _shutdown_mode(run_dir)
        if shutdown_mode == "suspend":
            reconciled = reconcile_run_segments(runs_dir=args.runs_dir, run_id=args.run_id, target_state="QUEUED")
            runtime_stats = _current_runtime_stats(runs_dir=args.runs_dir, run_id=args.run_id, effective_run_state="INTERRUPTED")
            completed_rows = int(runtime_stats["processed_rows"] or completed_rows)
            _write_progress(
                run_dir=run_dir,
                run_id=args.run_id,
                state="INTERRUPTED",
                started_at=started_at,
                total_rows=total_rows,
                processed_rows=completed_rows,
                completed_at=_now_iso(),
                message="Processing suspended by native supervisor",
            )
            _append_log(run_dir, f"[INTERRUPTED] Segment worker suspended by native supervisor; reconciled {reconciled} in-flight segments")
            _write_artifact_manifest(run_dir)
            return 0
        block_remaining_segments(runs_dir=args.runs_dir, run_id=args.run_id, state="CANCELLED", error_message="Run cancelled by operator.")
        runtime_stats = _current_runtime_stats(runs_dir=args.runs_dir, run_id=args.run_id, effective_run_state="CANCELLED")
        completed_rows = int(runtime_stats["processed_rows"] or completed_rows)
        _write_progress(
            run_dir=run_dir,
            run_id=args.run_id,
            state="CANCELLED",
            started_at=started_at,
            total_rows=total_rows,
            processed_rows=completed_rows,
            completed_at=_now_iso(),
            message="Processing cancelled by operator",
        )
        _append_log(run_dir, "[CANCELLED] Segment worker stopped by operator")
        _write_artifact_manifest(run_dir)
        return 1
    except Exception as exc:  # noqa: BLE001
        block_remaining_segments(runs_dir=args.runs_dir, run_id=args.run_id, state="FAILED", error_message=str(exc))
        runtime_stats = _current_runtime_stats(runs_dir=args.runs_dir, run_id=args.run_id, effective_run_state="FAILED")
        completed_rows = int(runtime_stats["processed_rows"] or completed_rows)
        _write_progress(
            run_dir=run_dir,
            run_id=args.run_id,
            state="FAILED",
            started_at=started_at,
            total_rows=total_rows,
            processed_rows=completed_rows,
            completed_at=_now_iso(),
            message=str(exc),
        )
        _append_log(run_dir, f"[FAILED] {exc}")
        _write_artifact_manifest(run_dir)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
