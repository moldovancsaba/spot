from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

from .defaults import (
    DEFAULT_HF_HOME,
    DEFAULT_HF_HUB_CACHE,
    DEFAULT_LOCKED_SSOT_PATH,
    DEFAULT_MLX_MODELS_DIR,
    DEFAULT_MODELS_HOME,
    DEFAULT_OLLAMA_MODELS,
    DEFAULT_OLLAMA_URL,
    DEFAULT_PRODUCTION_MODE,
)
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


def _ollama_listener_check(url: str) -> tuple[bool, str]:
    port = urllib.parse.urlparse(url).port or 11434
    lsof = shutil.which("lsof")
    if not lsof:
        return False, "Cannot verify the actual Ollama listener: lsof is unavailable"
    try:
        probe = subprocess.run([lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fn"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False, "Cannot inspect the actual Ollama listener"
    addresses = [line[1:].rsplit(":", 1)[0].strip("[]") for line in probe.stdout.splitlines() if line.startswith("n")]
    local_only = bool(addresses) and all(address in {"127.0.0.1", "::1"} for address in addresses)
    return local_only, "Actual Ollama listener is loopback-only" if local_only else "Ollama is absent or has a non-loopback listener; disable network exposure in Ollama settings"


def _python_dependency_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _python_dependency_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _read_pinned_requirements(requirements_path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    if not requirements_path.exists():
        return pins
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        package_name, version = line.split("==", 1)
        pins[package_name.strip()] = version.strip()
    return pins


def _version_prefix(version: str, parts: int = 2) -> str:
    chunks = re.findall(r"\d+", version)
    return ".".join(chunks[:parts])


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


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:  # noqa: BLE001
        return False


def _huggingface_repo_cache_path(cache_root: Path, repo_id: str) -> Path:
    return cache_root / f"models--{repo_id.replace('/', '--')}"


def _ollama_manifest_path(models_root: Path, model_tag: str) -> Path:
    name, _, variant = model_tag.partition(":")
    manifest_root = models_root / "manifests" / "registry.ollama.ai" / "library" / name
    return manifest_root / variant if variant else manifest_root


def _ollama_model_available(models_root: Path, model_tag: str) -> tuple[bool, str]:
    manifest_path = _ollama_manifest_path(models_root, model_tag)
    if manifest_path.exists():
        return True, f"{model_tag} manifest path: {manifest_path}"
    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
            env={**os.environ, "OLLAMA_MODELS": str(models_root)},
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"{model_tag} manifest path: {manifest_path} (ollama list probe failed: {exc})"
    if model_tag in proc.stdout:
        return True, f"{model_tag} visible via ollama list under OLLAMA_MODELS={models_root}"
    return False, f"{model_tag} manifest path: {manifest_path}"


def _backend_contract_check() -> tuple[bool, str]:
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
    except Exception as exc:  # noqa: BLE001
        return False, f"Backend import/TestClient bootstrap failed: {exc}"
    try:
        client = TestClient(app)
        response = client.get("/auth/config")
    except Exception as exc:  # noqa: BLE001
        return False, f"Backend TestClient request failed: {exc}"
    if response.status_code != 200:
        return False, f"/auth/config returned status {response.status_code}"
    return True, "Backend app imported and TestClient GET /auth/config returned 200"


def _mlx_cli_contract_check() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mlx_lm", "generate", "--help"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"mlx_lm generate --help failed: {exc}"
    output = f"{proc.stdout}\n{proc.stderr}"
    if "--model" not in output or "--prompt" not in output:
        return False, "mlx_lm generate help output no longer exposes --model/--prompt as expected"
    return True, "mlx_lm generate CLI contract exposes --model and --prompt"


def run_preflight(ssot_path: Path, runs_dir: Path, port: int = 8765, inference_smoke: bool = False) -> dict:
    checks: list[dict] = []
    project_root = Path(__file__).resolve().parent.parent
    requirements_path = project_root / "requirements.txt"
    pinned_requirements = _read_pinned_requirements(requirements_path)

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
        ("reportlab", "reportlab"),
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
    required_pins = ["openpyxl", "fastapi", "uvicorn", "mlx", "mlx-lm", "reportlab"]
    for package_name in required_pins:
        pinned_version = pinned_requirements.get(package_name)
        installed_version = _python_dependency_version(package_name)
        checks.append(
            _check(
                f"pinned_{package_name}",
                pinned_version is not None,
                f"requirements.txt pin for {package_name}: {pinned_version or 'missing'}",
            )
        )
        checks.append(
            _check(
                f"installed_{package_name}",
                installed_version is not None,
                f"Installed {package_name} version: {installed_version or 'not installed'}",
            )
        )
        if pinned_version is not None and installed_version is not None:
            checks.append(
                _check(
                    f"lockstep_{package_name}",
                    pinned_version == installed_version,
                    f"{package_name} pinned={pinned_version}, installed={installed_version}",
                )
            )

    primary_route = parse_model_spec(
        f"{ssot.runtime.classifier.backend}://{ssot.runtime.classifier.model}",
        ssot.runtime.classifier.backend,
        ssot.runtime.classifier.model,
    )
    shared_models_root = Path("/Users/Shared/Models")
    models_home = Path(DEFAULT_MODELS_HOME)
    hf_home = Path(DEFAULT_HF_HOME)
    hf_hub_cache = Path(DEFAULT_HF_HUB_CACHE)
    ollama_models_root = Path(DEFAULT_OLLAMA_MODELS)
    mlx_models_dir = Path(DEFAULT_MLX_MODELS_DIR)
    checks.append(
        _check(
            "shared_models_root",
            _path_within(models_home, shared_models_root),
            f"SPOT_MODELS_HOME={models_home}",
            severity="warning",
        )
    )
    checks.append(_check("models_home_exists", models_home.exists(), f"Shared model root: {models_home}", severity="warning"))
    checks.append(_check("hf_home_exists", hf_home.exists(), f"HF_HOME={hf_home}", severity="warning"))
    checks.append(_check("hf_hub_cache_exists", hf_hub_cache.exists(), f"HF_HUB_CACHE={hf_hub_cache}", severity="warning"))
    checks.append(_check("ollama_models_root", ollama_models_root.exists(), f"OLLAMA_MODELS={ollama_models_root}", severity="warning"))
    checks.append(_check("mlx_models_dir", mlx_models_dir.exists(), f"SPOT_MLX_MODELS_DIR={mlx_models_dir}", severity="warning"))
    checks.append(
        _check(
            "mlx_runtime",
            _python_dependency_exists("mlx_lm") if primary_route.backend == "mlx" else True,
            f"Primary classifier route: {primary_route.spec}",
        )
    )
    if primary_route.backend == "mlx":
        if Path(primary_route.model_name).exists():
            mlx_model_available = True
            mlx_model_detail = f"Primary MLX model path exists: {primary_route.model_name}"
        else:
            repo_cache_path = _huggingface_repo_cache_path(hf_hub_cache, primary_route.model_name)
            mlx_model_available = repo_cache_path.exists()
            mlx_model_detail = f"Expected MLX repo cache: {repo_cache_path}"
        checks.append(_check("mlx_model_availability", mlx_model_available, mlx_model_detail, severity="warning"))
        pinned_mlx = pinned_requirements.get("mlx")
        pinned_mlx_lm = pinned_requirements.get("mlx-lm")
        installed_mlx = _python_dependency_version("mlx")
        installed_mlx_lm = _python_dependency_version("mlx-lm")
        checks.append(
            _check(
                "mlx_pin_pair",
                bool(pinned_mlx and pinned_mlx_lm and _version_prefix(pinned_mlx) == _version_prefix(pinned_mlx_lm)),
                f"requirements.txt mlx={pinned_mlx or 'missing'}, mlx-lm={pinned_mlx_lm or 'missing'}",
            )
        )
        checks.append(
            _check(
                "mlx_installed_pair",
                bool(installed_mlx and installed_mlx_lm and _version_prefix(installed_mlx) == _version_prefix(installed_mlx_lm)),
                f"installed mlx={installed_mlx or 'missing'}, mlx-lm={installed_mlx_lm or 'missing'}",
            )
        )
        mlx_cli_ok, mlx_cli_detail = _mlx_cli_contract_check()
        checks.append(_check("mlx_cli_contract", mlx_cli_ok, mlx_cli_detail))

    backend_ok, backend_detail = _backend_contract_check()
    checks.append(_check("backend_contract", backend_ok, backend_detail))

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
                severity="warning",
            )
        )
        required_ollama_models = {
            ssot.runtime.classifier.fallback_model,
            ssot.runtime.drafter.model,
            ssot.runtime.judge.model,
            ssot.runtime.judge.fallback_model,
        }
        required_ollama_models.update(model.strip() for model in ssot.runtime.drafter.fallback_model.split(",") if model.strip())
        required_ollama_models.update(
            route.model_name
            for route in (parse_model_spec(model_spec, "ollama") for model_spec in ssot.runtime.evaluation.ensemble_models)
            if route.backend == "ollama"
        )
        for model_tag in sorted(required_ollama_models):
            available, detail = _ollama_model_available(ollama_models_root, model_tag)
            checks.append(
                _check(
                    f"ollama_model_{model_tag.replace(':', '_')}",
                    available,
                    detail,
                    severity="warning",
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

    if is_loopback:
        listener_ok, listener_detail = _ollama_listener_check(DEFAULT_OLLAMA_URL)
        checks.append(_check("ollama_listener", listener_ok, listener_detail))

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

    if inference_smoke:
        checks.extend(_inference_smoke_checks(ssot))
    report = _finalize_report(checks)
    report["inference_status"] = ("passed" if all(c["ok"] for c in checks if c["name"].startswith("inference_")) else "failed") if inference_smoke else "not_checked"
    return report


def _inference_smoke_checks(ssot) -> list[dict]:
    from .classifier import _classify_with_backend
    from .failure_policy import MANDATORY_REVIEW_FLAGS

    checks = []
    # Synthetic input only. Never include model output or source text in the report.
    routes = [
        ("primary", ssot.runtime.classifier.backend, ssot.runtime.classifier.model),
        ("fallback", ssot.runtime.classifier.fallback_backend, ssot.runtime.classifier.fallback_model),
    ]
    for name, backend, model in routes:
        try:
            result = _classify_with_backend("Das Wetter ist heute sonnig.", ssot, backend, model)
            ok = result.raw_category == "Not Antisemitic" and not (set(result.flags) & MANDATORY_REVIEW_FLAGS)
            detail = f"{backend} structured classifier response: {'passed' if ok else 'failed'}"
        except Exception as exc:
            ok = False
            detail = f"{backend} classifier request failed ({type(exc).__name__})"
        checks.append(_check(f"inference_{name}", ok, detail))
    return checks


def _finalize_report(checks: list[dict]) -> dict:
    failures = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    warnings = [check for check in checks if not check["ok"] and check["severity"] == "warning"]
    return {
        "status": "ok" if not failures else "error",
        "inference_status": "not_checked",
        "summary": {
            "checks_total": len(checks),
            "errors": len(failures),
            "warnings": len(warnings),
        },
        "checks": checks,
    }
