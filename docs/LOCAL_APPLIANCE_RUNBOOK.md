# {spot} Local Appliance Runbook

Current workspace implementation baseline: `0.5.2`
SSOT baseline: `0.2`
Document date: `2026-05-11`

## Purpose

This runbook defines the minimum operator workflow for running `{spot}` on local Apple Silicon hardware.

It is written for a single-node deployment where the system, models, artifacts, and UI all remain on the same machine.

## Supported Delivery Posture

- local Apple Silicon machine
- local `.xlsx` input and output
- local backend/UI bound to loopback
- primary classifier on MLX
- deterministic Ollama fallback and support lanes

Source and installer status:
- the repo does not currently declare an open-source license file
- the supported posture is a maintained source checkout on the target machine
- there is no supported `.pkg`, `.dmg`, or package-manager installer in the current baseline

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
- native app source: `app/macos/`
- run artifacts: `runs/`
- environment: `.venv/`
- shared model root: `/Users/Shared/Models/spot/`
- shared Hugging Face cache: `/Users/Shared/Models/spot/huggingface/`
- shared Ollama store: `/Users/Shared/Models/spot/ollama/`

## Preflight Checklist

Before first use, confirm:

1. the machine is Apple Silicon
2. Python virtual environment exists at `.venv/`
3. dependencies from `requirements.txt` are installed
4. `mlx_lm` is available for MLX inference
5. required local model weights are available under `/Users/Shared/Models/spot/` or an explicitly configured `SPOT_*` model root override
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

## Shared Model Install On A New Machine

Use this when provisioning `{spot}` on another Apple Silicon machine.

Target shared layout:
- `/Users/Shared/Models/spot/huggingface/`
- `/Users/Shared/Models/spot/ollama/`
- `/Users/Shared/Models/spot/mlx-local/`
- `/Users/Shared/Models/spot/manifest/`

Expected runtime environment:
- `SPOT_MODELS_HOME=/Users/Shared/Models/spot`
- `SPOT_HF_HOME=/Users/Shared/Models/spot/huggingface`
- `SPOT_HF_HUB_CACHE=/Users/Shared/Models/spot/huggingface/hub`
- `SPOT_OLLAMA_MODELS=/Users/Shared/Models/spot/ollama`
- `SPOT_MLX_MODELS_DIR=/Users/Shared/Models/spot/mlx-local`
- `HF_HOME=/Users/Shared/Models/spot/huggingface`
- `HF_HUB_CACHE=/Users/Shared/Models/spot/huggingface/hub`
- `OLLAMA_MODELS=/Users/Shared/Models/spot/ollama`

Recommended install order:
1. check out the repo and create `.venv/`
2. run `python3 -m src.cli bootstrap ...`
3. populate `/Users/Shared/Models/spot/huggingface/` with the required MLX/Hugging Face cache content, including `mlx-community/Apertus-8B-Instruct-2509-4bit`
4. populate `/Users/Shared/Models/spot/ollama/` with the required Ollama model store content
5. optionally replace `~/.cache/huggingface` with a symlink to `/Users/Shared/Models/spot/huggingface` for compatibility with tools that still probe the legacy per-user cache path
6. run `.venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` and require `warnings=0` before operator use

Required `{spot}` model set on a fresh machine:
- MLX primary: `mlx-community/Apertus-8B-Instruct-2509-4bit`
- Ollama: `qwen2.5:7b`
- Ollama: `granite4:350m`
- Ollama: `gemma3:1b`
- Ollama: `llama3.2:1b`
- Ollama: `llama3.2:3b`
- Ollama: `gemma2:2b`
- Ollama evaluation: `gemma2:9b`
- Ollama evaluation: `llama3.1:8b`

Current maintainer note:
- on this machine the legacy `~/.cache/huggingface` path is now a symlink to `/Users/Shared/Models/spot/huggingface`
- preflight is the canonical verification step for confirming that the shared model roots are complete and that the required model set is available

## Start Procedure

From the project root:

```bash
cd /Users/moldovancsaba/Projects/spot
cd app/macos
swift build
bash build-bundle.sh
bash install-bundle.sh
open /Applications/spot.app
```

