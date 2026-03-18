#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
UVICORN_BIN="${ROOT_DIR}/.venv/bin/uvicorn"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing Python virtual environment at .venv/bin/python" >&2
  exit 1
fi

if [[ ! -x "${UVICORN_BIN}" ]]; then
  echo "Missing uvicorn entrypoint at .venv/bin/uvicorn" >&2
  exit 1
fi

if [[ "${SPOT_RUN_PREFLIGHT:-1}" == "1" ]]; then
  "${PYTHON_BIN}" -m src.cli preflight \
    --ssot ssot/ssot.json \
    --runs-dir runs \
    --port 8765
fi

exec "${UVICORN_BIN}" backend.main:app --host 127.0.0.1 --port 8765
