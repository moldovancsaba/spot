# {spot}
**{spot} - Smart Platform for Observing Threats**

AI-assisted antisemitism classification system with SSOT-governed, auditable local processing.

Current workspace implementation: `0.3.1`
Pipeline version: `mvp-0.3.1`
Authoritative SSOT version: `0.2`
Latest shipped release notes in repo: [`docs/RELEASE_NOTES_0.3.0.md`](/Users/moldovancsaba/Projects/spot/docs/RELEASE_NOTES_0.3.0.md)

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
- `drafter`: `ollama://gemma3:1b`
- `drafter fallback`: `ollama://llama3.2:1b`
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

Start monitoring API/UI on port `8765`:

```bash
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

## Monitoring URLs

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
export SPOT_ROUTE_DRAFTER_MODEL=gemma3:1b
export SPOT_ROUTE_DRAFTER_FALLBACK_BACKEND=ollama
export SPOT_ROUTE_DRAFTER_FALLBACK_MODEL=llama3.2:1b

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