Expected result:
- the native app starts locally
- the supervised backend starts on loopback
- the native SwiftUI workspace becomes available
- no remote bind is required for normal operation

Supported native build validation:
- `swift build`
- `bash build-bundle.sh`
- `bash install-bundle.sh`

## Update Procedure

Use this path for supported maintenance updates on a machine that already runs `{spot}`:

1. update the checked-out source tree under `/Users/moldovancsaba/Projects/spot`
2. rerun bootstrap if environment or directory expectations changed
3. rerun preflight
4. rebuild the native bundle with `app/macos/build-bundle.sh`
5. reinstall the app with `app/macos/install-bundle.sh`
6. relaunch `/Applications/spot.app`
7. rerun native acceptance smoke and any required benchmark/UAT checks before operator sign-off

Current native dashboard capabilities:
- queue one or more `.xlsx` workbooks into local intake
- inspect accepted uploads and their queue segmentation summary
- monitor run state, row progress, segment progress, elapsed time, and average seconds per row
- pause, resume, or stop the active run from the main dashboard
- inspect unfinished runs, including resumable, retryable, and broken recovery candidates
- delete an inactive unfinished run and purge its managed source workbook when no other run still depends on that upload
- open review-required rows and retrieve artifacts locally

Native app note:
- `spot.app` currently uses a separate native-local workflow with watched-folder intake, native inbox history, and local run/upload fallback state
- native app source of truth lives in `app/macos/`
- generated native build folders `.build/` and `dist/` under `app/macos/` are disposable and intentionally untracked
- native runtime shutdown is now expected to suspend active segment-worker runs for later recovery instead of cancelling them
- relaunching `spot.app` is expected to restart the loopback backend and recover an interrupted resumable run when segment state remains queued
- native settings now surface the effective shared model-root paths for `SPOT_MODELS_HOME`, `SPOT_HF_HOME`, `SPOT_HF_HUB_CACHE`, `SPOT_OLLAMA_MODELS`, and `SPOT_MLX_MODELS_DIR`
- this runbook describes the supported native dashboard recovery logic and watched-folder automation contract

## Interrupted Run Recovery

The native workspace now exposes unfinished runs as recovery candidates instead of treating them as hidden backend state.

Recovery-candidate semantics:
- `resume`: an attached paused worker still exists and can continue in place
- `recover`: the run is upload-backed, queued segment state remains, and the native app can restart the segment worker against the same canonical run state
- `retry`: the run is not upload-backed but the source workbook and start payload still exist for a clean restart
- `broken`: the native app found missing source state, missing start payload, or stale run metadata and cannot continue safely without operator repair

Operator expectations:
- use the unfinished-run list after relaunch to verify whether a stopped run is resumable, retryable, or broken
- prefer `recover` for interrupted upload-backed runs because it preserves committed canonical row and segment state
- use deletion only for inactive runs you intentionally want to discard
- if deletion is requested with managed intake data, `{spot}` only purges the stored upload when no other run still references that upload

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

## Bounded Trinity/Train Export

