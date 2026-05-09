from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


RUN_ARTIFACT_NAMES = [
    "output.xlsx",
    "integrity_report.json",
    "artifact_manifest.json",
    "segment_assignment_manifest.jsonl",
    "policy.json",
    "logs.txt",
    "progress.json",
    "processing_stats.json",
    "review_state.json",
    "signoff.json",
    "action_log.jsonl",
    "disagreement_report.json",
    "control.json",
    "result_checkpoint.jsonl",
]


def build_artifact_manifest(*, run_dir: Path, sha256_file: Callable[[Path], str]) -> dict:
    manifest: dict[str, dict[str, int | str]] = {}
    for name in RUN_ARTIFACT_NAMES:
        path = run_dir / name
        if path.exists():
            manifest[name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return {"artifacts": manifest}


def write_artifact_manifest(*, run_dir: Path, sha256_file: Callable[[Path], str]) -> None:
    payload = build_artifact_manifest(run_dir=run_dir, sha256_file=sha256_file)
    (run_dir / "artifact_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
