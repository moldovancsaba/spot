#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${SPOT_TEST_PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN=python
fi
"$PYTHON_BIN" -m compileall -q src backend
"$PYTHON_BIN" -m unittest backend.backend_contract_regression backend.ops_queue_regression src.targeted_adjudication_regression src.soft_signal_regression src.failure_contract_regression src.trinity_spot_bundle_regression src.acceptance_regression backend.case_report_regression src.auto_resolution_regression backend.automatic_report_regression
