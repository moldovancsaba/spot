# {spot}
**{spot} - Smart Platform for Observing Threats**

AI-assisted antisemitism classification system with SSOT-governed, auditable local processing.

Current workspace implementation: `0.4.0`
Pipeline version: `mvp-0.4.0`
Authoritative SSOT version: `0.2`
Latest shipped release notes in repo: [`docs/RELEASE_NOTES_0.3.1.md`](/Users/moldovancsaba/Projects/spot/docs/RELEASE_NOTES_0.3.1.md)

Documentation map:
- [README Brief](/Users/moldovancsaba/Projects/spot/README_BRIEF.md)
- [Architecture](/Users/moldovancsaba/Projects/spot/docs/ARCHITECTURE.md)
- [Browser Operator Contract](/Users/moldovancsaba/Projects/spot/docs/BROWSER_OPERATOR_CONTRACT.md)
- [Browser Productionization Contract](/Users/moldovancsaba/Projects/spot/docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md)
- [Production Plan](/Users/moldovancsaba/Projects/spot/docs/PRODUCTION_PLAN.md)
- [Client Package](/Users/moldovancsaba/Projects/spot/docs/CLIENT_PACKAGE.md)
- [Local Appliance Runbook](/Users/moldovancsaba/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)
- [Benchmark Checklist](/Users/moldovancsaba/Projects/spot/docs/BENCHMARK_CHECKLIST.md)
- [UAT Checklist](/Users/moldovancsaba/Projects/spot/docs/UAT_CHECKLIST.md)
- [Acceptance Evidence Template](/Users/moldovancsaba/Projects/spot/docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md)
- [Release Notes 0.3.1](/Users/moldovancsaba/Projects/spot/docs/RELEASE_NOTES_0.3.1.md)
- [Release Notes 0.3.0 (Historical)](/Users/moldovancsaba/Projects/spot/docs/RELEASE_NOTES_0.3.0.md)

{spot} is a deterministic, auditable classification platform for large Excel batches of social media posts.
It enforces a strict closed-set taxonomy, produces explainable metadata, and writes governed outputs to Excel.

## What {spot} Is

- Input/output: `.xlsx` only
- One language per run
- Exactly one category per row
- Closed taxonomy only
- Deterministic local inference
- Explainable metadata per row
- Full run artifacts for audit and legal/regulatory review

## What {spot} Is Not

- OCR or document scanning
- Image or video analysis
- URL crawling
- Automatic language detection
- Multi-label classification
- Taxonomy CRUD or schema CRUD

