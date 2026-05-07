from __future__ import annotations

import argparse
import json
from pathlib import Path

from .defaults import DEFAULT_ENSEMBLE_MODELS, DEFAULT_PRODUCTION_MODE, DEFAULT_SINGLE_MODEL


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AI-assisted antisemitism classification MVP")
    sub = p.add_subparsers(dest="command", required=True)

    classify = sub.add_parser("classify", help="Classify rows from an Excel file")
    classify.add_argument("--input", required=True, type=Path)
    classify.add_argument("--output", required=True, type=Path)
    classify.add_argument("--run-id", required=True)
    classify.add_argument("--language", required=True)
    classify.add_argument("--review-mode", default="none")
    classify.add_argument("--ssot", default=Path("ssot/ssot.json"), type=Path)
    classify.add_argument("--runs-dir", default=Path("runs"), type=Path)
    classify.add_argument("--ensemble-enabled", action="store_true")
    classify.add_argument(
        "--ensemble-models",
        default=DEFAULT_ENSEMBLE_MODELS,
        help="Comma-separated model specs (use backend://model for explicit routing; exactly 3 for MVP ensemble)",
    )
    classify.add_argument("--consensus-strategy", default="majority", choices=["majority", "unanimous", "weighted"])
    classify.add_argument("--disagreement-mode", default="human_review", choices=["flag", "fail", "human_review"])
    classify.add_argument("--max-workers", type=int, default=4)
    classify.add_argument("--limit", type=int, default=None)
    classify.add_argument("--progress-every", type=int, default=100)

    benchmark = sub.add_parser("benchmark-workers", help="Benchmark local throughput across max_workers values")
    benchmark.add_argument("--input", required=True, type=Path)
    benchmark.add_argument("--ssot", default=Path("ssot/ssot.json"), type=Path)
    benchmark.add_argument("--runs-dir", default=Path("runs"), type=Path)
    benchmark.add_argument("--benchmark-run-id", required=True)
    benchmark.add_argument("--language", required=True)
    benchmark.add_argument("--review-mode", default="partial")
    benchmark.add_argument("--worker-values", default="1,2,4")
    benchmark.add_argument("--limit", type=int, default=None)
    benchmark.add_argument("--progress-every", type=int, default=100)
    benchmark.add_argument("--per-run-timeout-sec", type=int, default=0)

    evaluate = sub.add_parser("evaluate", help="Run deterministic single vs ensemble comparison")
    evaluate.add_argument("--input", required=True, type=Path)
    evaluate.add_argument("--ssot", default=Path("ssot/ssot.json"), type=Path)
    evaluate.add_argument("--runs-dir", default=Path("runs"), type=Path)
    evaluate.add_argument("--evaluation-run-id", required=True)
    evaluate.add_argument("--language", required=True)
    evaluate.add_argument("--review-mode", default="partial")
    evaluate.add_argument("--single-model", default=DEFAULT_SINGLE_MODEL, help="Model spec; supports backend://model")
    evaluate.add_argument(
        "--ensemble-models",
        default=DEFAULT_ENSEMBLE_MODELS,
        help="Comma-separated model specs; supports backend://model",
    )
    evaluate.add_argument("--max-workers", type=int, default=1)
    evaluate.add_argument("--limit", type=int, default=None)
    evaluate.add_argument("--progress-every", type=int, default=100)

    preflight = sub.add_parser("preflight", help="Validate local appliance prerequisites")
    preflight.add_argument("--ssot", default=Path("ssot/ssot.json"), type=Path)
    preflight.add_argument("--runs-dir", default=Path("runs"), type=Path)
    preflight.add_argument("--port", type=int, default=8765)

    bootstrap = sub.add_parser("bootstrap", help="Prepare local appliance directories and Python environment")
    bootstrap.add_argument("--project-root", default=Path("."), type=Path)
    bootstrap.add_argument("--venv-path", default=Path(".venv"), type=Path)
    bootstrap.add_argument("--requirements", default=Path("requirements.txt"), type=Path)
    bootstrap.add_argument("--ssot", default=Path("ssot/ssot.json"), type=Path)
    bootstrap.add_argument("--runs-dir", default=Path("runs"), type=Path)
    bootstrap.add_argument("--logs-dir", default=Path("logs"), type=Path)
    bootstrap.add_argument("--skip-install", action="store_true")
    return p


def main() -> int:
    args = _parser().parse_args()

    if args.command == "classify":
        try:
            if DEFAULT_PRODUCTION_MODE and args.ensemble_enabled:
                raise RuntimeError("SPOT production mode does not allow ensemble classification from the CLI.")
            from .pipeline import run_classification

            run_classification(
                input_path=args.input,
                output_path=args.output,
                run_id=args.run_id,
                run_language=args.language,
                review_mode=args.review_mode,
                ssot_path=args.ssot,
                runs_dir=args.runs_dir,
                max_workers=args.max_workers,
                limit=args.limit,
                ensemble_enabled=bool(args.ensemble_enabled),
                ensemble_models=[m.strip() for m in args.ensemble_models.split(",") if m.strip()],
                consensus_strategy=args.consensus_strategy,
                disagreement_mode=args.disagreement_mode,
                progress_every=args.progress_every,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            return 1
    elif args.command == "evaluate":
        try:
            if DEFAULT_PRODUCTION_MODE:
                raise RuntimeError("SPOT production mode does not allow CLI evaluation runs.")
            from .evaluation import evaluate_runs

            report_path = evaluate_runs(
                input_path=args.input,
                ssot_path=args.ssot,
                runs_dir=args.runs_dir,
                evaluation_run_id=args.evaluation_run_id,
                run_language=args.language,
                review_mode=args.review_mode,
                single_model=args.single_model,
                ensemble_models=[m.strip() for m in args.ensemble_models.split(",") if m.strip()],
                max_workers=args.max_workers,
                limit=args.limit,
                progress_every=args.progress_every,
            )
            print(json.dumps({"status": "ok", "evaluation_report": str(report_path)}, ensure_ascii=False))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            return 1
    elif args.command == "benchmark-workers":
        try:
            from .benchmark import benchmark_worker_configs

            worker_values = [int(item.strip()) for item in str(args.worker_values).split(",") if item.strip()]
            report_path = benchmark_worker_configs(
                input_path=args.input,
                ssot_path=args.ssot,
                runs_dir=args.runs_dir,
                benchmark_run_id=args.benchmark_run_id,
                run_language=args.language,
                review_mode=args.review_mode,
                worker_values=worker_values,
                limit=args.limit,
                progress_every=args.progress_every,
                per_run_timeout_sec=args.per_run_timeout_sec or None,
            )
            print(json.dumps({"status": "ok", "benchmark_report": str(report_path)}, ensure_ascii=False))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            return 1
    elif args.command == "preflight":
        from .preflight import run_preflight

        report = run_preflight(
            ssot_path=args.ssot,
            runs_dir=args.runs_dir,
            port=args.port,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "ok" else 1
    elif args.command == "bootstrap":
        from .bootstrap import bootstrap_local_appliance, bootstrap_report_json

        report = bootstrap_local_appliance(
            project_root=args.project_root.resolve(),
            venv_path=args.venv_path,
            requirements_path=args.requirements,
            ssot_path=args.ssot,
            runs_dir=args.runs_dir,
            logs_dir=args.logs_dir,
            skip_install=bool(args.skip_install),
        )
        print(bootstrap_report_json(report))
        return 0 if report["status"] == "ok" else 1

    print(json.dumps({"status": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
