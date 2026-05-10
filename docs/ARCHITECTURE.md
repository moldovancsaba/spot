# {spot} Architecture

`{spot}` stands for `Smart Platform for Observing Threats`.

Current workspace implementation: `0.5.1`
Pipeline version: `mvp-0.5.1`
SSOT version: `0.2`

## System Boundary

{spot} is a local, deterministic `.xlsx` classification system.
It processes text already present in Excel rows and produces governed Excel outputs plus audit artifacts.

The current product phase exposes a native macOS operator workspace over this runtime. That native shell does not change the system boundary: `{spot}` remains `.xlsx`-only, local-first, and auditable.
The native workspace is implemented in SwiftUI and supervises the loopback FastAPI backend as a local runtime contract, not as a second product surface.

## Main Components

- CLI entrypoint: [`src/cli.py`](/Users/moldovancsaba/Projects/spot/src/cli.py)
- Classification pipeline: [`src/pipeline.py`](/Users/moldovancsaba/Projects/spot/src/pipeline.py)
- Classifier + runtime adapters: [`src/classifier.py`](/Users/moldovancsaba/Projects/spot/src/classifier.py)
- Lane defaults and model-spec parsing: [`src/lanes.py`](/Users/moldovancsaba/Projects/spot/src/lanes.py)
- SSOT loader and validation: [`src/ssot_loader.py`](/Users/moldovancsaba/Projects/spot/src/ssot_loader.py)
- Excel ingestion/output: [`src/excel_io.py`](/Users/moldovancsaba/Projects/spot/src/excel_io.py)
- Evaluation runner: [`src/evaluation/evaluate.py`](/Users/moldovancsaba/Projects/spot/src/evaluation/evaluate.py)
- Native app supervisor and operator workspace: [`app/macos/`](/Users/moldovancsaba/Projects/spot/app/macos)
- Monitoring backend: [`backend/main.py`](/Users/moldovancsaba/Projects/spot/backend/main.py)
- Local operations index: [`backend/services/ops_db_service.py`](/Users/moldovancsaba/Projects/spot/backend/services/ops_db_service.py)

## Data Flow

1. Validate SSOT
2. Validate workbook schema
3. Read input rows
4. Normalize text with drafter lane
5. Classify with classifier lane
6. Enforce taxonomy and fallback rules
7. Apply review policy
8. Write output workbook
9. Persist integrity, policy, progress, logs, and queue snapshots
10. Surface upload, run, review, and segment status through the native macOS operator workspace

## Runtime Paths

Standard classification path:
- `drafter -> classifier`

Disagreement and evaluation path:
- `drafter -> classifier -> judge`

The `judge` is not invoked on every standard single-model row classification.

## Agent Topology

- `drafter`: normalization only
- `classifier`: category authority
- `judge`: disagreement scoring only

No writer lane exists in {spot}.

## Runtime Routing

Primary runtime:
- `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Fallback / support runtimes:
- `ollama://qwen2.5:7b`
- `ollama://granite4:350m`
- `ollama://gemma3:1b`
- `ollama://llama3.2:1b`
- `ollama://llama3.2:3b`
- `ollama://gemma2:2b`

## Security Controls

- Ollama loopback-only by default
- remote Ollama requires explicit override
- API/UI loopback bind
- deterministic settings pinned in code
- no training loop on processed client data

## Audit Controls

Each run records:
- resolved lane config
- resolved model versions
- prompt / taxonomy / SSOT / pipeline versions
- run language and review mode
- category and flag distributions
- integrity validation result
