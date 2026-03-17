from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import socket
import sys
import tempfile
import urllib.parse
from pathlib import Path

from .defaults import DEFAULT_LOCKED_SSOT_PATH, DEFAULT_OLLAMA_URL, DEFAULT_PRODUCTION_MODE
from .lanes import parse_model_spec
from .ssot_loader import SSOTError, load_ssot


def _check(name: str, ok: bool, detail: str, severity: str = "error") -> dict:
    return {
        "name": name,
        "ok": ok,
        "severity": severity,
        "detail": detail,
    }


def _is_loopback_url(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    if hostname in {"127.0.0.1", "localhost", "::1"}:
        return True, hostname
    return False, hostname or "<missing>"


def _is_port_bindable(host: str, port: int) -> tuple[bool, str]:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        return False, str(exc)
    finally:
        probe.close()
    return True, "port is available for local bind"


def _python_dependency_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _writable_directory(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".preflight-", delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, "directory is writable"


def _permissions_ok(path: Path, expected_mode: int) -> tuple[bool, str]:
    try:
        current_mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        return False, "path not found"
    return current_mode == expected_mode, f"mode={oct(current_mode)}, expected={oct(expected_mode)}"


def run_preflight(ssot_path: Path, runs_dir: Path, port: int = 8765) -> dict:
    checks: list[dict] = []

    machine = platform.machine().lower()
    checks.append(
        _check(
            "apple_silicon",
            machine in {"arm64", "aarch64"},
            f"Detected machine architecture: {machine}",
        )
    )

    venv_python = Path(sys.prefix) / "bin" / "python"
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    checks.append(
        _check(
            "virtualenv",
            in_venv and venv_python.exists(),
            f"Python executable: {sys.executable}",
        )
    )

    if not ssot_path.exists():
        checks.append(_check("ssot_file", False, f"SSOT not found at {ssot_path}"))
        return _finalize_report(checks)

    try:
        ssot = load_ssot(ssot_path)
        checks.append(_check("ssot_load", True, f"Loaded SSOT {ssot.ssot_version} from {ssot_path}"))
    except SSOTError as exc:
        checks.append(_check("ssot_load", False, str(exc)))
        return _finalize_report(checks)
    if DEFAULT_PRODUCTION_MODE:
        checks.append(
            _check(
                "locked_ssot_path",
                ssot_path.resolve() == Path(DEFAULT_LOCKED_SSOT_PATH).resolve(),
                f"Production SSOT path: {ssot_path.resolve()}",
            )
        )

    required_modules = [
        ("openpyxl", "openpyxl"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
    ]
    for package_name, module_name in required_modules:
        checks.append(
            _check(
                f"dependency_{package_name}",
                _python_dependency_exists(module_name),
                f"Python module '{module_name}' {'is' if _python_dependency_exists(module_name) else 'is not'} importable",
            )
        )

    primary_route = parse_model_spec(
        f"{ssot.runtime.classifier.backend}://{ssot.runtime.classifier.model}",
        ssot.runtime.classifier.backend,
        ssot.runtime.classifier.model,
    )
    checks.append(
        _check(
            "mlx_runtime",
            _python_dependency_exists("mlx_lm") if primary_route.backend == "mlx" else True,
            f"Primary classifier route: {primary_route.spec}",
        )
    )

    uses_ollama = any(
        lane.backend == "ollama" or lane.fallback_backend == "ollama"
        for lane in [ssot.runtime.classifier, ssot.runtime.drafter, ssot.runtime.judge]
    )
    if uses_ollama:
        ollama_path = shutil.which("ollama")
        checks.append(
            _check(
                "ollama_binary",
                ollama_path is not None,
                f"Ollama binary: {ollama_path or 'not found'}",
            )
        )

    is_loopback, host_detail = _is_loopback_url(DEFAULT_OLLAMA_URL)
    checks.append(
        _check(
            "ollama_loopback",
            is_loopback,
            f"Configured Ollama URL host: {host_detail} ({DEFAULT_OLLAMA_URL})",
        )
    )

    writable, writable_detail = _writable_directory(runs_dir)
    checks.append(_check("runs_directory", writable, f"{runs_dir}: {writable_detail}"))
    runs_perm_ok, runs_perm_detail = _permissions_ok(runs_dir, 0o700)
    checks.append(_check("runs_permissions", runs_perm_ok, f"{runs_dir}: {runs_perm_detail}", severity="warning"))
    ssot_perm_ok, ssot_perm_detail = _permissions_ok(ssot_path, 0o600)
    checks.append(_check("ssot_permissions", ssot_perm_ok, f"{ssot_path}: {ssot_perm_detail}", severity="warning"))

    free_bytes = shutil.disk_usage(runs_dir).free if runs_dir.exists() else shutil.disk_usage(runs_dir.parent).free
    free_gib = free_bytes / (1024**3)
    checks.append(
        _check(
            "disk_space",
            free_gib >= 5,
            f"Free disk space near runs dir: {free_gib:.2f} GiB",
            severity="warning",
        )
    )

    port_ok, port_detail = _is_port_bindable("127.0.0.1", port)
    checks.append(_check("backend_port", port_ok, f"127.0.0.1:{port} {port_detail}", severity="warning"))

    return _finalize_report(checks)


def _finalize_report(checks: list[dict]) -> dict:
    failures = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    warnings = [check for check in checks if not check["ok"] and check["severity"] == "warning"]
    return {
        "status": "ok" if not failures else "error",
        "summary": {
            "checks_total": len(checks),
            "errors": len(failures),
            "warnings": len(warnings),
        },
        "checks": checks,
    }