Current next-phase product contract:
- browser operator experience remains scoped to local `.xlsx` upload, run monitoring, review, annotation, and artifact retrieval
- the implementation contract for that phase is [`docs/BROWSER_OPERATOR_CONTRACT.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_OPERATOR_CONTRACT.md)

Current implementation stage:
- core deterministic runtime is implemented
- local browser operator workflow is implemented
- productionization verification is in progress
- live client acceptance on the current browser-enabled baseline is still pending

## Canonical Taxonomy

- `Anti-Israel`
- `Anti-Judaism`
- `Classical Antisemitism`
- `Structural Antisemitism`
- `Conspiracy Theories`
- `Not Antisemitic`

## Production Runtime Truth

Primary classifier route is SSOT-governed and Apertus-first:
- `classifier`: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- `classifier fallback`: `ollama://qwen2.5:7b`
- `drafter`: `ollama://granite4:350m`
- `drafter fallbacks`: `ollama://gemma3:1b` -> `ollama://llama3.2:1b`
- `judge`: `ollama://llama3.2:3b`
- `judge fallback`: `ollama://gemma2:2b`

Evaluation defaults remain explicit and deterministic:
- single-model benchmark: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- ensemble benchmark: `ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b`
- legacy Ollama tags such as `qwen2.5:7b` still resolve to Ollama for backward compatibility

## Control Principle

`LLM output -> normalization -> validation -> canonical category -> write`

## Pipeline

1. Load and validate SSOT from [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json)
2. Validate `.xlsx` schema against required columns
3. Read row text into deterministic batch processing
4. Normalize text through the internal `drafter` lane
5. Classify through the `classifier` lane
6. Normalize label and enforce closed taxonomy
7. Apply review policy and flags
8. Write governed metadata columns into output workbook
9. Run post-write integrity checks and persist artifacts

## Determinism Guarantees

- `temperature=0`
- `top_p=1`
- fixed seed
- deterministic fallback handling
- versioned SSOT / prompt / model route / pipeline in artifacts
- no stochastic rerun strategy

## Security Defaults

- API binds to `127.0.0.1`
- Ollama default endpoint is `http://127.0.0.1:11434/api/generate`
- Remote Ollama endpoints are blocked unless `SPOT_ALLOW_REMOTE_OLLAMA=1`
- MLX is intended for locally available Apertus weights
- No training on client data is part of {spot}

## Quick Start

```bash
cd /Users/moldovancsaba/Projects/spot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run deterministic classification:

```bash
.venv/bin/python -m src.cli classify \
  --input samples/sample_germany.xlsx \
  --output samples/sample_germany_out.xlsx \
  --run-id run-001 \
  --language de \
  --review-mode partial \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --max-workers 1
```

Run local appliance preflight:

```bash
.venv/bin/python -m src.cli preflight \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --port 8765
```

Bootstrap local appliance setup:

```bash
python3 -m src.cli bootstrap \
  --project-root . \
  --venv-path .venv \
  --requirements requirements.txt \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --logs-dir logs
```

Run single-vs-ensemble evaluation:

```bash
.venv/bin/python -m src.cli evaluate \
  --input samples/sample_germany.xlsx \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --evaluation-run-id eval-2000 \
  --language de \
  --review-mode partial \
  --single-model mlx://mlx-community/Apertus-8B-Instruct-2509-4bit \
  --ensemble-models ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b \
  --max-workers 1 \
  --limit 500 \
  --progress-every 10
```

Start the supported local browser appliance on port `8765`:

```bash
chmod +x start_browser_appliance.sh
bash start_browser_appliance.sh
```

Browser-intake foundation endpoints:

- `POST /uploads/intake` with raw `.xlsx` request body and `X-Filename` header
- `GET /uploads`
- `GET /uploads/{upload_id}`
- `POST /classify/start/{run_id}` with `{"upload_id":"..."}` to start from an accepted intake record

Browser-state foundation endpoints:

- `GET /runs/{run_id}/state`
- `GET /runs/{run_id}/detail`
- `GET /runs/{run_id}/review-rows`
- `GET /runs/{run_id}/review-rows/{row_index}`
- `GET /runs/{run_id}/artifacts`
- `POST /runs/{run_id}/review-rows/{row_index}`
- `GET /runs/{run_id}/actions`
- `POST /runs/{run_id}/signoff`
- `POST /runs/{run_id}/cancel`
- `POST /runs/{run_id}/retry`
- `POST /runs/{run_id}/recover`

Browser run-operation endpoints:

- `POST /classify/pause/{run_id}`
- `POST /classify/resume/{run_id}`
- `POST /classify/stop/{run_id}`
- `GET /classify/status/{run_id}`

Browser auth and permission endpoints:

- `GET /auth/config`
- `GET /auth/session`
- `POST /auth/login`
- `POST /auth/logout`

Local browser auth defaults:

- auth is enabled by default with `SPOT_AUTH_ENABLED=1`
- local shared access code defaults to `spot-local`
- rotate the shared local code with `SPOT_LOCAL_ACCESS_CODE`
- role gates currently distinguish `operator`, `reviewer`, `acceptance_lead`, and `admin`
- upload, run start, run recovery actions, review updates, sign-off, and artifact downloads are permission-gated

Browser productionization verification command:

```bash
.venv/bin/python backend/browser_operator_smoke.py
```

The startup script runs local preflight by default before binding the browser appliance. Set `SPOT_RUN_PREFLIGHT=0` only when you intentionally need a faster dev restart.

Current verification boundary:
- `backend/browser_operator_smoke.py` is deterministic integration smoke for browser seams
- it does not replace a live client acceptance run on the target machine
- the historical `0.3.2` acceptance record is archived in [`docs/ACCEPTANCE_EVIDENCE_2026-03-18.md`](/Users/moldovancsaba/Projects/spot/docs/ACCEPTANCE_EVIDENCE_2026-03-18.md)

Browser app shell:

- operator dashboard: [http://127.0.0.1:8765/app](http://127.0.0.1:8765/app)
- root path also resolves to the dashboard: [http://127.0.0.1:8765/](http://127.0.0.1:8765/)
- dedicated run detail page: `http://127.0.0.1:8765/runs/<run_id>/view`
- dedicated review queue page: `http://127.0.0.1:8765/runs/<run_id>/review`
- dedicated row inspector page: `http://127.0.0.1:8765/runs/<run_id>/review-rows/<row_index>/view`
- dedicated artifact center page: `http://127.0.0.1:8765/runs/<run_id>/artifacts/view`

## Monitoring URLs

- Operator dashboard: [http://127.0.0.1:8765/app](http://127.0.0.1:8765/app)
- Classify monitor: [http://127.0.0.1:8765/classify-monitor](http://127.0.0.1:8765/classify-monitor)
- Eval monitor: [http://127.0.0.1:8765/agent-eval](http://127.0.0.1:8765/agent-eval)

## Runtime Configuration

{spot} now resolves runtime defaults from [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json). Environment variables still override them when explicitly set.

Supported overrides:

```bash
export SPOT_ROUTE_CLASSIFIER_BACKEND=mlx
export SPOT_ROUTE_CLASSIFIER_MODEL=mlx-community/Apertus-8B-Instruct-2509-4bit
export SPOT_ROUTE_CLASSIFIER_FALLBACK_BACKEND=ollama
export SPOT_ROUTE_CLASSIFIER_FALLBACK_MODEL=qwen2.5:7b

export SPOT_ROUTE_DRAFTER_BACKEND=ollama
export SPOT_ROUTE_DRAFTER_MODEL=granite4:350m
export SPOT_ROUTE_DRAFTER_FALLBACK_BACKEND=ollama
export SPOT_ROUTE_DRAFTER_FALLBACK_MODEL=gemma3:1b,llama3.2:1b

export SPOT_ROUTE_JUDGE_BACKEND=ollama
export SPOT_ROUTE_JUDGE_MODEL=llama3.2:3b
export SPOT_ROUTE_JUDGE_FALLBACK_BACKEND=ollama
export SPOT_ROUTE_JUDGE_FALLBACK_MODEL=gemma2:2b
```

Security override for exceptional environments only:

```bash
export SPOT_ALLOW_REMOTE_OLLAMA=1
export SPOT_PRODUCTION_MODE=1
export SPOT_LOCKED_SSOT_PATH=ssot/ssot.json
```

## Output Metadata Columns

{spot} appends governed metadata columns including:
- `Assigned Category`
- `Fallback Events`
- `Confidence Score`
- `Explanation / Reasoning`
- `Flags`
- `Model Version`
- `Prompt Version`
- `Taxonomy Version`
- `SSOT Version`
- `Pipeline Version`
- `Run ID`
- `Run Language`
- `Review Mode`
- `Review Required`
- `Row Hash`

`Model Version` now records the resolved runtime route used for that row, for example `mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`.

## Run Artifacts

Each classification run in `runs/<run-id>/` stores:
- `progress.json`
- `integrity_report.json`
- `artifact_manifest.json`
- `policy.json`
- `output.xlsx`
- `logs.txt`
- `disagreement_report.json` when disagreement paths are used
- `control.json` when started via monitoring API

Each evaluation run in `runs/<evaluation-run-id>/` stores:
- `evaluation_report.json`
- `single_output.xlsx`
- `ensemble_output.xlsx`
- linked run IDs

## Documentation Map

- Project brief: [`README_BRIEF.md`](/Users/moldovancsaba/Projects/spot/README_BRIEF.md)
- Client package: [`docs/CLIENT_PACKAGE.md`](/Users/moldovancsaba/Projects/spot/docs/CLIENT_PACKAGE.md)
- Foundation hardening plan: [`docs/FOUNDATION_HARDENING_PLAN.md`](/Users/moldovancsaba/Projects/spot/docs/FOUNDATION_HARDENING_PLAN.md)
- Local appliance runbook: [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/moldovancsaba/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)
- SSOT contract: [`ssot/SSOT.md`](/Users/moldovancsaba/Projects/spot/ssot/SSOT.md)
- SSOT machine config: [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json)
- Architecture: [`docs/ARCHITECTURE.md`](/Users/moldovancsaba/Projects/spot/docs/ARCHITECTURE.md)
- Ingestion contract: [`docs/INGESTION.md`](/Users/moldovancsaba/Projects/spot/docs/INGESTION.md)
- Operational notes: [`docs/BRAIN_DUMP.md`](/Users/moldovancsaba/Projects/spot/docs/BRAIN_DUMP.md)
- Monitoring/UI: [`MONITORING_UI.md`](/Users/moldovancsaba/Projects/spot/MONITORING_UI.md)
- Foundation baseline: [`FOUNDATION.md`](/Users/moldovancsaba/Projects/spot/FOUNDATION.md)
- Design baseline: [`DESIGN.md`](/Users/moldovancsaba/Projects/spot/DESIGN.md)
- Handover log: [`docs/HANDOVER.md`](/Users/moldovancsaba/Projects/spot/docs/HANDOVER.md)
- Changelog: [`CHANGELOG.md`](/Users/moldovancsaba/Projects/spot/CHANGELOG.md)
