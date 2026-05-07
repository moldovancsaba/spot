# {spot} Local Appliance Runbook

Current workspace implementation baseline: `0.4.1`
SSOT baseline: `0.2`
Document date: `2026-05-03`

## Purpose

This runbook defines the minimum operator workflow for running `{spot}` on local Apple Silicon hardware.

It is written for a single-node deployment where the system, models, artifacts, and UI all remain on the same machine.

## Supported Delivery Posture

- local Apple Silicon machine
- local `.xlsx` input and output
- local backend/UI bound to loopback
- primary classifier on MLX
- deterministic Ollama fallback and support lanes

## Runtime Baseline

- classifier primary: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://granite4:350m`
- drafter fallbacks: `ollama://gemma3:1b`, `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`
- SSOT: `ssot/ssot.json`
- backend bind: `127.0.0.1:8765`

## Expected Local Layout

Project root:
- `/Users/moldovancsaba/Projects/spot`

Key locations:
- input examples: `samples/`
- SSOT: `ssot/`
- backend: `backend/`
- runtime code: `src/`
- run artifacts: `runs/`
- environment: `.venv/`

## Preflight Checklist

Before first use, confirm:

1. the machine is Apple Silicon
2. Python virtual environment exists at `.venv/`
3. dependencies from `requirements.txt` are installed
4. `mlx_lm` is available for MLX inference
5. required local model weights are available
6. Ollama is installed if fallback and support lanes are required
7. the configured Ollama endpoint resolves to loopback only
8. `ssot/ssot.json` loads without validation failure
9. the `runs/` directory is writable
10. sufficient free disk space exists for new run artifacts

## Bootstrap Command

Use this to prepare the local runtime skeleton on a clean machine:

```bash
cd /Users/moldovancsaba/Projects/spot
python3 -m src.cli bootstrap \
  --project-root . \
  --venv-path .venv \
  --requirements requirements.txt \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --logs-dir logs
```

What it does:
- creates `runs/` if missing
- creates `logs/` if missing
- creates `.venv/` if missing
- restricts local permissions on `runs/`, `logs/`, and the SSOT file
- installs `requirements.txt` unless `--skip-install` is used

For a dry bootstrap without package installation:

```bash
python3 -m src.cli bootstrap \
  --project-root . \
  --venv-path .venv \
  --requirements requirements.txt \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --logs-dir logs \
  --skip-install
```

## Start Procedure

From the project root:

```bash
cd /Users/moldovancsaba/Projects/spot
chmod +x start_browser_appliance.sh
bash start_browser_appliance.sh
```

Expected result:
- startup preflight runs first unless `SPOT_RUN_PREFLIGHT=0`
- backend starts locally
- browser operator surface becomes available on loopback
- no remote bind is required for normal operation

Supported appliance entrypoint:
- `start_browser_appliance.sh`
- override `SPOT_RUN_PREFLIGHT=0` only for deliberate local dev restarts

Supported browser startup URL:

- dashboard: `http://127.0.0.1:8765/app`
- root path alias: `http://127.0.0.1:8765/`

Supported browser verification command:

```bash
cd /Users/moldovancsaba/Projects/spot
.venv/bin/python backend/browser_operator_smoke.py
```

Expected verification result:
- local auth succeeds
- upload intake succeeds
- browser operator pages render
- review/sign-off/recovery seams respond successfully

Verification boundary:
- this smoke command validates the browser integration seams inside the local app
- it does not replace live benchmark/UAT execution on the target delivery machine

Current browser dashboard capabilities:
- queue one or more `.xlsx` workbooks into local intake
- inspect accepted uploads and their queue segmentation summary
- monitor run state, row progress, segment progress, elapsed time, and average seconds per row
- pause, resume, or stop the active run from the main dashboard
- open review-required rows and retrieve artifacts locally

Native app note:
- `spot.app` currently uses a separate native-local workflow with watched-folder intake, native inbox history, and local run/upload fallback state
- native runtime shutdown is now expected to suspend active segment-worker runs for later recovery instead of cancelling them
- relaunching `spot.app` is expected to restart the loopback backend and recover an interrupted resumable run when segment state remains queued
- the browser runbook above does not describe the native dashboard recovery logic or its watched-folder automation contract

## Preflight Command

Run before first use on a machine or after runtime changes:

```bash
cd /Users/moldovancsaba/Projects/spot
source .venv/bin/activate
.venv/bin/python -m src.cli preflight \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --port 8765
```

Expected result:
- JSON report is printed
- exit code is `0` if required checks pass
- exit code is non-zero if required checks fail
- production mode should use the locked SSOT path only

## Classification Procedure

Example command:

```bash
.venv/bin/python -m src.cli classify \
  --input samples/sample_germany.xlsx \
  --output samples/sample_germany_out.xlsx \
  --run-id local-run-001 \
  --language de \
  --review-mode partial \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --max-workers 1
```

Expected result:
- output workbook is produced
- run artifacts are written under `runs/local-run-001/`

## Monitoring Procedure

Main local URLs:
- `http://127.0.0.1:8765/app`
- `http://127.0.0.1:8765/classify-monitor`
- `http://127.0.0.1:8765/agent-eval`

Operator checks:
- run state moves through validation, processing, writing, completion
- row and segment counters advance on the main dashboard during processing
- `progress.json` and `processing_stats.json` update during processing
- `integrity_report.json` exists after completion

## Artifact Checklist

Each successful classification run should retain:
- `progress.json`
- `processing_stats.json`
- `integrity_report.json`
- `policy.json`
- `output.xlsx`
- `logs.txt`

Runs started from the backend should also retain:
- `control.json`

Completed runs should also retain:
- `artifact_manifest.json`

Ensemble disagreement paths should also retain:
- `disagreement_report.json`

## Fallback And Failure Handling

Expected failure classes:
- malformed workbook schema
- empty input after filtering
- MLX runtime unavailable
- classifier request failure
- local storage or write failure

Operator response:
- do not modify run artifacts manually
- inspect `logs.txt`, `progress.json`, and `integrity_report.json` if present
- verify whether fallback was activated in `Fallback Events` and run artefacts
- rerun only after the failure cause is understood

## Recovery Notes

If MLX primary route fails:
- verify local model availability
- verify `mlx_lm` availability
- confirm fallback artifacts correctly record the resolved model version and fallback flags

If backend/UI is unavailable:
- confirm the process is running
- confirm port `8765` is free
- restart the local backend on loopback only

If output workbook is missing:
- inspect `runs/<run-id>/logs.txt`
- inspect `runs/<run-id>/progress.json`
- confirm output directory is writable

## Backup Guidance

Minimum retained material:
- SSOT files
- output workbooks delivered to operators
- `runs/` artifacts required for audit and support

Recommended approach:
- copy artifacts to an external backup volume after accepted runs
- avoid editing archived artifacts after a run is complete

## Handover Note

This runbook is the first local-appliance baseline.
It should be expanded alongside install scripts, preflight automation, and acceptance checklists during the next hardening steps.
