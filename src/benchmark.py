from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from .ssot_loader import load_ssot


def benchmark_worker_configs(
    *,
    input_path: Path,
    ssot_path: Path,
    runs_dir: Path,
    benchmark_run_id: str,
    run_language: str,
    review_mode: str,
    worker_values: list[int],
    limit: int | None = None,
    progress_every: int = 100,
    per_run_timeout_sec: int | None = None,
) -> Path:
    ssot = load_ssot(ssot_path)
    if review_mode not in ssot.policy.review_modes:
        raise RuntimeError(f"Invalid review_mode '{review_mode}'. Expected one of {ssot.policy.review_modes}.")

    benchmark_root = runs_dir / f"{benchmark_run_id}-benchmark"
    benchmark_root.mkdir(parents=True, exist_ok=True)
    report_path = benchmark_root / "worker_benchmark_report.json"

    results: list[dict] = []
    for worker_count in worker_values:
        run_id = f"{benchmark_run_id}-w{worker_count}"
        output_path = benchmark_root / f"{run_id}.xlsx"
        started = time.time()
        command = [
            sys.executable,
            "-m",
            "src.cli",
            "classify",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--run-id",
            run_id,
            "--language",
            run_language,
            "--review-mode",
            review_mode,
            "--ssot",
            str(ssot_path),
            "--runs-dir",
            str(runs_dir),
            "--max-workers",
            str(worker_count),
            "--progress-every",
            str(progress_every),
        ]
        if limit is not None:
            command.extend(["--limit", str(limit)])
        status = "completed"
        error_message = None
        try:
            subprocess.run(
                command,
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                timeout=per_run_timeout_sec if per_run_timeout_sec and per_run_timeout_sec > 0 else None,
            )
        except subprocess.TimeoutExpired:
            status = "timeout"
            error_message = f"Timed out after {per_run_timeout_sec} seconds."
        except subprocess.CalledProcessError as exc:
            status = "failed"
            error_message = f"classify exited with status {exc.returncode}"
        duration_seconds = round(time.time() - started, 2)
        processing_stats_path = runs_dir / run_id / "processing_stats.json"
        processing_stats = json.loads(processing_stats_path.read_text(encoding="utf-8")) if processing_stats_path.exists() else {}
        processed_rows = int(processing_stats.get("processed_rows") or 0)
        rows_per_minute = round((processed_rows / duration_seconds) * 60, 2) if duration_seconds > 0 and processed_rows > 0 else 0.0
        results.append(
            {
                "run_id": run_id,
                "max_workers": worker_count,
                "status": status,
                "error_message": error_message,
                "duration_seconds": duration_seconds,
                "processed_rows": processed_rows,
                "rows_per_minute": rows_per_minute,
                "avg_seconds_per_row": processing_stats.get("avg_seconds_per_row"),
                "threat_rows_detected": processing_stats.get("threat_rows_detected"),
                "review_required_rows_detected": processing_stats.get("review_required_rows_detected"),
                "second_pass_candidates": processing_stats.get("second_pass_candidates"),
                "second_pass_completed": processing_stats.get("second_pass_completed"),
                "second_pass_overrides": processing_stats.get("second_pass_overrides"),
                "output_path": str(output_path),
                "artifacts_dir": str(runs_dir / run_id),
            }
        )
        report_path.write_text(
            json.dumps(
                {
                    "benchmark_run_id": benchmark_run_id,
                    "input_path": str(input_path),
                    "ssot_path": str(ssot_path),
                    "review_mode": review_mode,
                    "run_language": run_language,
                    "limit": limit,
                    "worker_values": worker_values,
                    "results": results,
                    "recommended_max_workers": None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    completed_runs = [item for item in results if item.get("status") == "completed"]
    fastest = min(completed_runs, key=lambda item: float(item.get("duration_seconds") or 0.0)) if completed_runs else None
    report = {
        "benchmark_run_id": benchmark_run_id,
        "input_path": str(input_path),
        "ssot_path": str(ssot_path),
        "review_mode": review_mode,
        "run_language": run_language,
        "limit": limit,
        "worker_values": worker_values,
        "results": results,
        "recommended_max_workers": fastest.get("max_workers") if fastest else None,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path
