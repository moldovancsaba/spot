# {spot}
**{spot} - Smart Platform for Observing Threats**

AI-assisted antisemitism classification system with SSOT-governed, auditable local processing.

Current workspace implementation: `0.5.2`
Pipeline version: `mvp-0.5.2`
Authoritative SSOT version: `0.4`
Latest shipped release notes in repo: [`docs/RELEASE_NOTES_0.3.1.md`](/Users/Shared/Projects/spot/docs/RELEASE_NOTES_0.3.1.md)

Distribution note:
- native macOS app source lives under [`app/macos/`](/Users/Shared/Projects/spot/app/macos)
- generated native app outputs live under `app/macos/.build/` and `app/macos/dist/` and are intentionally not source-controlled
- this repository currently has no declared open-source license file; treat it as a private maintainer workspace, not an open-source distribution

Documentation map:
- [README Brief](/Users/Shared/Projects/spot/README_BRIEF.md)
- [Architecture](/Users/Shared/Projects/spot/docs/ARCHITECTURE.md)
- [Production Plan](/Users/Shared/Projects/spot/docs/PRODUCTION_PLAN.md)
- [Foundation Hardening Plan](/Users/Shared/Projects/spot/docs/FOUNDATION_HARDENING_PLAN.md)
- [Relation Hardening Implementation Plan](/Users/Shared/Projects/spot/docs/RELATION_HARDENING_IMPLEMENTATION_PLAN.md)
- [DB-First Self-Learning Execution Plan](/Users/Shared/Projects/spot/docs/DB_FIRST_SELF_LEARNING_EXECUTION_PLAN.md)
- [Client Package](/Users/Shared/Projects/spot/docs/CLIENT_PACKAGE.md)
- [Local Appliance Runbook](/Users/Shared/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)
- [Local Queue Operations Plan](/Users/Shared/Projects/spot/docs/LOCAL_QUEUE_OPERATIONS_PLAN.md)
- [Benchmark Checklist](/Users/Shared/Projects/spot/docs/BENCHMARK_CHECKLIST.md)
- [UAT Checklist](/Users/Shared/Projects/spot/docs/UAT_CHECKLIST.md)
- [Acceptance Evidence Template](/Users/Shared/Projects/spot/docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md)
- [Release Notes 0.3.1](/Users/Shared/Projects/spot/docs/RELEASE_NOTES_0.3.1.md)
- [Release Notes 0.3.0 (Historical)](/Users/Shared/Projects/spot/docs/RELEASE_NOTES_0.3.0.md)

{spot} is a deterministic, auditable classification platform for large Excel batches of social media posts.
It enforces a strict closed-set taxonomy, produces explainable metadata, and writes governed outputs to Excel.

## Source Status

- this repository does not currently ship with a `LICENSE` file
- no public redistribution, modification, packaging, or support rights should be assumed from the repository contents alone
- the supported delivery posture is a source checkout maintained by the project owner or an explicitly authorized maintainer
- there is no supported `.pkg`, `.dmg`, Homebrew formula, or public installer channel in the current baseline

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

Current implementation stage:
- core deterministic runtime is implemented
- native macOS operator workflow is implemented
- native macOS supervisor shell is implemented
- queue-backed local operations dashboard is implemented
- canonical upload-row, run-row, run-attempt, and segment relations are implemented in the local operations DB
- read-model surfaces now resolve runtime state without mutating `run_record.json` or indexed run snapshots as a side effect
- productionization verification is in progress
- bounded `{trinity}` / `{train}` review-policy export is now implemented and locally validated
- live client acceptance on the current workspace baseline is still pending

## Canonical Taxonomy

- `Anti-Israel`
- `Anti-Judaism`
- `Classical Antisemitism`
- `Structural Antisemitism`
- `Conspiracy Theories`
- `Not Antisemitic`

## Production Runtime Truth

Primary classification and independent verification are SSOT-governed:
- `classifier`: `ollama://gemma2:9b`
- `classifier fallback / independent verifier`: `ollama://qwen2.5:7b`
- `drafter`: `ollama://granite4:350m`
- `drafter fallbacks`: `ollama://gemma3:1b` -> `ollama://llama3.2:1b`
- `judge`: `ollama://llama3.1:8b`
- `judge fallback`: `ollama://gemma2:2b`

Evaluation defaults remain explicit and deterministic:
- single-model benchmark: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- ensemble benchmark: `ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b`
- legacy Ollama tags such as `qwen2.5:7b` still resolve to Ollama for backward compatibility

## Control Principle

`LLM output -> normalization -> validation -> canonical category -> write`

## Pipeline