Before exporting or handing off a bundle, complete the [interim classification review safeguard](#interim-classification-review-safeguard). The export reads native review records, not the separate protected review record; external decisions are not automatically incorporated. It can include a row whose native state is `escalated` if a `confirm` or `adjust` decision is present. The acceptance lead must reconcile the actual export rows against the protected record and hold any export containing unresolved cases. Saving decisions on flagged rows alone does not establish that this check is complete.

```bash
.venv/bin/python -m src.cli export-trinity-spot-bundles \
  --run-id local-run-001 \
  --runs-dir runs \
  --company-id company-1 \
  --output-dir runs/local-run-001/trinity_bundles
```

Expected result:
- reviewed Spot rows are exported as `trinity.spot.v1alpha1` `spot-review-policy-learning` bundle files
- the exported bundle files can be handed to the bounded `{train}` Spot review-policy proposal lane

## Monitoring Procedure

Main local backend URL:
- `http://127.0.0.1:8765/api/health`

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

### Interim classification review safeguard

Until the failure-outcome contract is corrected and validated, treat every output as a classification proposal requiring human review before a consequential decision or external handoff. A `Not Antisemitic` assignment, a high confidence score, `Review Required = NO`, or an empty native review queue does not establish that analysis succeeded or that content is benign. The current runtime can convert a missing or invalid model category to the fallback without reliably marking the row for review; a missing model category may leave no distinguishable flag in the workbook. An explanation is model-generated and is not independent proof.

Use this procedure for **full, partial, and none** review modes, including existing runs:

1. The operator records the run ID and review mode, obtains the output workbook through the artifact workflow, and preserves the source workbook and run artifacts unchanged according to the organization's approved access and retention policy. Do not make the only copy of evidence an edited workbook. If the output is missing, incomplete, unreadable, or has missing/ambiguous headers, stop the handoff and escalate to the maintainer without sending source text or artifacts through an unauthorized channel.
2. A designated reviewer examines every processed row against the original `Post text`, not just rows in the native review queue. Inspect `Raw Category`, `Assigned Category`, `Flags`, `Fallback Events`, `Model Version`, `Confidence Score`, `Review Mode`, and `Review Required`. The native queue is populated from rows marked review-required; it can omit rows that this safeguard requires checking. Compare against the original text and preserve context limitations.
3. Escalate any missing or invalid raw category; any `TAXONOMY_VIOLATION`, `MODEL_REQUEST_FAILED`, `CLASSIFIER_FALLBACK_FAILED`, `CLASSIFIER_FALLBACK`, `UNSTRUCTURED_MODEL_OUTPUT`, `EMPTY_TEXT`, `SKIPPED`, `SECOND_PASS_UNAVAILABLE`, or `JUDGE_UNAVAILABLE` flag; and any non-empty `Fallback Events`. Also escalate disagreement or an unclear explanation. Do not assume an empty flag or apparently valid raw category proves the model actually supplied a valid category: missing output can be normalized without a reliable marker. If the reviewer cannot determine what happened, treat the row as unresolved.
4. For a row available in the native review queue, the reviewer records the appropriate review state, decision, and note there. An unqueued row cannot be assumed to be editable in that workflow. Record its row identifier, decision and escalation in the organization's approved access-controlled review record; do not alter the original evidence or include source text in operational logs. Native decisions and notes are stored separately and do not rewrite `Assigned Category` in the output workbook. Provide an authorized, linked review record with the workbook so downstream users can distinguish reviewed decisions from original labels; otherwise hold the handoff. If no approved review record or qualified reviewer is available, hold the handoff and contact the run owner.
5. The run owner or designated acceptance lead reconciles input rows against output and run counts, including any configured row limit. A workbook may retain source rows with blank classification columns when the run was limited; those rows were not analyzed. Hold the handoff if unprocessed rows are not explicitly identified and handled under the organization's policy. Check that every processed row has a documented disposition and that unresolved cases are held or escalated. Record the reviewer, decision, run ID, row identifiers and outstanding limitations in the protected review record. Native sign-off checks the run and queued review state, but does not perform this external cross-check or cover unqueued rows by itself.

For example, a synthetic row with `Raw Category = invalid-label`, `Assigned Category = Not Antisemitic`, `Confidence Score = 0.99`, `Flags = TAXONOMY_VIOLATION`, and `Review Required = NO` must be escalated under step 3. The confidence value and `NO` do not override the violation. This is a synthetic control-flow example, not a measured model prediction.

This is an interim manual control, not an automated guarantee or a legal determination. If examining every row is not feasible, do not represent the run as fully reviewed. Classification-failure handling and consumer contracts are tracked separately in issue #80.

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

## Removal Guidance

If a machine must be decommissioned:
- archive retained `runs/` evidence first if audit retention applies
- remove `/Applications/spot.app`
- remove or archive the configured runtime directories under `~/Library/Application Support/spot/`
- remove the source checkout only after evidence retention and handover obligations are complete

## Handover Note

This runbook is the first local-appliance baseline.
It should be expanded alongside install scripts, preflight automation, and acceptance checklists during the next hardening steps.
