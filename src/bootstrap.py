from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except Exception:
        pass


def _step(name: str, ok: bool, detail: str) -> dict:
    return {
        "name": name,
        "ok": ok,
        "detail": detail,
    }


def _ensure_directory(path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    _chmod(path, 0o700)
    return _step(f"mkdir_{path.name}", True, f"Ensured directory exists: {path}")


def _create_venv(venv_path: Path) -> dict:
    if (venv_path / "bin" / "python").exists():
        _chmod(venv_path, 0o700)
        return _step("virtualenv", True, f"Virtual environment already exists at {venv_path}")
    venv.create(venv_path, with_pip=True, clear=False, symlinks=True)
    _chmod(venv_path, 0o700)
    return _step("virtualenv", True, f"Created virtual environment at {venv_path}")


def _install_requirements(venv_python: Path, requirements_path: Path) -> dict:
    if not requirements_path.exists():
        return _step("requirements_install", False, f"Requirements file not found at {requirements_path}")

    cmd = [str(venv_python), "-m", "pip", "install", "-r", str(requirements_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        return _step("requirements_install", False, f"pip install failed: {tail}")
    return _step("requirements_install", True, f"Installed requirements from {requirements_path}")


def bootstrap_local_appliance(
    project_root: Path,
    venv_path: Path,
    requirements_path: Path,
    ssot_path: Path,
    runs_dir: Path,
    logs_dir: Path,
    skip_install: bool = False,
) -> dict:
    steps: list[dict] = []

    steps.append(_ensure_directory(runs_dir))
    steps.append(_ensure_directory(logs_dir))
    steps.append(_create_venv(venv_path))
    if ssot_path.exists():
        _chmod(ssot_path, 0o600)
        steps.append(_step("ssot_permissions", True, f"Restricted SSOT file permissions: {ssot_path}"))
    else:
        steps.append(_step("ssot_permissions", False, f"SSOT file not found at {ssot_path}"))

    venv_python = venv_path / "bin" / "python"
    if not skip_install:
        steps.append(_install_requirements(venv_python, requirements_path))
    else:
        steps.append(_step("requirements_install", True, "Skipped requirements installation by request"))

    next_steps = [
        f"Activate the environment: source {venv_path}/bin/activate",
        f"Run bootstrap verification: {venv_python} -m src.cli preflight --ssot ssot/ssot.json --runs-dir {runs_dir} --port 8765",
        "Ensure local MLX model weights are available for Apertus before production use",
        "Ensure Ollama is installed locally for fallback and support lanes before production use",
    ]

    failures = [step for step in steps if not step["ok"]]
    return {
        "status": "ok" if not failures else "error",
        "project_root": str(project_root),
        "virtualenv_python": str(venv_python),
        "summary": {
            "steps_total": len(steps),
            "failures": len(failures),
        },
        "steps": steps,
        "next_steps": next_steps,
        "environment": {
            "runs_dir": str(runs_dir),
            "logs_dir": str(logs_dir),
            "ssot_path": str(ssot_path),
            "cwd": os.getcwd(),
            "python": sys.executable,
        },
    }


def bootstrap_report_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