1. Load and validate SSOT from [`ssot/ssot.json`](/Users/Shared/Projects/spot/ssot/ssot.json)
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

New runs mark missing/invalid classifier categories as failed analysis with zero confidence and mandatory review, including `none` mode. Any single analysis that assigns a positive antisemitism category at confidence >= 0.30 forces human review (`ANY_POSITIVE_ANALYSIS`), even when the final label is `Not Antisemitic`; only a complete independent-consensus certificate clears a row. The closed-taxonomy fallback is a placeholder, not a successful negative result. Existing artifacts are unchanged.

Before using classification results for a consequential decision or external handoff, follow the interim row-by-row safeguard in [Fallback and Failure Handling](docs/LOCAL_APPLIANCE_RUNBOOK.md#fallback-and-failure-handling). A fallback `Not Antisemitic` label or `Review Required = NO` alone does not establish a valid negative result.

## Maintainer Install From Source

```bash
cd /Users/Shared/Projects/spot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Prepare the local appliance directories:

```bash
python3 -m src.cli bootstrap \
  --project-root . \
  --venv-path .venv \
  --requirements requirements.txt \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --logs-dir logs
```

Validate the machine before first launch:

```bash
.venv/bin/python -m src.cli preflight \
  --ssot ssot/ssot.json \
  --runs-dir runs \
  --port 8765
```

Native macOS build and install entrypoints:

```bash
cd /Users/Shared/Projects/spot/app/macos
swift build
bash build-bundle.sh
bash install-bundle.sh
open /Applications/spot.app
```

The only supported update path for `/Applications/spot.app` is to rebuild the bundle and rerun `app/macos/install-bundle.sh`.

## Maintenance Workflow

Routine maintainer workflow:

1. pull or review the intended repo changes into a clean source checkout
2. run `python3 -m src.cli bootstrap ... --skip-install` if only directory/permission setup needs refresh
3. rerun `.venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765`
4. rebuild and reinstall the native app with `app/macos/build-bundle.sh` and `app/macos/install-bundle.sh`
5. run backend and native verification before handing the machine back to operators

Supported maintainer removal path:

- remove `/Applications/spot.app`
- remove or archive the configured runtime directories under `~/Library/Application Support/spot/` if the machine is being decommissioned
- preserve `runs/` artifacts separately before cleanup when audit retention is required

Example deterministic classification command:

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

Example single-vs-ensemble evaluation command:

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

Example bounded Trinity/Train bundle export from reviewed Spot rows:

```bash
.venv/bin/python -m src.cli export-trinity-spot-bundles \
  --run-id run-001 \
  --runs-dir runs \
  --company-id company-1 \
  --output-dir runs/run-001/trinity_bundles
```

## Backend Endpoints

Intake and queue endpoints:

- `POST /uploads/intake?filename=<workbook.xlsx>` with raw `.xlsx` request body and legacy `X-Filename` header fallback
- `GET /uploads`
- `GET /uploads/{upload_id}`
- `GET /operations/overview`
- `POST /classify/start/{run_id}` with `{"upload_id":"..."}` to start from an accepted intake record

Run, review, and artifact endpoints:

- `GET /runs` (resolved run list)
- `GET /runs/{run_id}` (single resolved run record)
- `GET /runs/recovery-candidates/list`
- `GET /runs/{run_id}/state`
- `GET /runs/{run_id}/detail`
- `GET /runs/{run_id}/review-rows`
- `GET /runs/{run_id}/review-rows/{row_index}`
- `GET /runs/{run_id}/artifacts`
- `GET /runs/{run_id}/artifacts/download/{artifact_name}` (permission: `download_artifact`)
- `GET /runs/{run_id}/events` (append-only run audit trail, newest first; permission: `view`)
- `POST /learning/cycle/{run_id}` (run one governed learning cycle: feedback, drift, training export, registry; permission: `signoff`)
- `GET /learning/cycles/{run_id}` (learning cycle registry; permission: `view`)
- `POST /runs/{run_id}/review-rows/{row_index}`
- `GET /runs/{run_id}/actions`
- `POST /runs/{run_id}/signoff`
- `POST /runs/{run_id}/cancel`
- `POST /runs/{run_id}/retry`
- `POST /runs/{run_id}/recover`
- `POST /runs/{run_id}/heal`
- `POST /runs/{run_id}/migrate-row-state` to backfill canonical `run_rows` from checkpoint and/or output artifacts for legacy or interrupted runs
- `DELETE /runs/{run_id}` to purge an inactive run and optionally purge its managed upload when no other run still references it

Native runtime and active-run endpoints:

- `POST /native/runtime/suspend`
- `POST /classify/pause/{run_id}`
- `POST /classify/resume/{run_id}`
- `POST /classify/stop/{run_id}`
- `GET /classify/status/{run_id}`

## Continuous learning

{spot} runs as a learning service, not a one-shot tool. On backend startup a scheduler thread runs a learning
cycle for the most recent runs that carry canonical rows, every `SPOT_LEARNING_CYCLE_INTERVAL_SEC` seconds
(default 21600 = 6 h; set `0` to disable). A cycle:

1. summarises human decisions and how many rows are now eligible training evidence,
2. scores the run's canonical labels against the frozen reference so drift is measured continuously,
3. exports eligible reviewed rows through the bounded `{trinity}` / `{train}` seam,
4. appends an immutable record to `runs/<run_id>/learning/registry.jsonl`.

It never mutates classification state, never retrains, and never changes the governed contract; adopting a
model or threshold stays an explicit, recorded decision. Cycles can also be triggered on demand with
`POST /learning/cycle/{run_id}`.

## Repo Layout

- [`app/macos/`](/Users/Shared/Projects/spot/app/macos): native macOS shell, bundle scripts, SwiftUI sources
- [`backend/`](/Users/Shared/Projects/spot/backend): FastAPI appliance backend and queue/runtime services
- [`src/`](/Users/Shared/Projects/spot/src): classification pipeline, CLI, evaluation, benchmarking
- [`ssot/`](/Users/Shared/Projects/spot/ssot): governed taxonomy and runtime contract
- [`docs/`](/Users/Shared/Projects/spot/docs): active operational, architecture, and handover documentation
- [`script/`](/Users/Shared/Projects/spot/script): dev wrappers such as native build-and-run

Current native operator surface:

- queue one or more `.xlsx` workbooks into local intake
- segment accepted workbooks into queue-backed local operations records
- start a run from an accepted workbook
- monitor row progress, segment progress, elapsed time, and throughput from the main dashboard
- pause, resume, or stop the active run from the dashboard
- review flagged rows and retrieve audit artifacts locally

Auth and permission endpoints:

- `GET /auth/config`
- `GET /auth/session`
- `POST /auth/login`
- `POST /auth/logout`

Local auth defaults:

- auth is enabled by default with `SPOT_AUTH_ENABLED=1`
- the native app generates a per-install local access code when empty or set to the historical default
- standalone backend compatibility still defaults to `spot-local`; set `SPOT_LOCAL_ACCESS_CODE` before using that path
- rotate the shared local code with `SPOT_LOCAL_ACCESS_CODE`
- role gates currently distinguish `operator`, `reviewer`, `acceptance_lead`, and `admin`
- upload, run start, run recovery actions, review updates, sign-off, and artifact downloads are permission-gated

Current verification boundary:
- backend regressions validate the runtime/API contract behind the native shell
- it does not replace a live client acceptance run on the target machine
- the historical `0.3.2` acceptance record is archived in [`docs/ACCEPTANCE_EVIDENCE_2026-03-18.md`](/Users/Shared/Projects/spot/docs/ACCEPTANCE_EVIDENCE_2026-03-18.md)

## Monitoring URLs

- Backend health: [http://127.0.0.1:8765/api/health](http://127.0.0.1:8765/api/health)

## Runtime Configuration

{spot} now resolves runtime defaults from [`ssot/ssot.json`](/Users/Shared/Projects/spot/ssot/ssot.json). Environment variables still override them when explicitly set.

Supported overrides:

```bash
export SPOT_ROUTE_CLASSIFIER_BACKEND=ollama
export SPOT_ROUTE_CLASSIFIER_MODEL=qwen2.5:7b
export SPOT_ROUTE_CLASSIFIER_FALLBACK_BACKEND=ollama
export SPOT_ROUTE_CLASSIFIER_FALLBACK_MODEL=gemma2:9b

export SPOT_ROUTE_DRAFTER_BACKEND=ollama
export SPOT_ROUTE_DRAFTER_MODEL=granite4:350m
export SPOT_ROUTE_DRAFTER_FALLBACK_BACKEND=ollama
export SPOT_ROUTE_DRAFTER_FALLBACK_MODEL=gemma3:1b,llama3.2:1b

export SPOT_ROUTE_JUDGE_BACKEND=ollama
export SPOT_ROUTE_JUDGE_MODEL=llama3.1:8b
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

- Project brief: [`README_BRIEF.md`](/Users/Shared/Projects/spot/README_BRIEF.md)
- Client package: [`docs/CLIENT_PACKAGE.md`](/Users/Shared/Projects/spot/docs/CLIENT_PACKAGE.md)
- Foundation hardening plan: [`docs/FOUNDATION_HARDENING_PLAN.md`](/Users/Shared/Projects/spot/docs/FOUNDATION_HARDENING_PLAN.md)
- Local appliance runbook: [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/Shared/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)
- SSOT contract: [`ssot/SSOT.md`](/Users/Shared/Projects/spot/ssot/SSOT.md)
- SSOT machine config: [`ssot/ssot.json`](/Users/Shared/Projects/spot/ssot/ssot.json)
- Architecture: [`docs/ARCHITECTURE.md`](/Users/Shared/Projects/spot/docs/ARCHITECTURE.md)
- Ingestion contract: [`docs/INGESTION.md`](/Users/Shared/Projects/spot/docs/INGESTION.md)
- Operational notes: [`docs/BRAIN_DUMP.md`](/Users/Shared/Projects/spot/docs/BRAIN_DUMP.md)
- Monitoring/UI: [`MONITORING_UI.md`](/Users/Shared/Projects/spot/MONITORING_UI.md)
- Foundation baseline: [`FOUNDATION.md`](/Users/Shared/Projects/spot/FOUNDATION.md)
- Design baseline: [`DESIGN.md`](/Users/Shared/Projects/spot/DESIGN.md)
- Handover log: [`docs/HANDOVER.md`](/Users/Shared/Projects/spot/docs/HANDOVER.md)
- Changelog: [`CHANGELOG.md`](/Users/Shared/Projects/spot/CHANGELOG.md)

## Human case decisions and threat reports

The native **Reports** tab shows per-run case totals and attached reference-label evaluations. **Review** lists all classified posts in pages of 100, including posts the model did not flag. Reviewers can record **Confirm threat**, **False alarm**, or **Leave unresolved**. A confirmed threat requires a selected closed-taxonomy category. The human decision is saved separately from the original model proposal, with actor, timestamp, evidence fingerprint and immutable decision history.

Only a current, saved human-confirmed threat can produce an official `{spot}` threat-report PDF. Reviewers, acceptance leads and administrators can export; operators cannot. PDFs contain the original post, human finding and note, original model proposal/flags, report and decision IDs, timestamps and evidence hashes. They are local report snapshots, not digital signatures. The PDF and original Unicode JSON snapshot are retained under the run's `threat_reports/` directory with an export ledger. Later evidence or review changes supersede previous reports and prevent them from being downloaded as current reports.

New local endpoints: `GET /runs/{run_id}/reports`, `GET /runs/{run_id}/cases`, `POST /runs/{run_id}/cases/{row_index}/decision`, `POST /runs/{run_id}/cases/{row_index}/report.pdf`, `GET /runs/{run_id}/threat-reports/{report_id}.pdf`, `POST /runs/{run_id}/cases/{row_index}/automatic-report.pdf`, and `GET /runs/{run_id}/automatic-reports/{report_id}.pdf`. Case writes require the case token returned with the current evidence; stale writes return 409. Every branded report endpoint (human-confirmed and automatic AI) requires the `export_threat_report` permission. PDF generation requires the pinned `reportlab` dependency.

Independent automatic checks (SSOT 0.3): partial mode obtains two distinct classifier opinions and a third-model quality check. Automatic completion requires agreement, both classifier scores >=0.85, quality PASS >=0.85, valid structured responses, verified original source, and exact source evidence for positive claims. An automatic marker alone is insufficient. Context/format failures and disagreements remain human exceptions. Schema-constrained Ollama responses replace the unreliable primary MLX response path; Apertus remains available for comparison. The generative drafter configuration is legacy and unused; text preparation is deterministic. Model confidence is a self-reported score, not a measured accuracy probability.

Automatic AI reporting (SSOT 0.4): under the approved any-positive rule, any current canonical, primary, independent, or structured-retry analysis assigning a positive antisemitism category at confidence >=0.30 routes directly to AI reports and generates a branded PDF. No human review or cross-model agreement is required for that reporting route; warnings, disagreement, failed quality checks and a negative final classification remain visible in the report. Confidence is the score for a category, not calibrated probability of harm. Only the closed antisemitism taxonomy is scored; generic harmful-content categories are not inferred. Reports are explicitly AI-generated and unconfirmed. Saved human decisions, including false alarms and follow-up decisions, take precedence and suppress automatic reports. Later analyses may supersede a report; all exported snapshots remain in audit history. Human-confirmed reports retain their separate confirmation and permission gates. The policy is snapshotted per run; new native runs inherit it automatically, and current runs require explicit activation/backfill. **This route is disabled in the governed default (`automatic_reporting.enabled: false`); a new run generates no automatic AI reports and writes no reporting policy snapshot. Enabling it is an explicit per-run decision gated on an adjudicated gold set.**
