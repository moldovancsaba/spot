# {spot} Architecture

`{spot}` stands for `Smart Platform for Observing Threats`.

Current workspace implementation: `0.5.2`
Pipeline version: `mvp-0.5.2`
SSOT version: `0.4`

## System Boundary

{spot} is a local, deterministic `.xlsx` classification system.
It processes text already present in Excel rows and produces governed Excel outputs plus audit artifacts.

The current product phase exposes a native macOS operator workspace over this runtime. That native shell does not change the system boundary: `{spot}` remains `.xlsx`-only, local-first, and auditable.
The native workspace is implemented in SwiftUI and supervises the loopback FastAPI backend as a local runtime contract, not as a second product surface.

## Main Components

- CLI entrypoint: [`src/cli.py`](/Users/Shared/Projects/spot/src/cli.py)
- Classification pipeline: [`src/pipeline.py`](/Users/Shared/Projects/spot/src/pipeline.py)
- Classifier + runtime adapters: [`src/classifier.py`](/Users/Shared/Projects/spot/src/classifier.py)
- Lane defaults and model-spec parsing: [`src/lanes.py`](/Users/Shared/Projects/spot/src/lanes.py)
- SSOT loader and validation: [`src/ssot_loader.py`](/Users/Shared/Projects/spot/src/ssot_loader.py)
- Excel ingestion/output: [`src/excel_io.py`](/Users/Shared/Projects/spot/src/excel_io.py)
- Evaluation runner: [`src/evaluation/evaluate.py`](/Users/Shared/Projects/spot/src/evaluation/evaluate.py)
- Trinity/Train export seam: [`src/trinity_spot_bundle.py`](/Users/Shared/Projects/spot/src/trinity_spot_bundle.py)
- Native app supervisor and operator workspace: [`app/macos/`](/Users/Shared/Projects/spot/app/macos)
- Monitoring backend: [`backend/main.py`](/Users/Shared/Projects/spot/backend/main.py)
- Run state projection and artifact helpers: [`backend/services/run_state_service.py`](/Users/Shared/Projects/spot/backend/services/run_state_service.py)
- Local operations index: [`backend/services/ops_db_service.py`](/Users/Shared/Projects/spot/backend/services/ops_db_service.py)
- Upload-backed segment worker: [`backend/segment_worker.py`](/Users/Shared/Projects/spot/backend/segment_worker.py)

## Canonical Persistence Model

The active runtime truth is split across governed files and the local operations database.

Indexed database entities:
- `uploads`: accepted upload metadata and row counts
- `upload_rows`: canonical accepted input rows with immutable source provenance
- `runs`: indexed run snapshots used for dashboard and lifecycle summaries
- `run_attempts`: explicit start/resume attempt history
- `segments`: queue ownership and segment progress state
- `run_rows`: canonical row-level classification and review truth
- `feedback_items`: reviewer feedback evidence
- `events`: upload/run lifecycle events

File-backed governed artifacts:
- `run_record.json`: local run envelope and operator-facing metadata
- `progress.json`: lifecycle progress emitted by active runtime processes
- `processing_stats.json`: throughput and review-detection counters
- `control.json`: local process-control state
- `policy.json`, `integrity_report.json`, `artifact_manifest.json`, `logs.txt`, `output.xlsx`

Read/write split:
- explicit write flows use `refresh_run_record(...)`, migration commands, review updates, and queue mutation helpers
- read-model surfaces use `resolve_run_record(...)` and canonical projections so GET endpoints do not rewrite run state as a side effect

## Data Flow

1. Validate SSOT
2. Validate workbook schema
3. Read input rows
4. Normalize text with drafter lane
5. Classify with classifier lane
6. Enforce taxonomy and fallback rules
7. Apply review policy
8. Write output workbook
9. Persist canonical row truth, queue ownership, integrity, policy, progress, and logs
10. Surface upload, run, review, and segment status through non-mutating backend read models consumed by the native macOS operator workspace

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
- `ollama://gemma2:9b`

Fallback / independent verifier:
- `ollama://qwen2.5:7b`

Configured legacy support runtimes (generative drafter unused):
- `ollama://granite4:350m`
- `ollama://gemma3:1b`
- `ollama://llama3.2:1b`
- `ollama://llama3.1:8b`
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

Independent automatic checks (SSOT 0.3): partial mode obtains two distinct classifier opinions and a third-model quality check. Automatic completion requires agreement, both classifier scores >=0.85, quality PASS >=0.85, valid structured responses, verified original source, and exact source evidence for positive claims. An automatic marker alone is insufficient. Context/format failures and disagreements remain human exceptions. Schema-constrained Ollama responses replace the unreliable primary MLX response path; Apertus remains available for comparison. The generative drafter configuration is legacy and unused; text preparation is deterministic. Model confidence is a self-reported score, not a measured accuracy probability.

Automatic AI reporting (SSOT 0.4): under the approved any-positive rule, any current canonical, primary, independent, or structured-retry analysis assigning a positive antisemitism category at confidence >=0.30 routes directly to AI reports and generates a branded PDF. No human review or cross-model agreement is required for that reporting route; warnings, disagreement, failed quality checks and a negative final classification remain visible in the report. Confidence is the score for a category, not calibrated probability of harm. Only the closed antisemitism taxonomy is scored; generic harmful-content categories are not inferred. Reports are explicitly AI-generated and unconfirmed. Saved human decisions, including false alarms and follow-up decisions, take precedence and suppress automatic reports. Later analyses may supersede a report; all exported snapshots remain in audit history. Human-confirmed reports retain their separate confirmation and permission gates. The policy is snapshotted per run; new native runs inherit it automatically, and current runs require explicit activation/backfill.
