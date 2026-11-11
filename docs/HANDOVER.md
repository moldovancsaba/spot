# {spot} Handover Log

Historical note:
- this file is a chronological delivery log, not the active operating contract
- older entries intentionally preserve the browser-phase and `app/spot-app` wording that was true when those entries were written
- current operator and startup guidance lives in [`README.md`](/Users/Shared/Projects/spot/README.md), [`READMEDEV.md`](/Users/Shared/Projects/spot/READMEDEV.md), and [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/Shared/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)

## 2026-11-11 Europe/Budapest - Delivery (operator safeguards, measured route swap, model decision)

- Committed and merged the body of work that had been sitting uncommitted in the working tree: SSOT 0.4, failure policy and review routing, human case decisions and threat reports, automatic any-positive reporting, the native reports surface, the model-free contract regressions, CI, and documentation reconciliation. PR #84, merge commit `5da4f7c`, 23 reviewed commits.
- Swapped the governed classifier route to `ollama://gemma2:9b` with `ollama://qwen2.5:7b` as independent verifier, on 300-row same-sample evidence: binary recall 0.788 -> 0.936, binary F1 0.855 -> 0.918, six-way macro-F1 0.270 -> 0.354, +44% per-row latency.
- Re-ran the 30-row German acceptance under the new route: reference agreement 26.67% -> 40.00%, macro-F1 0.1755 -> 0.3201, zero analysis failures. Recorded in `docs/ACCEPTANCE_EVIDENCE_2026-11-11.md`. Formal acceptance remains held.
- Closed model selection in `docs/MODEL_SELECTION_DECISION_2026-11-11.md`: six-way autonomy is unsupported by every tested candidate (best 0.354; `Structural Antisemitism` 0.000 for all), the candidate ranking flips with the reference, and the binding constraint is label consistency rather than model scale. Binary triage is the reliable capability.
- Rejected the remaining size options on evidence: `qwen3.8:27b` produced 86% unparseable output at 8.5x latency; the Apertus family has only 8B and 70B, the 70B needs ~40 GB at INT4 against 32 GB of memory, and the 8B reproduces the documented malformed/ungrounded failure at 89.7%.
- **Disabled automatic AI reporting in the governed default.** The prior freeze covered one run's policy file only, so the next run would have resumed publishing branded reports from a 0.30-0.35 macro-F1 classifier. `ssot/ssot.json` now ships `enabled: false`, with activation gated on a decision record and an adjudicated gold set.
- Fixed two asymmetric-privilege defects: automatic-report PDF endpoints required only `view` (now `export_threat_report`, matching human-confirmed exports), and `DELETE /runs/{id}` purged the managed source workbook by default (now opt-in).
- Gave the append-only `events` table a reader (`GET /runs/{id}/events`), retired the dead `feedback_items` table behind a data-preserving guard, and unified the processed-row precedence ladder so the queue and run-record projections cannot disagree.
- Archived and purged the 62,024-row run so it could not be auto-recovered under a different route; its evidence (419 automatic AI reports plus policy, recheck, review history and logs) is preserved under `runs/_archive/2026-11-11-german-full-system-autoreports/`, and the managed source upload with all 62,024 canonical rows is retained.
- Verification: 116 model-free contract tests pass, preflight inference smoke passes for both classifier routes, Swift build and bundle install pass, and `/Applications/spot.app` is byte-identical to `main` for every runtime file. Documentation reconciled: all 41 registered routes documented, 116 machine-specific paths normalized, CHANGELOG brought to 0.5.1/0.5.2/current.
- Remaining gates: a human-confirmed gold set (the measured label inconsistency is the blocker, not the model), then a bounded pilot under the new route; full six-way autonomy and re-enabling automatic reporting both depend on that. Full-volume throughput and operator usability sign-off remain unestablished.

## 2026-11-08 Europe/Budapest - Codex (cockpit reports and human threat decisions)

- Added native Reports with per-run evaluation metrics, case totals, paginated cases and generated threat report history. Attached the existing German baseline and comparison evaluation summaries to their actual run records without altering original workbooks.
- Added explicit human confirmed-threat / false-alarm / unresolved decisions, closed-taxonomy human categories, actor/time, evidence-bound write tokens, decision history and evidence-change invalidation. Original model assignments remain intact.
- Added gated official `{spot}` PDF generation and current-report downloads with original post, saved human finding, model evidence, identities/times and hashes. Exact Unicode snapshots and export ledger records are retained locally. Stale decisions, false alarms, unresolved cases, operators and tampered reports cannot authorize current PDF downloads.
- Added the pinned reportlab runtime dependency and PDF regressions; visually inspected a multi-page synthetic report. Actual client rows were not confirmed or dismissed by the agent.
- Bounded learning exports now use an explicit human-corrected final label when present, while retaining the original model interpretation and existing conservative failure/fallback exclusions.

## 2026-11-08 Europe/Budapest - Codex (visible German acceptance evaluation)

- The project owner approved the German sample workbook and identified themselves as the designated acceptance reviewer.
- Added a reproducible balanced 30-row sample and scoring harness that keeps reference labels out of inference and never scores failed-analysis negative placeholders as successful predictions.
- Exercised watched intake in the installed cockpit and uncovered a missing `DEFAULT_PROGRESS_EVERY` import on the real production start path; fixed it and added a regression that executes the actual start builder.
- Exercised pause/resume/stop on the initial control run and started the full-review evaluation visibly in the cockpit.
- Replaced the obsolete native acceptance smoke's artificial run fixtures with attachment to a real run, explicit auth/permission checks, invalid-schema intake, and artifact download/hash checks.
- Baseline comparison exposed substantial drafter edits and malformed string metadata. Added source-preserving drafter validation and metadata shape handling, with regressions. Full suite: 70 tests passed before the comparison rerun.
- Final numerical evidence is in `docs/ACCEPTANCE_EVIDENCE_2026-11-08.md`: baseline 5/30 vs source-preserving 8/30 reference-label matches; operational smoke/hash checks and the synthetic none-mode failure review/sign-off gate passed. Engineering recommendation: hold acceptance pending reviewer adjudication.
- Corrected terminal-progress precedence, required complete canonical row coverage before sign-off, and preserved explicitly selected historical runs across native refresh. The final 71-test suite and native build passed.

## 2026-11-08 Europe/Budapest - Codex (local audit hardening)

- Added mandatory failure review, zero-confidence failure placeholders, and shared safety enforcement at canonical persistence/workbook boundaries.
- Added regressions for absent/invalid categories, total request failure, unstructured output, export eligibility, and inference smoke reporting.
- Corrected MLX response parsing and raised the bounded inference deadline to 120 seconds; added explicit primary/fallback smoke verification to preflight.
- Kept startup readiness separate from inference verification in the health response.
- Enabled native local authentication, generated non-default installation codes, and corrected session reuse when the actor changes.
- Blocked escalated/incomplete reviews from sign-off and excluded failed/escalated rows from learning export.
- Aligned active maintainer paths and shared model defaults; added one local regression entrypoint and a model-free GitHub workflow.
- Target-machine inference, native authentication, listener and deployment verification are recorded in `docs/AUDIT_EVIDENCE_2026-11-08.md`; fresh client acceptance is still required.

## 2026-05-20 Europe/Budapest - Codex ({spot} targeted code-comment audit cleanup)

- Objective: verify the active runtime inline comments against the current native-only and canonical-state contracts, then correct stale wording instead of assuming the documentation pass was sufficient.
- Changes:
  - corrected [`backend/services/run_state_service.py`](/Users/Shared/Projects/spot/backend/services/run_state_service.py) so the artifact label for `review_state.json` no longer describes it as browser-specific state
  - corrected the generated native config comments in [`app/macos/Sources/SpotCoreService.swift`](/Users/Shared/Projects/spot/app/macos/Sources/SpotCoreService.swift) so `SPOT_LOCAL_ACCESS_CODE` guidance is now conditional on auth actually being enabled for the runtime
  - refreshed [`docs/CODE_COMMENT_AUDIT.md`](/Users/Shared/Projects/spot/docs/CODE_COMMENT_AUDIT.md) to record the follow-up audit result
- Validation:
  - rescanned active code comments for the stale `browser` / `review_state.json` / native-auth wording that triggered the follow-up
  - `python3 -m py_compile backend/services/run_state_service.py src/trinity_spot_bundle.py` => passed

## 2026-05-20 Europe/Budapest - Codex ({spot} active documentation hardening pass)

- Objective: remove active documentation drift across the current `0.5.2` native-only baseline, including stale queue/native wording, missing runtime surfaces, and outdated planning references.
- Changes:
  - updated [`README.md`](/Users/Shared/Projects/spot/README.md) so the documentation map, active implementation summary, and backend endpoint inventory now reflect the current queue, recovery, intake, and native-runtime surface
  - expanded [`docs/ARCHITECTURE.md`](/Users/Shared/Projects/spot/docs/ARCHITECTURE.md) with the canonical persistence model, current indexed entities, and the current read/write split in runtime state resolution
  - rewrote [`docs/LOCAL_QUEUE_OPERATIONS_PLAN.md`](/Users/Shared/Projects/spot/docs/LOCAL_QUEUE_OPERATIONS_PLAN.md) around the current queue-backed appliance baseline instead of the earlier browser-dashboard transition framing
  - refreshed [`docs/FOUNDATION_HARDENING_PLAN.md`](/Users/Shared/Projects/spot/docs/FOUNDATION_HARDENING_PLAN.md) and [`docs/PROJECT_MANAGEMENT.md`](/Users/Shared/Projects/spot/docs/PROJECT_MANAGEMENT.md) so they point at the current remaining execution lane rather than pre-hardening next steps
  - marked [`docs/CODE_COMMENT_AUDIT.md`](/Users/Shared/Projects/spot/docs/CODE_COMMENT_AUDIT.md) and [`docs/NATIVE_APP_SCAFFOLD_SPEC.md`](/Users/Shared/Projects/spot/docs/NATIVE_APP_SCAFFOLD_SPEC.md) more clearly as point-in-time historical documents while aligning their top-level framing with the current `0.5.2` baseline
  - updated [`docs/NATIVE_APP_BUILD_HANDOFF.md`](/Users/Shared/Projects/spot/docs/NATIVE_APP_BUILD_HANDOFF.md) to reflect the hardened read-model behavior and explicit `review_state.json` persistence contract
- Validation:
  - rescanned active docs for stale `0.5.1`, browser-dashboard, and missing endpoint drift and confirmed the remaining `0.5.1` markers now exist only in explicitly historical notes
  - rescanned active docs for current queue/recovery/runtime surfaces including `run_rows`, `run_attempts`, `upload_rows`, `heal`, `delete`, recovery candidates, and native runtime suspend

## 2026-05-20 Europe/Budapest - Codex ({spot} issue #19 side-effect-free read-model delivery)

- Objective: move runtime read paths onto an observational resolver so GETs stop mutating canonical run state.
- Changes:
  - split [`backend/services/run_state_service.py`](/Users/Shared/Projects/spot/backend/services/run_state_service.py) into a non-mutating `resolve_run_record(...)` path and a mutating `refresh_run_record(...)` path that is now reserved for explicit write-oriented flows
  - switched read builders and recovery-candidate listing to consume the non-mutating resolver, including run detail, artifact center, review queue, row inspector, run listing, and recovery-candidate projection
  - switched GET read endpoints in [`backend/main.py`](/Users/Shared/Projects/spot/backend/main.py) onto the non-mutating resolver, including `/runs/{run_id}`, `/runs/{run_id}/state`, and `/classify/status/{run_id}`
  - updated [`src/trinity_spot_bundle.py`](/Users/Shared/Projects/spot/src/trinity_spot_bundle.py) to consume resolved run state without rewriting the run record as a side effect
  - extended [`backend/backend_contract_regression.py`](/Users/Shared/Projects/spot/backend/backend_contract_regression.py) to prove stale runs can be projected for reads without rewriting `run_record.json`, creating `review_state.json`, or bumping the indexed `runs` snapshot
- Validation:
  - `python3 -m py_compile backend/services/run_state_service.py backend/main.py backend/backend_contract_regression.py backend/ops_queue_regression.py src/trinity_spot_bundle.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed

## 2026-05-19 Europe/Budapest - Codex ({spot} issues #62 and #63 relation hardening delivery)

- Objective: finish the remaining relation-hardening slices by making segment claims atomic and by refusing to silently downgrade broken managed upload relations.
- Changes:
  - hardened [`backend/services/ops_db_service.py`](/Users/Shared/Projects/spot/backend/services/ops_db_service.py) so `claim_next_segment(...)` now claims work under a write lock with a conditional state guard and retry loop instead of a bare select-then-update sequence
  - added strict managed-upload resolution to `register_run(...)` and `update_run_snapshot(...)` so upload-backed runtime records fail explicitly when the referenced `uploads` row is missing instead of being downgraded to `None`
  - kept passive historical reads compatible by letting [`backend/services/run_state_service.py`](/Users/Shared/Projects/spot/backend/services/run_state_service.py) refresh legacy run records without forcing a managed-upload rewrite on every list/detail read
  - gated `/runs/{run_id}/retry`, `/recover`, and `/heal` in [`backend/main.py`](/Users/Shared/Projects/spot/backend/main.py) through the recovery-candidate audit so broken managed runs now return an explicit `409` with the integrity reason
  - extended [`backend/ops_queue_regression.py`](/Users/Shared/Projects/spot/backend/ops_queue_regression.py) with a competing-claim regression and updated [`backend/backend_contract_regression.py`](/Users/Shared/Projects/spot/backend/backend_contract_regression.py) to cover strict managed-upload enforcement plus the new API refusal behavior
- Validation:
  - `python3 -m py_compile backend/services/ops_db_service.py backend/services/run_state_service.py backend/main.py backend/ops_queue_regression.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-19 Europe/Budapest - Codex ({spot} issue #61 immutable run-row lineage delivery)

- Objective: deliver the first relation-hardening slice by making upload-backed canonical run rows carry explicit source-row lineage instead of relying on best-effort reconstruction.
- Changes:
  - rebuilt the `run_rows` schema in [`backend/services/ops_db_service.py`](/Users/Shared/Projects/spot/backend/services/ops_db_service.py) so upload-backed run rows now carry `source_row_index` and `source_row_hash` and keep a composite foreign-key relation on `(upload_id, sequence_index)` back to `upload_rows`
  - added automatic table-rebuild migration logic so older local DBs are promoted onto the stronger lineage-aware schema when missing the new relation shape
  - tightened `upsert_run_rows(...)` so upload-backed writes now fail explicitly when canonical upload lineage cannot be resolved for the target row
  - extended backend and queue regressions so upload-backed canonical rows prove persisted lineage and so missing lineage now fails as an explicit integrity error
- Validation:
  - `python3 -m py_compile backend/services/ops_db_service.py backend/backend_contract_regression.py backend/services/run_state_service.py src/pipeline.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed

## 2026-05-19 Europe/Budapest - Codex ({spot} relation hardening implementation plan and GitHub issue sync)

- Objective: turn the May 2026 relation audit into a concrete implementation plan, deliverable issues, and dependency-aware GitHub board order.
- Changes:
  - added [`docs/RELATION_HARDENING_IMPLEMENTATION_PLAN.md`](/Users/Shared/Projects/spot/docs/RELATION_HARDENING_IMPLEMENTATION_PLAN.md) with the scoped hardening phases, deliverable issue map, recommended delivery order, and explicit gate in front of the DB-first ingest lane
  - added the relation-hardening plan to the [`README.md`](/Users/Shared/Projects/spot/README.md) documentation map
  - created GitHub issues `#61` through `#63` for immutable row lineage, atomic segment claiming, and fail-fast managed relation handling
  - updated GitHub issues `#3`, `#17`, `#18`, `#22`, `#23`, `#24`, `#50`, and `#54` so their dependency sections and execution notes now reflect the audited delivery order
  - synced the new issues to GitHub Project `{spot} - From IDEA to LIVE`
- Validation:
  - `gh issue create` => created `#61`, `#62`, and `#63`
  - `gh issue edit` => updated `#3`, `#17`, `#18`, `#22`, `#23`, `#24`, `#50`, and `#54`
  - `gh project item-add 5 --owner moldovancsaba --url ...` => added `#61`, `#62`, and `#63` to the project board
  - `gh project item-list 5 --owner moldovancsaba --limit 250 --format json` => confirmed project sync

## 2026-05-19 Europe/Budapest - Codex ({spot} native recovery surface and shared model-root health-check documentation)

- Objective: document the now-implemented native recovery candidate surface and record the current health-check status for the shared model-root and unfinished-run relations.
- Changes:
  - expanded [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/Shared/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md) so the operator contract now includes unfinished-run recovery candidates, deletion semantics for inactive runs, and the native settings exposure of the shared model-root paths
  - recorded the recovery-action semantics explicitly: `resume` for attached paused workers, `recover` for upload-backed queued segment recovery, `retry` for non-upload restarts, and `broken` for runs missing required restart state
  - confirmed the shared model-root contract is now wired end to end across bootstrap, preflight, bundled launch, and the native SwiftUI settings surface
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/backend_contract_regression.py backend/ops_queue_regression.py backend/segment_worker.py src/benchmark.py src/targeted_adjudication_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed
  - `.venv/bin/python src/targeted_adjudication_regression.py` => passed
  - `python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --ssot ssot/ssot.json --runs-dir runs --logs-dir logs --skip-install` => passed
  - `.venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` => passed with `errors=0`, `warnings=0`
  - `cd app/macos && swift package dump-package >/dev/null && swift build && bash -n ./build-icon.sh && bash -n ./build-bundle.sh && bash -n ./install-bundle.sh && plutil -lint ./Info.plist` => passed

## 2026-05-18 Europe/Budapest - Codex ({spot} shared model root standardization and machine-install documentation)

- Objective: standardize `{spot}` model storage under `/Users/Shared/Models/spot`, migrate the current machine onto that layout, and document the install pattern for future Apple Silicon machines.
- Changes:
  - added explicit shared model-root defaults and native launch wiring so `{spot}` now targets `/Users/Shared/Models/spot/huggingface` and `/Users/Shared/Models/spot/ollama`
  - migrated the active MLX/Hugging Face cache and Ollama store into the new `{spot}` shared roots
  - pulled the missing Ollama fallback tag `llama3.2:1b` into the shared `{spot}` store
  - replaced the legacy per-user Hugging Face cache path `~/.cache/huggingface` with a symlink to `/Users/Shared/Models/spot/huggingface`
  - expanded [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/Shared/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md) and [`READMEDEV.md`](/Users/Shared/Projects/spot/READMEDEV.md) so future machine installs have a concrete shared-model provisioning checklist
- Validation:
  - `python3 -m py_compile src/defaults.py src/bootstrap.py src/preflight.py src/classifier.py src/cli.py backend/main.py` => passed
  - `bash -n app/macos/build-bundle.sh` => passed
  - `cd app/macos && swift build` => passed
  - `.venv/bin/python -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --ssot ssot/ssot.json --runs-dir runs --logs-dir logs --skip-install` => passed
  - `.venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` => passed with `errors=0`, `warnings=0`

## 2026-05-13 Europe/Budapest - Codex ({spot} DB-first ingest and bounded self-learning planning lane)

- Objective: turn the repo discussion about canonical-schema-first ingest, DB-backed runtime truth, and bounded model improvement into an executable `{spot}` implementation lane.
- Changes:
  - added [`docs/DB_FIRST_SELF_LEARNING_EXECUTION_PLAN.md`](/Users/Shared/Projects/spot/docs/DB_FIRST_SELF_LEARNING_EXECUTION_PLAN.md) with the target architecture, guardrails, delivery phases, and recommended local training stack
  - created milestone `{spot} v0.6.0 DB-First Ingest & Learning Loop`
  - created GitHub epic `#50` plus concrete delivery issues `#51` through `#60` covering canonical intake schema, importer/exporter adapters, DB-first classification, governed feedback capture, offline evaluation, Apple Silicon fine-tuning, candidate registry, and active learning
  - added the new issues to GitHub Project `{spot} - From IDEA to LIVE` and placed them in dependency-aware status lanes behind the active canonical-state hardening work
- Validation:
  - `gh issue list --limit 100` => confirmed new issues `#50` through `#60`
  - `gh project item-list 5 --owner moldovancsaba --limit 100 --format json` => confirmed new board items and statuses

## 2026-05-13 Europe/Budapest - Codex ({spot} Apple-Silicon-only learning lane correction)

- Objective: remove accidental secondary-framework framing from the new planning lane and make the training/runtime roadmap explicitly Apple-Silicon-only.
- Changes:
  - updated [`docs/DB_FIRST_SELF_LEARNING_EXECUTION_PLAN.md`](/Users/Shared/Projects/spot/docs/DB_FIRST_SELF_LEARNING_EXECUTION_PLAN.md) so the active `{spot}` learning plan uses `mlx-lm` only and excludes `Axolotl`, `LLaMA-Factory`, and `Unsloth` from the delivery lane
  - updated GitHub issues `#50` and `#58` so the public implementation plan now states that the active training path is Apple Silicon only
- Validation:
  - `gh issue view 50`
  - `gh issue view 58`

## 2026-05-13 Europe/Budapest - Codex ({spot} canonical intake schema first implementation slice)

- Objective: start issue `#51` by making the intake contract explicit in code and by persisting source-row provenance in the DB-backed upload layer.
- Changes:
  - added canonical intake schema definitions to [`src/models.py`](/Users/Shared/Projects/spot/src/models.py) with schema version `spot.input-row.v1alpha1`
  - changed [`src/excel_io.py`](/Users/Shared/Projects/spot/src/excel_io.py) so workbook intake rows are canonicalized into a structured row shape before manifest/storage projection
  - extended `upload_rows` in [`backend/services/ops_db_service.py`](/Users/Shared/Projects/spot/backend/services/ops_db_service.py) with schema version, normalization status, and source provenance fields
  - changed [`backend/services/excel_service.py`](/Users/Shared/Projects/spot/backend/services/excel_service.py) to persist the canonical schema version in upload validation metadata and to write canonicalized intake rows into the DB
  - rewrote [`docs/INGESTION.md`](/Users/Shared/Projects/spot/docs/INGESTION.md) around the canonical-row contract instead of only the workbook header order
- Validation:
  - `python3 -m py_compile src/models.py src/excel_io.py backend/services/excel_service.py backend/services/ops_db_service.py` => passed

## 2026-05-13 Europe/Budapest - Codex ({spot} canonical intake validation summary and importer scaffold)

- Objective: continue issues `#51` and `#52` by formalizing canonical intake validation summaries and introducing the first source-adapter abstraction for the existing workbook path.
- Changes:
  - added `summarize_canonical_input_rows(...)` in [`src/excel_io.py`](/Users/Shared/Projects/spot/src/excel_io.py) so accepted-row, quarantine, rejection, schema-version, and source-type semantics are explicit in code
  - changed [`backend/services/excel_service.py`](/Users/Shared/Projects/spot/backend/services/excel_service.py) so upload validation metadata now carries canonical validation summary fields instead of only workbook-specific counters
  - added [`src/intake_adapters.py`](/Users/Shared/Projects/spot/src/intake_adapters.py) with the first importer abstraction and `.xlsx` implementation, so the current workbook path now flows through a source-adapter seam
  - extended [`backend/backend_contract_regression.py`](/Users/Shared/Projects/spot/backend/backend_contract_regression.py) to assert schema version, normalization status, provenance, and canonical validation summary fields for both fresh intake and legacy materialization
- Validation:
  - `python3 -m py_compile src/intake_adapters.py src/models.py src/excel_io.py backend/services/excel_service.py backend/services/ops_db_service.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python -m unittest backend.backend_contract_regression.BackendContractRegressionTests.test_intake_writes_row_manifest_for_accepted_upload backend.backend_contract_regression.BackendContractRegressionTests.test_ensure_upload_rows_materialized_backfills_legacy_upload` => passed

## 2026-05-11 Europe/Budapest - Codex ({spot} 0.5.2 bounded export docs promotion)

- Objective: promote the active workspace baseline after the bounded `{trinity}` / `{train}` Spot export seam landed, and align maintainer-facing install/update docs to that new current state.
- Changes:
  - promoted the active workspace baseline from `0.5.1` to `0.5.2` and the pipeline marker from `mvp-0.5.1` to `mvp-0.5.2`
  - updated backend runtime version reporting and native bundle metadata to the `0.5.2` baseline
  - updated `README.md`, `READMEDEV.md`, `README_BRIEF.md`, `docs/CLIENT_PACKAGE.md`, and `docs/LOCAL_APPLIANCE_RUNBOOK.md` so the supported install/update path and the bounded `{trinity}` / `{train}` export command are documented together
  - kept the acceptance wording explicit: the bounded export seam is working and locally validated, but fresh client-machine acceptance evidence is still a separate gate
- Files touched:
  - `VERSION`
  - `src/__init__.py`
  - `backend/main.py`
  - `app/macos/Info.plist`
  - `README.md`
  - `READMEDEV.md`
  - `README_BRIEF.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/ARCHITECTURE.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/backend_contract_regression.py backend/ops_queue_regression.py backend/segment_worker.py src/benchmark.py src/targeted_adjudication_regression.py src/trinity_spot_bundle.py src/trinity_spot_bundle_regression.py` => passed
  - `PYTHONPATH=/Users/Shared/Projects/spot .venv/bin/python backend/backend_contract_regression.py` => passed
  - `PYTHONPATH=/Users/Shared/Projects/spot .venv/bin/python backend/ops_queue_regression.py` => passed
  - `cd app/macos && swift package dump-package >/dev/null && swift build && bash -n ./build-icon.sh && bash -n ./build-bundle.sh && bash -n ./install-bundle.sh && plutil -lint ./Info.plist` => passed

## 2026-05-11 Europe/Budapest - Codex ({spot} bounded Trinity/Train bundle export)

- Objective: add the first explicit `{spot}` export seam that lets reviewed run rows feed the bounded `{trinity}` / `{train}` Spot review-policy loop without inventing broader live-runtime integration.
- Changes:
  - added `src/trinity_spot_bundle.py` with a bounded `trinity.spot.v1alpha1` export path that converts reviewed canonical Spot rows into `spot-review-policy-learning` bundle files
  - added `python -m src.cli export-trinity-spot-bundles --run-id ... --company-id ... --output-dir ...` so maintainers can export reviewed rows directly from local run artefacts
  - limited export eligibility to reviewed/escalated rows with saved `confirm` or `adjust` decisions and documented the new command in `README.md` and `AGENTS.md`
  - added `src/trinity_spot_bundle_regression.py` and validated one generated export against `{train}`'s `load_trinity_spot_training_bundle(...)` loader
- Files touched:
  - `src/trinity_spot_bundle.py`
  - `src/cli.py`
  - `src/trinity_spot_bundle_regression.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/backend_contract_regression.py backend/ops_queue_regression.py backend/segment_worker.py src/benchmark.py src/targeted_adjudication_regression.py src/trinity_spot_bundle.py src/trinity_spot_bundle_regression.py` => passed
  - `PYTHONPATH=/Users/Shared/Projects/spot .venv/bin/python src/trinity_spot_bundle_regression.py` => passed
  - generated a real bundle with `{spot}` and loaded it via `{train}` using `PYTHONPATH=core uv run python -c 'from train_core.trinity_trace_loader import load_trinity_spot_training_bundle ...'` => passed

## 2026-05-11 Europe/Budapest - Codex ({spot} P0 Run Presentation Canonicalization)

- Objective: finish the current `#19` cleanup pass by making run-list, run-state, detail, and artifact-center presentation fields inherit canonicalized progress and review summaries instead of raw `progress.json` counters.
- Changes:
  - added resolved row-counter helpers to `run_state_service` so run presentation fields now use canonical `run_rows` first, segment summaries second, and stale file counters last
  - changed `refresh_run_record(...)` to rewrite presented `progress`, `processing_stats`, top-level progress counters, and review summary from the canonical projection layer
  - kept raw lifecycle metadata such as `started_at`, `completed_at`, and messages from `progress.json`, while replacing only the drift-prone numeric counters
  - added regression coverage proving `/runs/{run_id}` no longer trusts stale `progress.json` row counts over committed canonical row state
- Files touched:
  - `backend/services/run_state_service.py`
  - `backend/backend_contract_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/services/run_state_service.py backend/backend_contract_regression.py backend/main.py` => passed
  - `.venv/bin/python -m unittest backend.backend_contract_regression.BackendContractRegressionTests.test_run_read_surface_prefers_canonical_progress_over_stale_progress_file` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-11 Europe/Budapest - Codex ({spot} P0 Canonical Progress Precedence Cleanup)

- Objective: continue `#19` by normalizing run/upload summary precedence so queue and dashboard surfaces stop trusting file-derived progress counters over canonical DB state.
- Changes:
  - added centralized helpers in `ops_db_service` for resolving total rows, processed rows, and processing stats
  - changed resolved run snapshots to derive row counters from canonical `run_rows` first, segment counters second, and indexed run snapshot data last
  - stopped using `progress.json` as a higher-priority source for processed row counts in queue and dashboard summaries
  - changed upload queue summaries to derive row progress and processing stats from the same canonical precedence contract used by resolved run snapshots
  - added regression coverage proving stale `progress.json` row counts do not outrank canonical committed row state
- Files touched:
  - `backend/services/ops_db_service.py`
  - `backend/ops_queue_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/services/ops_db_service.py backend/ops_queue_regression.py` => passed
  - `.venv/bin/python -m unittest backend.ops_queue_regression.OpsQueueRegressionTests.test_upload_queue_summary_does_not_trust_stale_progress_rows_over_canonical_state` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-11 Europe/Budapest - Codex ({spot} P0 Read-Path Side-Effect Purification)

- Objective: start `#19` by removing hidden checkpoint/output repair work from normal review and detail reads while preserving explicit migration/sync paths for legacy runs.
- Changes:
  - changed canonical review-state projection so projecting from `run_rows` no longer writes `review_state.json` as a side effect
  - restricted `review_state.json` persistence to explicit sync and review-write paths instead of GET-driven read paths
  - changed `refresh_run_record`, `build_run_detail`, `build_review_queue`, and `build_row_inspector` to use pure canonical projections without automatic checkpoint backfill
  - preserved the explicit compatibility bridge in `sync_review_rows_from_output(...)` and the explicit `POST /runs/{run_id}/migrate-row-state` endpoint for legacy/output-backed runs
  - fixed the review-row POST path so, after an explicit migration, it reprojects review state instead of rereading a stale persisted file
  - updated backend regressions to prove review reads no longer import live checkpoint rows unless an explicit sync is invoked
- Files touched:
  - `backend/main.py`
  - `backend/services/run_state_service.py`
  - `backend/backend_contract_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py backend/services/run_state_service.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python -m unittest backend.backend_contract_regression.BackendContractRegressionTests.test_signoff_requires_review_completion backend.backend_contract_regression.BackendContractRegressionTests.test_review_queue_does_not_import_live_checkpoint_rows_without_explicit_sync` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-11 Europe/Budapest - Codex ({spot} P0 Canonical Final Merge Recovery)

- Objective: reduce another remaining child-run filesystem dependency in `#18` by making final run assembly recover missing segment outputs from committed canonical state.
- Changes:
  - added worker helper logic to rebuild a segment workbook from canonical `run_rows` even when the child-run `input.xlsx` and `output.xlsx` are both missing locally
  - changed final run merge to iterate canonical segment records from the ops DB instead of only merging whatever segment directories already contain `output.xlsx`
  - added recovery behavior so a `COMPLETED` segment with full committed progress can recreate its missing output workbook before aggregate merge
  - added queue regression coverage proving a completed segment can restore its missing segment workbook from canonical state alone
- Files touched:
  - `backend/segment_worker.py`
  - `backend/services/ops_db_service.py`
  - `backend/ops_queue_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/segment_worker.py backend/services/ops_db_service.py backend/ops_queue_regression.py` => passed
  - `.venv/bin/python -m unittest backend.ops_queue_regression.OpsQueueRegressionTests.test_rebuild_segment_output_from_canonical_restores_missing_completed_segment_output` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex (Versioning And Documentation Audit)

- Objective: promote the active workspace baseline and audit the maintainer-facing documentation for version drift, source-distribution ambiguity, and incomplete install/update guidance.
- Changes:
  - promoted active workspace markers from `0.5.0` to `0.5.1` and the pipeline marker from `mvp-0.5.0` to `mvp-0.5.1`
  - updated backend runtime version reporting and native bundle metadata to the `0.5.1` baseline
  - rewrote active README sections so the repo no longer reads like an open-source/public-installer distribution when no license or package channel exists
  - clarified the supported source-checkout install, update, removal, and maintenance path for the native local appliance
  - aligned the client package, developer handover, local appliance runbook, and active baseline docs to the same maintainer/support posture
- Files touched:
  - `VERSION`
  - `src/__init__.py`
  - `backend/main.py`
  - `app/macos/Info.plist`
  - `app/macos/README.md`
  - `README.md`
  - `READMEDEV.md`
  - `README_BRIEF.md`
  - `docs/ARCHITECTURE.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/LOCAL_QUEUE_OPERATIONS_PLAN.md`
  - `docs/NATIVE_APP_SCAFFOLD_SPEC.md`
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/CODE_COMMENT_AUDIT.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py src/__init__.py` => passed
  - `plutil -lint app/macos/Info.plist` => passed

## 2026-05-10 Europe/Budapest - Codex (Industry Feature Research And GitHub Ideabank Refresh)

- Objective: research current leader platforms adjacent to `{spot}`, convert the strongest recurring capabilities into an auditable ideabank source, and use that to normalize GitHub planning quality.
- Changes:
  - added an official-source research note covering trust and safety, moderation, consumer-intelligence, and review/compliance platforms relevant to `{spot}`
  - distilled recurring market patterns into a `{spot}`-specific top-25 feature candidate list
  - used that feature list as the source basis for GitHub ideabank issue creation and project-board cleanup
- Files touched:
  - `docs/INDUSTRY_FEATURE_RESEARCH_2026-05-10.md`
  - `docs/HANDOVER.md`

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Canonical Read-Path Hardening)

- Objective: push `#17` further by removing normal review/detail reads from the `output.xlsx` truth path while keeping explicit migration available for legacy runs.
- Changes:
  - changed canonical review-state projection so normal review/detail reads use `run_rows` and only checkpoint import remains as a temporary in-flight compatibility bridge
  - stopped `build_run_detail`, `build_review_queue`, and `build_row_inspector` from opportunistically parsing `output.xlsx` during reads
  - kept explicit legacy workbook import behind `POST /runs/{run_id}/migrate-row-state`
  - changed review-row mutation so an explicit reviewer action can still promote a legacy output-backed row into canonical state before saving the review decision
  - added regression coverage proving read paths no longer parse `output.xlsx` unless migration is invoked explicitly
- Files touched:
  - `backend/main.py`
  - `backend/services/run_state_service.py`
  - `backend/backend_contract_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py backend/services/run_state_service.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Segment Progress From Row Commits)

- Objective: start `#18` by moving segment `processed_rows` updates into the child row-commit path so the parent worker stops inferring segment progress from row-range scans and checkpoint polling.
- Changes:
  - extended `src.cli classify` and `src.pipeline.run_classification(...)` with `canonical_segment_id`
  - changed row completion in `src/pipeline.py` so canonical row persistence and segment-progress updates now happen from the same commit path
  - changed checkpoint resume initialization so resumed committed rows immediately restore segment `processed_rows`
  - changed `backend/segment_worker.py` to pass the owning `segment_id` into the child classifier and to read committed segment counters from `build_run_segment_summary(...)` instead of recomputing per-segment progress from canonical row-range scans
  - added regression coverage proving classification now advances segment progress directly from row commits
- Files touched:
  - `src/cli.py`
  - `src/pipeline.py`
  - `backend/segment_worker.py`
  - `backend/backend_contract_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/cli.py src/pipeline.py backend/segment_worker.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python -m unittest backend.backend_contract_regression.BackendContractRegressionTests.test_run_classification_advances_segment_progress_from_row_commits` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Segment-Counter-First Worker Accounting)

- Objective: continue `#18` by removing more parent-side processed-row inference so startup, live progress, completion, suspend, cancel, and failure paths all prefer committed segment counters over canonical row-range scans.
- Changes:
  - added a shared runtime-stats helper in `backend/segment_worker.py` that combines committed segment totals with canonical threat/review/judge counters
  - changed segment-worker startup accounting to derive `processed_rows` from `build_run_segment_summary(...)`
  - changed resumed-segment bootstrapping to use the claimed segment record's committed `processed_rows` instead of recomputing row-range summaries
  - changed in-loop, post-segment, suspend, cancel, and failure progress writes to reuse the same segment-counter-first runtime stats
- Files touched:
  - `backend/segment_worker.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/segment_worker.py src/cli.py src/pipeline.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Canonical-First Child Resume)

- Objective: continue `#18` by making resumed child classification trust committed canonical `run_rows` before checkpoint replay when deciding which rows are already done.
- Changes:
  - added canonical committed-result restoration in `src/pipeline.py` for resumed classification runs
  - changed resume initialization so checkpoint replay only fills rows still missing from canonical state
  - added regression coverage proving a resumed classification run can skip already committed rows even when `result_checkpoint.jsonl` is absent
- Files touched:
  - `src/pipeline.py`
  - `backend/backend_contract_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/pipeline.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python -m unittest backend.backend_contract_regression.BackendContractRegressionTests.test_run_classification_resumes_from_canonical_rows_without_checkpoint` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Resume Heuristic From Committed Segment State)

- Objective: continue `#18` by removing the segment-worker resume heuristic that depended on `result_checkpoint.jsonl` existence and replacing it with a committed-segment-progress rule.
- Changes:
  - added an explicit `_should_resume_segment_attempt(...)` helper in `backend/segment_worker.py`
  - changed segment resume gating so the worker resumes when `resume_existing` is requested and the claimed segment already has committed `processed_rows > 0`
  - changed resume logging so the worker distinguishes `committed state` from `committed state + checkpoint`
  - added queue regression coverage proving resume gating now uses committed segment progress rather than checkpoint-file presence
- Files touched:
  - `backend/segment_worker.py`
  - `backend/ops_queue_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/segment_worker.py backend/ops_queue_regression.py` => passed
  - `.venv/bin/python -m unittest backend.ops_queue_regression.OpsQueueRegressionTests.test_resume_segment_attempt_uses_committed_progress_not_checkpoint_presence` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Canonical Segment Output Rebuild On Child Failure)

- Objective: continue `#18` by removing one more child-run filesystem dependency from segment completion: when a child classify process dies after fully committing its rows, rebuild the segment workbook from canonical `run_rows` instead of failing solely because the child output file is missing.
- Changes:
  - added `rebuild_output_from_canonical(...)` in `src/pipeline.py` to reconstruct a governed output workbook from canonical committed rows
  - changed `backend/segment_worker.py` so a non-zero child exit can recover by rebuilding the segment output from canonical state when the committed row count already covers the full segment
  - added regression coverage proving canonical output rebuild works and remains compatible with review queue projection
- Files touched:
  - `src/pipeline.py`
  - `backend/segment_worker.py`
  - `backend/backend_contract_regression.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/pipeline.py backend/segment_worker.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python -m unittest backend.backend_contract_regression.BackendContractRegressionTests.test_rebuild_output_from_canonical_recreates_segment_output` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/ops_queue_regression.py` => passed

## 2026-05-10 Europe/Budapest - Codex ({spot} P0 Canonical Run-Row Migration Start)

- Objective: start `#17` by making canonical `run_rows` backfill explicit for legacy and interrupted runs while preserving read-path backfill as a temporary compatibility bridge.
- Changes:
  - added backend `POST /runs/{run_id}/migrate-row-state` as a manage-run endpoint for explicit canonical row-state migration
  - changed run-row checkpoint import so checkpoint replay can backfill all completed rows into `run_rows`, not only `REVIEW_REQUIRED` rows
  - preserved output-workbook and read-path backfill as deterministic compatibility paths for completed legacy runs while projecting review state from canonical `run_rows`
  - added backend regression coverage for output-backed migration and checkpoint-backed non-review row migration
- Files touched:
  - `backend/main.py`
  - `backend/services/run_state_service.py`
  - `backend/backend_contract_regression.py`
  - `README.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py backend/services/run_state_service.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed

## 2026-05-07 Europe/Budapest - Codex (Repository Structure And Documentation Normalization)

- Objective: normalize the active repository layout and maintainer-facing documentation around the current `0.5.0` baseline.
- Changes:
  - renamed the native app source root from `app/spot-app` to `app/macos`
  - aligned version markers to `0.5.0` across the active workspace surfaces
  - documented that `app/macos/.build/` and `app/macos/dist/` are generated, disposable, and intentionally untracked
  - refreshed active maintainer docs so the current baseline describes the native supervisor layer explicitly without rewriting historical delivery records
- Files touched:
  - `.gitignore`
  - `VERSION`
  - `src/__init__.py`
  - `backend/main.py`
  - `README.md`
  - `READMEDEV.md`
  - `README_BRIEF.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/PROJECT_MANAGEMENT.md`
  - `docs/BROWSER_OPERATOR_CONTRACT.md`
  - `docs/NATIVE_APP_BUILD_HANDOFF.md`
  - `docs/NATIVE_APP_SCAFFOLD_SPEC.md`
  - `app/macos/README.md`
  - `app/macos/install-bundle.sh`
- Historical note:
  - older entries below still reference `app/spot-app` because they describe the repo state at the time they were written
  - do not rewrite those entries as if the historical path never existed

## 2026-05-06 Europe/Budapest - Codex (Native Supervisor Lifecycle And Resume Contract)

- Objective: make `spot.app` behave like a supervised local appliance instead of a native shell with a loosely managed backend.
- Changes:
  - added backend `POST /native/runtime/suspend` so the native supervisor can request resumable shutdown for active runs without converting them into operator cancellations
  - changed `backend/segment_worker.py` so supervisor shutdown now writes `INTERRUPTED`, reconciles in-flight segments back to `QUEUED`, and preserves recoverability on the next launch
  - kept operator `cancel` as a separate path that still writes `CANCELLED`
  - changed `SpotCoreService` so native stop, restart, and app termination all suspend active runs before stopping the runtime
  - added native startup auto-recovery for interrupted resumable runs
  - changed `script/build_and_run.sh` so the dev wrapper no longer starts the backend outside `spot.app`
  - added backend regression coverage for the new suspend contract
- Files touched:
  - `backend/main.py`
  - `backend/segment_worker.py`
  - `backend/backend_contract_regression.py`
  - `app/spot-app/Sources/SpotApp.swift`
  - `app/spot-app/Sources/SpotCoreService.swift`
  - `app/spot-app/Sources/SpotModels.swift`
  - `script/build_and_run.sh`
  - `docs/NATIVE_APP_BUILD_HANDOFF.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py backend/services/run_state_service.py backend/segment_worker.py backend/backend_contract_regression.py` => passed
  - `.venv/bin/python backend/backend_contract_regression.py` => passed
  - `cd app/spot-app && swift build` => passed
  - `bash -n script/build_and_run.sh && bash -n app/spot-app/build-bundle.sh` => passed

## 2026-05-05 Europe/Budapest - Codex (Native Dashboard And Summary Recovery Fixes)

- Objective: fix the native dashboard path where watched-folder intake could succeed locally while mission control still showed stale or empty run state.
- Changes:
  - hardened native `SpotRunProgress` decoding so local `run_record.json` files with ISO timestamp strings no longer fail to decode in the Swift shell
  - changed native fallback selection to prefer real local run records over stale inbox-history `run_started` events
  - changed native upload fallback to read local `upload.json` files when `/uploads` is unavailable or late
  - changed backend summary refresh so `/runs`, `/runs/{run_id}`, `/runs/{run_id}/state`, and artifact-center summaries no longer rescan `output.xlsx` on every refresh
  - preserved workbook review synchronization on review-specific routes only
  - updated native handoff docs to describe watched-folder intake, inbox activity persistence, local file fallback, and lightweight summary routing
- Files touched:
  - `app/spot-app/Sources/SpotModels.swift`
  - `app/spot-app/Sources/SpotCoreService.swift`
  - `app/spot-app/Sources/SpotViews/SpotWorkspaceView.swift`
  - `backend/main.py`
  - `backend/services/run_state_service.py`
  - `docs/NATIVE_APP_BUILD_HANDOFF.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py backend/services/run_state_service.py` => passed
  - native backend probe after restart: `/api/health`, `/runs`, `/uploads`, `/operations/overview`, and `/runs/minta-ne-metorsza-g-20260505-204351/detail` all responded quickly
  - `swift build` => passed
  - `bash app/spot-app/build-bundle.sh` => passed

## 2026-03-18 Europe/Budapest - Codex (Pre-Delivery Truth Correction)

- Objective: restore one clear current-state picture before first client delivery by aligning version markers, SSOT-facing docs, and acceptance documentation boundaries.
- Changes:
  - corrected the canonical workspace version marker by updating `VERSION` to `0.4.0`
  - turned `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md` back into a reusable current-baseline template
  - preserved the old filled `0.3.2` acceptance session as `docs/ACCEPTANCE_EVIDENCE_2026-03-18.md`
  - restored `docs/BENCHMARK_CHECKLIST.md` and `docs/UAT_CHECKLIST.md` as current `0.4.0` operational checklists instead of historical session records
  - updated README, developer handover, architecture, production, and project-management docs to state the real implementation stage: core runtime and browser operator workflow implemented, live current-baseline acceptance still pending
  - updated SSOT wording so the local browser operator surface is explicitly treated as an operational layer and not a second source of product truth
  - clarified that `backend/browser_operator_smoke.py` is deterministic browser integration smoke and not a substitute for live client acceptance
- Files touched:
  - `VERSION`
  - `CHANGELOG.md`
  - `README.md`
  - `READMEDEV.md`
  - `README_BRIEF.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/ACCEPTANCE_EVIDENCE_2026-03-18.md`
  - `docs/ARCHITECTURE.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/PROJECT_MANAGEMENT.md`
  - `docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md`
  - `docs/BROWSER_PRODUCTIONIZATION_EXECUTION_PLAN.md`
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/PRODUCTION_PLAN.md`
  - `ssot/SSOT.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/browser_operator_smoke.py` => passed
  - `python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --ssot ssot/ssot.json --runs-dir runs --logs-dir logs --skip-install` => passed
  - `SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` => passed
  - `.venv/bin/python backend/browser_operator_smoke.py` => passed with `session_role=admin`, accepted upload intake, synthetic completed run, sign-off `accepted_with_conditions`, `retry_status=409`, and browser page render checks
  - `bash -n start_browser_appliance.sh` => passed

## 2026-03-18 Europe/Budapest - Codex (Version And Documentation Normalization)

- Objective: remove drift between the implemented browser-enabled workspace, active docs, and historical release records.
- Changes:
  - promoted the active workspace baseline to `0.4.0`
  - promoted the active pipeline baseline to `mvp-0.4.0`
  - aligned active current-state docs to the `0.4.0` workspace baseline
  - relabeled acceptance benchmark/UAT documents as `0.3.2` acceptance-session evidence rather than current workspace baseline docs
  - corrected the historical `v0.3.1` release documents so they no longer claim the later Granite drafter route
- Files touched:
  - `src/__init__.py`
  - `backend/main.py`
  - `README.md`
  - `README_BRIEF.md`
  - `docs/ARCHITECTURE.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/RELEASE_NOTES_0.3.1.md`
  - `docs/GITHUB_RELEASE_v0.3.1.md`
  - `docs/HANDOVER.md`
- Validation:
  - active runtime version markers now resolve to workspace `0.4.0` and pipeline `mvp-0.4.0`
  - historical `v0.3.1` docs remain explicitly shipped-release records
- Known follow-up:
  - carry the `0.4.0` baseline consistently into future browser-phase release notes once that milestone is ready to ship

## 2026-03-18 Europe/Budapest - Codex (Browser Recovery Flows)

- Objective: implement operator-safe retry, cancel, and recovery flows for the browser run lifecycle.
- Changes:
  - added role-gated run management permission for local operator/admin sessions
  - persisted `start_payload` in run records so browser retries can restart a failed or cancelled run deterministically
  - added `POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/retry`, and `POST /runs/{run_id}/recover`
  - exposed pause/resume/cancel/retry/recover controls on the dedicated run-detail browser page
  - extended shaped run detail with `available_operations` and `recovery` status
  - aligned README and browser operator contract docs to the new run-operations surface
- Files touched:
  - `backend/services/auth_service.py`
  - `backend/services/run_state_service.py`
  - `backend/main.py`
  - `README.md`
  - `docs/BROWSER_OPERATOR_CONTRACT.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py` => passed
  - `.venv/bin/python` TestClient smoke => passed for run detail recovery contract, `recover`, `retry`, and `cancel` on a synthetic failed run record
- Known follow-up:
  - add browser-surface handling for rejected upload revalidation and richer failure messaging if product scope still requires that beyond run lifecycle recovery

## 2026-03-18 Europe/Budapest - Codex (Browser UX Polish Baseline)

- Objective: deliver the first coherent visual-system and responsive UX polish pass over the browser operator surfaces.
- Changes:
  - improved the dashboard with shared top navigation, stronger run/upload selection states, and more readable status tiles
  - improved run detail action guidance and recovery summaries without changing backend workflow scope
  - tightened queue, row-inspector, and artifact messaging so operators see concise summaries before raw JSON-like detail
  - preserved browser responsiveness across dashboard, run detail, review queue, row inspector, and artifact center
  - extracted shared operator-page chrome helpers in `backend/main.py` so the secondary browser pages no longer duplicate their navigation treatment by hand
- Files touched:
  - `backend/main.py`
  - `docs/BROWSER_OPERATOR_CONTRACT.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py` => passed
  - `.venv/bin/python` TestClient smoke => `/`, `/app`, `/runs/browser-recovery-smoke/view`, `/runs/browser-recovery-smoke/review`, `/runs/browser-recovery-smoke/review-rows/2/view`, and `/runs/browser-recovery-smoke/artifacts/view` all rendered successfully
- Known follow-up:
  - if needed, extract the repeated inline page styles into a more maintainable shared browser asset strategy in a later refactor

## 2026-03-18 Europe/Budapest - Codex (Browser Integration Cleanup)

- Objective: review the browser-phase integration seams and remove concrete lifecycle/state regressions before sign-off.
- Findings fixed:
  - stale review rows could survive reruns because review-state sync only appended flagged rows and never removed rows that were no longer `Review Required`
  - cancelled or abandoned runs could drift back to misleading nonterminal states because run refresh trusted `progress.json` over control state
- Changes:
  - review-state sync now rebuilds the flagged-row set from `output.xlsx` while preserving reviewer decisions only for still-flagged rows
  - run refresh now resolves effective lifecycle state from both `progress.json` and `control.json`, including `CANCELLED`, `PAUSED`, and `INTERRUPTED`
  - retry guidance now treats `INTERRUPTED` runs as recoverable in the same browser run-operations flow
- Files touched:
  - `backend/services/run_state_service.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py` => passed
  - `.venv/bin/python` smoke => confirmed `INTERRUPTED` state resolution, stale flagged-row removal after output change, and `CANCELLED` state resolution from control metadata

## 2026-03-18 Europe/Budapest - Codex (Browser Productionization Contract And Smoke Baseline)

- Objective: start the next post-browser implementation phase with a release-readiness contract and one executable browser smoke command.
- Changes:
  - added the browser productionization contract and execution plan documents for milestone `{spot} v0.4.3 Browser Productionization`
  - added `backend/browser_operator_smoke.py` as the repo-native smoke verification for auth, upload intake, run detail, review, artifacts, sign-off, recovery, and browser page renders
  - aligned project-management and README docs to the new productionization contract and verification command
- Files touched:
  - `docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md`
  - `docs/BROWSER_PRODUCTIONIZATION_EXECUTION_PLAN.md`
  - `docs/PROJECT_MANAGEMENT.md`
  - `README.md`
  - `backend/browser_operator_smoke.py`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/browser_operator_smoke.py` => passed
  - `.venv/bin/python backend/browser_operator_smoke.py` => passed with accepted upload intake, synthetic completed run, one review row, sign-off `accepted_with_conditions`, successful recovery endpoint call, and browser page render checks

## 2026-03-18 Europe/Budapest - Codex (Expanded Browser Smoke And Startup Alignment)

- Objective: deepen automated browser verification and align local appliance docs with the supported browser startup surface.
- Changes:
  - expanded `backend/browser_operator_smoke.py` to cover unauthenticated upload rejection, session retrieval, upload-record retrieval, run-state retrieval, filtered review queue, action-log growth, and non-retryable completed-run behavior
  - fixed `run_retry` so retry is only allowed for `FAILED`, `CANCELLED`, or `INTERRUPTED` runs, matching the browser recovery contract
  - updated local appliance runbook and client package docs so the browser dashboard and smoke command are part of the supported appliance delivery posture
- Files touched:
  - `backend/browser_operator_smoke.py`
  - `backend/main.py`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py backend/browser_operator_smoke.py backend/services/*.py src/*.py src/ensemble/*.py src/evaluation/*.py` => passed
  - `.venv/bin/python backend/browser_operator_smoke.py` => passed with `session_role=admin`, accepted upload intake, one review row, `retry_status=409` on a completed synthetic run, and browser page render checks

## 2026-03-12 Europe/Budapest - Codex

- Objective: align {spot} SSOT, runtime defaults, audit reporting, and public docs around the actual Apertus-first architecture.
- Changes:
  - promoted SSOT to `0.2` with explicit runtime and security defaults
  - made lane defaults derive from SSOT
  - added backend-qualified model-spec support for evaluation routing
  - preserved backward compatibility for legacy Ollama tags such as `qwen2.5:7b`
  - fixed resolved model-version reporting for MLX/Apertus runs
  - documented local-only security defaults and current architecture
- Files touched:
  - `ssot/SSOT.md`
  - `ssot/ssot.json`
  - `ssot/ssot.example.json`
  - `src/models.py`
  - `src/ssot_loader.py`
  - `src/defaults.py`
  - `src/lanes.py`
  - `src/classifier.py`
  - `src/pipeline.py`
  - `src/ensemble/ensemble_runner.py`
  - `src/excel_io.py`
  - `src/cli.py`
  - `src/__init__.py`
  - `backend/main.py`
  - `README.md`
  - `DESIGN.md`
  - `FOUNDATION.md`
  - `MONITORING_UI.md`
  - `CHANGELOG.md`
  - `docs/ARCHITECTURE.md`
  - `docs/INGESTION.md`
  - `docs/BRAIN_DUMP.md`
  - `docs/PROJECT_MANAGEMENT.md`
  - `docs/HANDOVER.md`
  - `docs/RELEASE_NOTES_0.3.0.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py` => passed
  - `python3 - <<... load_ssot/defaults ...` => SSOT `0.2`, policy model `mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`, defaults aligned
  - `./.venv/bin/python -m src.cli classify --input samples/tev_apertus_mlx_classifier_smoke4.xlsx ... --run-id ssot-align-smoke --limit 1` => completed successfully
  - smoke artifact proof: `runs/ssot-align-smoke/integrity_report.json` shows `ssot_version=0.2`, `policy_profile=prompt-v0.2`, `model_version=mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`
  - workbook proof: `/tmp/tev_ssot_align_smoke.xlsx` latest appended metadata shows `Model Version=mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`, `SSOT Version=0.2`, `Pipeline Version=mvp-0.3.1`
- Known follow-up:
  - regenerate fresh benchmark and acceptance artifacts under the new `0.3.1` baseline
  - produce production rollout and investment plan from the now-aligned architecture baseline

## 2026-03-12 Europe/Budapest - Codex (Production Planning)

- Objective: convert the aligned `0.3.1` / SSOT `0.2` baseline into a client-ready production delivery plan.
- Changes:
  - added a {spot} production plan document grounded in the current Apertus-first architecture
- Files touched:
  - `docs/PRODUCTION_PLAN.md`
  - `docs/HANDOVER.md`
- Validation:
  - document content cross-checked against `ssot/SSOT.md`, `ssot/ssot.json`, `README.md`, and runtime files under `src/`
- Known follow-up:
  - produce dated client quote using confirmed hardware configuration and labor rate assumptions

## 2026-03-12 Europe/Budapest - Codex (Commercial Alignment)

- Objective: align the {spot} production plan with Sentinel Squad's Value Credit commercial model.
- Changes:
  - replaced day-rate style pricing assumptions with Value Credit packaging in the production plan
- Files touched:
  - `docs/PRODUCTION_PLAN.md`
  - `docs/HANDOVER.md`
- Validation:
  - production plan content cross-checked against the provided Sentinel Squad pricing rules and the {spot} production baseline
- Known follow-up:
  - attach final hardware pass-through quote once the client hardware configuration is fixed

## 2026-03-12 Europe/Budapest - Codex (Client Quote)

- Objective: produce a client-sendable commercial quote for {spot} using the Sentinel Squad Value Credit model and a subscription structure.
- Changes:
  - added `quote.md` with a hardware-backed monthly subscription proposal
  - bundled hardware, implementation recovery, and monthly product/management into one monthly price
- Files touched:
  - `quote.md`
  - `docs/HANDOVER.md`
- Validation:
  - quote values cross-checked against the current {spot} production plan and the live hardware pricing basis used in this session
- Known follow-up:
  - confirm final hardware procurement route before signature if the client wants a different machine specification

## 2026-03-12 Europe/Budapest - Codex (Master Brief)

- Objective: create one top-level document that explains {spot} end-to-end from goal through architecture, delivery model, and operating method.
- Changes:
  - added `README_BRIEF.md` as the master project brief
  - linked the brief from the main README documentation map
- Files touched:
  - `README_BRIEF.md`
  - `README.md`
  - `docs/HANDOVER.md`
- Validation:
  - brief content cross-checked against SSOT, runtime docs, production plan, and quote documents
- Known follow-up:
  - keep `README_BRIEF.md` updated whenever the SSOT or commercial model materially changes

## 2026-03-17 Europe/Budapest - Codex (Foundation Hardening Start)

- Objective: start the foundation-hardening pass needed to turn `{spot}` into a delivery-safe local appliance baseline.
- Changes:
  - added a dedicated hardening plan document with workstreams, release gates, and execution phases
  - added the first local appliance runbook for operator-facing local deployment flow
  - clarified in core docs that the standard runtime path is `drafter -> classifier` and that `judge` is only used on disagreement and evaluation paths
  - narrowed quote wording so the client-facing scope matches the implemented antisemitism-classification boundary
- Files touched:
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `README.md`
  - `README_BRIEF.md`
  - `docs/ARCHITECTURE.md`
  - `docs/PRODUCTION_PLAN.md`
  - `quote.md`
  - `docs/HANDOVER.md`
- Validation:
  - documentation changes cross-checked against current runtime behavior in `src/classifier.py`, `src/ensemble/ensemble_runner.py`, `src/pipeline.py`, and current SSOT files
- Known follow-up:
  - add preflight automation and install/bootstrap steps for local Apple Silicon delivery
  - refresh commercial documents further if subscription packaging becomes the sole client model
  - produce fresh smoke evidence package under the current baseline

## 2026-03-17 Europe/Budapest - Codex (Preflight Command)

- Objective: add a supported local-appliance preflight check so machine readiness can be verified before classification or UI startup.
- Changes:
  - added a CLI `preflight` command
  - added local checks for Apple Silicon architecture, virtual environment presence, SSOT validity, runtime dependency availability, loopback-only Ollama configuration, writable runs directory, disk-space headroom, and backend port bindability
  - documented the command in the main README and local appliance runbook
- Files touched:
  - `src/preflight.py`
  - `src/cli.py`
  - `README.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - pending local execution against the current workspace after implementation
- Known follow-up:
  - expand preflight to verify install/bootstrap state and model-weight availability more deeply if delivery requirements tighten

## 2026-03-17 Europe/Budapest - Codex (Bootstrap Command)

- Objective: add a supported local setup path so the appliance has a repeatable bootstrap flow in addition to preflight validation.
- Changes:
  - added a CLI `bootstrap` command
  - added local bootstrap logic for `runs/`, `logs/`, and `.venv/`
  - added optional `requirements.txt` installation and structured JSON output with next steps
  - documented bootstrap usage in the main README and local appliance runbook
- Files touched:
  - `src/bootstrap.py`
  - `src/cli.py`
  - `README.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - pending local execution against the current workspace after implementation
- Known follow-up:
  - add model-weight bootstrap guidance if the delivery process standardises local model storage paths

## 2026-03-17 Europe/Budapest - Codex (SPOT Namespace And Security Hardening)

- Objective: complete the next delivery-hardening step by moving the product-facing runtime namespace to `SPOT_*` and adding stronger production controls and audit outputs.
- Changes:
  - switched the primary runtime environment namespace from `TEV_*` to `SPOT_*`, while keeping temporary compatibility aliases in code
  - added `SPOT_PRODUCTION_MODE` support
  - added production-mode model-route allowlist enforcement for classification and evaluation paths
  - added backend production-mode restrictions to block evaluation start and reject unsupported classify payload keys
  - added `artifact_manifest.json` with per-artifact hashes for completed runs
  - added `disagreement_report.json` for disagreement and judge-path auditability
  - updated product-facing docs and security notes to refer to `{spot}` and `SPOT_*`
- Files touched:
  - `src/defaults.py`
  - `src/classifier.py`
  - `src/pipeline.py`
  - `backend/main.py`
  - `README.md`
  - `FOUNDATION.md`
  - `MONITORING_UI.md`
  - `CHANGELOG.md`
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py` => passed
  - `python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --runs-dir runs --logs-dir logs --skip-install` => passed
  - `SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` => passed
- Known follow-up:
  - complete a fresh classification smoke run under the new artifact-manifest baseline once local model execution is available without blocking

## 2026-03-17 Europe/Budapest - Codex (Security Gap Closure)

- Objective: close the previously identified gaps in the SPOT delivery hardening work.
- Changes:
  - removed TEV runtime alias support and made `SPOT_*` the sole product runtime namespace
  - added production-mode SSOT path locking and full lane-route enforcement for classifier, drafter, and judge
  - added structured fallback reporting on classification results and workbook output
  - added workbook size, row-count, text-length, and null-byte guardrails
  - added explanation sanitisation to reduce prompt/control-text leakage into output files
  - tightened bootstrap to set restrictive local permissions on runtime directories and SSOT
  - tightened preflight to check locked SSOT path and local file permissions
  - tightened CLI behavior so production mode blocks evaluation runs and ensemble classification from the operator path
- Files touched:
  - `src/models.py`
  - `src/defaults.py`
  - `src/classifier.py`
  - `src/excel_io.py`
  - `src/pipeline.py`
  - `src/ensemble/ensemble_runner.py`
  - `src/cli.py`
  - `src/bootstrap.py`
  - `src/preflight.py`
  - `README.md`
  - `MONITORING_UI.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - pending post-change compile and preflight verification in this session
- Known follow-up:
  - complete a successful non-blocking classification smoke run to prove the new fallback and artifact outputs end-to-end

## 2026-03-17 Europe/Budapest - Codex (Client Package And Release Prep)

- Objective: produce a final client-facing package document from the aligned repository state and prepare the current baseline for release tagging.
- Changes:
  - added a consolidated client package document
  - linked the client package from the main README documentation map
- Files touched:
  - `docs/CLIENT_PACKAGE.md`
  - `README.md`
  - `docs/HANDOVER.md`
- Validation:
  - client package content cross-checked against `README_BRIEF.md`, `docs/PRODUCTION_PLAN.md`, `quote.md`, and current runtime/security baseline
- Known follow-up:
  - create and push the release tag for the aligned `0.3.1` baseline

## 2026-03-18 Europe/Budapest - Codex (Benchmark And Acceptance Pack)

- Objective: complete the local-hardware delivery pack with benchmark, UAT, and acceptance-evidence materials.
- Changes:
  - added a benchmark checklist for structured performance and audit validation on the target machine
  - added a UAT checklist for client-side acceptance testing on the local appliance
  - added an acceptance-evidence template so benchmark and UAT outcomes can be recorded consistently
  - linked the new benchmark and acceptance documents from the client package and main README
- Files touched:
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/CLIENT_PACKAGE.md`
  - `README.md`
  - `docs/HANDOVER.md`
- Validation:
  - content cross-checked against the local appliance runbook, client package, current `0.3.1` baseline, and current SSOT `0.2`
- Known follow-up:
  - execute the benchmark and UAT checklists on the target Apple Silicon delivery machine and archive the completed acceptance evidence with the client handover

## 2026-03-18 Europe/Budapest - Codex (Operational Acceptance Execution)

- Objective: execute the local operational acceptance phase on the target Apple Silicon machine and record concrete benchmark and UAT evidence.
- Changes:
  - executed repo-state, compile, bootstrap, and production preflight validation on the target machine
  - executed fresh acceptance benchmark, fallback, and evaluation runs under the current `0.3.2` workspace baseline
  - recorded the session outcome in the acceptance evidence template
  - tightened the benchmark and UAT checklists to require runtime input-guardrail compliance before execution
- Files touched:
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/HANDOVER.md`
- Validation:
  - `git status --short --branch` => clean `main...origin/main`
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py` => passed
  - `python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --ssot ssot/ssot.json --runs-dir runs --logs-dir logs --skip-install` => passed
  - `SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` => passed
  - `SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli classify --input /tmp/spot_acceptance_primary_input.xlsx --output /tmp/spot_acceptance_primary_limit1.xlsx --run-id acceptance-primary-limit1-20260318 --language de --review-mode partial --ssot ssot/ssot.json --runs-dir runs --max-workers 1 --limit 1` => completed in `55s`; output and artefacts written, but workbook row shows `CLASSIFIER_FALLBACK_FAILED`
  - `SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli classify --input /tmp/spot_acceptance_empty_input.xlsx --output /tmp/spot_acceptance_fallback.xlsx --run-id acceptance-fallback-20260318 --language de --review-mode partial --ssot ssot/ssot.json --runs-dir runs --max-workers 1` => completed in `3s`; fallback visibility confirmed with `EMPTY_TEXT_FALLBACK`
  - `.venv/bin/python -m src.cli evaluate --input /tmp/spot_acceptance_primary_input.xlsx --ssot ssot/ssot.json --runs-dir runs --evaluation-run-id acceptance-eval-limit1-20260318 --language de --review-mode partial --single-model mlx://mlx-community/Apertus-8B-Instruct-2509-4bit --ensemble-models ollama://qwen2.5:7b,ollama://gemma2:9b,ollama://llama3.1:8b --max-workers 1 --limit 1 --progress-every 1` => completed in `3m15s`; single and ensemble artefacts written, but `disagreement_count=0`, so no `disagreement_report.json`
  - direct runtime probes on target machine:
    - local Ollama `gemma3:1b` JSON probe => success in `10.27s`
    - direct MLX Apertus probe => success in `18.77s`
- Evidence:
  - acceptance record: `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - primary benchmark artefacts: `runs/acceptance-primary-limit1-20260318/`
  - fallback artefacts: `runs/acceptance-fallback-20260318/`
  - evaluation artefacts: `runs/acceptance-eval-limit1-20260318/`, `runs/acceptance-eval-limit1-20260318-single/`, `runs/acceptance-eval-limit1-20260318-ensemble/`
- Operational findings:
  - `samples/sample_germany.xlsx` is not acceptance-safe under current runtime guardrails because row `257` exceeds the maximum supported `Post text` length of `10000`
  - the target machine passes bootstrap and preflight, and both Ollama and MLX are locally reachable, but the benchmark row still resolved via `CLASSIFIER_FALLBACK_FAILED`; clean primary-route semantic acceptance remains outstanding
  - evaluation execution succeeded, but no actual disagreement case was triggered in this session, so judge-path evidence remains incomplete
- Known follow-up:
  - rerun benchmark and UAT on an approved client workbook that satisfies the runtime input guardrails
  - capture at least one clean primary-route benchmark row without classifier fallback
  - capture at least one genuine disagreement case that emits `disagreement_report.json`
  - complete client/operator sign-off against the recorded acceptance evidence

## 2026-03-18 Europe/Budapest - Codex (Granite Drafter Routing)

- Objective: move the drafter primary route to IBM Granite Nano and support ordered drafter fallbacks.
- Changes:
  - changed the drafter primary runtime route to `ollama://granite4:350m`
  - changed the drafter fallback chain to `ollama://gemma3:1b` then `ollama://llama3.2:1b`
  - updated drafter runtime parsing so `fallback_model` can hold an ordered comma-separated fallback list for the drafter lane
  - updated SSOT defaults and product/runtime docs to reflect the new drafter routing
- Files touched:
  - `src/classifier.py`
  - `src/ssot_loader.py`
  - `src/defaults.py`
  - `ssot/ssot.json`
  - `ssot/ssot.example.json`
  - `ssot/SSOT.md`
  - `README.md`
  - `README_BRIEF.md`
  - `docs/ARCHITECTURE.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/RELEASE_NOTES_0.3.1.md`
  - `docs/GITHUB_RELEASE_v0.3.1.md`
  - `docs/HANDOVER.md`

## 2026-03-18 Europe/Budapest - Codex (Developer Readme And Version Surface)

- Objective: align the developer-facing handover file and promote the workspace baseline beyond the shipped `v0.3.1` release.
- Changes:
  - rewrote `READMEDEV.md` into a repo-specific developer handover for `{spot}`
  - promoted the workspace baseline to `0.3.2` and the pipeline baseline to `mvp-0.3.2`
  - updated active baseline references in the main brief, architecture, production, appliance, benchmark, UAT, acceptance, and client-package documents
  - added a `0.3.2` changelog entry while keeping `v0.3.1` as the latest shipped release
- Files touched:
  - `READMEDEV.md`
  - `VERSION`
  - `src/__init__.py`
  - `backend/main.py`
  - `README.md`
  - `README_BRIEF.md`
  - `CHANGELOG.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/ARCHITECTURE.md`
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py` => passed
  - direct file checks confirmed `VERSION=0.3.2`, `PIPELINE_VERSION=mvp-0.3.2`, backend app version `0.3.2`, and updated `0.3.2` baseline references in active docs
- Known follow-up:
  - execute the benchmark and UAT pack on the target Apple Silicon machine and record the evidence for client acceptance

## 2026-03-17 Europe/Budapest - Codex (Release Draft Package)

- Objective: complete the release-delivery package for the aligned `v0.3.1` baseline.
- Changes:
  - added a GitHub-ready release draft document with release title, executive summary, and full release body
- Files touched:
  - `docs/GITHUB_RELEASE_v0.3.1.md`
  - `docs/HANDOVER.md`
- Validation:
  - release draft cross-checked against `docs/RELEASE_NOTES_0.3.1.md`, `docs/CLIENT_PACKAGE.md`, and the pushed `v0.3.1` baseline
- Known follow-up:
  - publish the GitHub release text through the hosting UI if needed

## 2026-03-18 Europe/Budapest - Codex (Browser Startup Path And Acceptance Doc Alignment)

- Objective: finish the supported browser appliance startup contract and align the acceptance pack to the browser-era operator workflow.
- Changes:
  - added `start_browser_appliance.sh` as the supported local browser appliance entrypoint with default preflight execution
  - updated the main developer, operator, and client-facing docs to use the startup script instead of raw `uvicorn`
  - extended the acceptance evidence, benchmark checklist, and UAT checklist to explicitly capture browser startup, browser smoke, dashboard access, upload flow, review flow, and artifact retrieval
- Files touched:
  - `start_browser_appliance.sh`
  - `README.md`
  - `READMEDEV.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/CLIENT_PACKAGE.md`
  - `docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`
  - `docs/BENCHMARK_CHECKLIST.md`
  - `docs/UAT_CHECKLIST.md`
  - `docs/HANDOVER.md`

## 2026-05-05 Europe/Budapest - Codex (Native App Scaffold Spec)

- Objective: convert the learned `{reply}` native-shell pattern into a concrete `{spot}` implementation scaffold without prematurely writing app code.
- Changes:
  - added `docs/NATIVE_APP_SCAFFOLD_SPEC.md` as the file-by-file scaffold for a future `spot.app`
  - defined the exact phase-1 file set: Swift package, plist, build/install scripts, launch wrapper, app entrypoint, runtime supervisor, and native build handoff
  - documented the native-shell boundary clearly: `spot.app` should supervise the existing local appliance runtime, not replace the Python classification stack
  - documented required method names, bundle contents, local writable paths, launch environment expectations, UI scope, and validation gates
- Files touched:
  - `docs/NATIVE_APP_SCAFFOLD_SPEC.md`
  - `docs/HANDOVER.md`
- Validation:
  - documentation-only change; no code-path validation required
- Known follow-up:
  - implement the scaffold in the documented order once the native-app build milestone starts

## 2026-05-05 Europe/Budapest - Codex (Native App Scaffold Security Hardening)

- Objective: tighten the `{spot}` native-app scaffold so security requirements are explicit rather than implied.
- Changes:
  - expanded `docs/NATIVE_APP_SCAFFOLD_SPEC.md` with a dedicated security position, mandatory constraints, forbidden shortcuts, launch/auth rules, and native security validation gates
  - clarified that the goal is secure-by-default local behavior, not an impossible claim of `100% secure`
- Files touched:
  - `docs/NATIVE_APP_SCAFFOLD_SPEC.md`
  - `docs/HANDOVER.md`
- Validation:
  - documentation-only change; no code-path validation required
- Known follow-up:
  - enforce these constraints in the eventual `spot.app` scaffold and runtime supervisor implementation

## 2026-05-05 Europe/Budapest - Codex (Native App Scaffold Implementation)

- Objective: implement the first `{spot}` native-app scaffold in repo rather than leaving only planning docs.
- Changes:
  - added `app/spot-app` as a Swift 6 macOS 15 native shell package with `SpotApp`, `SpotCoreService`, and minimal workspace/control-center/settings views
  - added deterministic icon, bundle, and install scripts for `spot.app`
  - added `script/build_and_run.sh` as the native dev wrapper that writes native runtime config, builds the bundle, starts the bundled launcher, opens the app, and verifies `/auth/config`
  - added `docs/NATIVE_APP_BUILD_HANDOFF.md` as the native build/install/launch source-of-truth document
  - kept the Python local appliance as the runtime authority; the native shell supervises it instead of rewriting it
- Files touched:
  - `app/spot-app/Package.swift`
  - `app/spot-app/Info.plist`
  - `app/spot-app/build-icon.sh`
  - `app/spot-app/build-bundle.sh`
  - `app/spot-app/install-bundle.sh`
  - `app/spot-app/Scripts/generate_app_icon.swift`
  - `app/spot-app/Sources/SpotApp.swift`
  - `app/spot-app/Sources/SpotCoreService.swift`
  - `app/spot-app/Sources/SpotModels.swift`
  - `app/spot-app/Sources/SpotViews/SpotWorkspaceView.swift`
  - `app/spot-app/Sources/SpotViews/SpotControlCenterView.swift`
  - `app/spot-app/Sources/SpotViews/SpotSettingsView.swift`
  - `script/build_and_run.sh`
  - `docs/NATIVE_APP_BUILD_HANDOFF.md`
  - `docs/HANDOVER.md`
- Validation:
  - `cd app/spot-app && swift package dump-package >/dev/null` => passed
  - `cd app/spot-app && swift build` => passed
  - `cd app/spot-app && ./build-bundle.sh` => passed; bundle written to `app/spot-app/dist/spot.app`
  - `cd app/spot-app && bash -n ./build-icon.sh && bash -n ./build-bundle.sh && bash -n ./install-bundle.sh && plutil -lint ./Info.plist` => passed
  - `bash -n ./script/build_and_run.sh` => passed
  - `bash ./script/build_and_run.sh --verify` => passed; `spot.app runtime ready on 127.0.0.1:8765`
- Known follow-up:
  - the native shell still opens the browser operator surface for the real review workflow; a fully native review workspace remains future work
  - production install and first-run config UX for native runtime values remain future hardening work

## 2026-05-05 Europe/Budapest - Codex (Native App Config Bootstrap Hardening)

- Objective: continue the `{spot}` native scaffold by reducing first-run ambiguity around native runtime configuration.
- Changes:
  - taught `SpotCoreService` to create a first-run `native-runtime.env` template automatically under `~/Library/Application Support/spot`
  - added native UI actions to open or rewrite that config template from the control-center and settings surfaces
  - tightened dev-wrapper permissions so native config is written as `0600` and runtime directories are created with `0700`
  - aligned `docs/NATIVE_APP_BUILD_HANDOFF.md` with the new config-template and permission behavior
- Files touched:
  - `app/spot-app/Sources/SpotCoreService.swift`
  - `app/spot-app/Sources/SpotViews/SpotControlCenterView.swift`
  - `app/spot-app/Sources/SpotViews/SpotSettingsView.swift`
  - `script/build_and_run.sh`
  - `docs/NATIVE_APP_BUILD_HANDOFF.md`
  - `docs/HANDOVER.md`
- Validation:
  - `cd app/spot-app && swift build` => passed
  - `bash -n ./script/build_and_run.sh` => passed
  - `bash ./script/build_and_run.sh --verify` => passed; `spot.app runtime ready on 127.0.0.1:8765`
- Known follow-up:
  - production install should eventually replace the template/default access-code story with a deliberate first-run setup flow

## 2026-05-05 Europe/Budapest - Codex (Native Health Contract Cleanup)

- Objective: continue the `{spot}` native scaffold by replacing the opportunistic auth-config readiness probe with a dedicated loopback health contract.
- Changes:
  - added `GET /api/health` to `backend/main.py` for native runtime readiness probing without depending on auth configuration semantics
  - switched the native shell and dev wrapper from `/auth/config` to `/api/health`
  - updated the native build handoff document to reflect the dedicated health endpoint
- Files touched:
  - `backend/main.py`
  - `app/spot-app/Sources/SpotModels.swift`
  - `app/spot-app/Sources/SpotCoreService.swift`
  - `script/build_and_run.sh`
  - `docs/NATIVE_APP_BUILD_HANDOFF.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile backend/main.py` => passed
  - `cd app/spot-app && swift build` => passed
  - `bash ./script/build_and_run.sh --verify` => passed; `spot.app runtime ready on 127.0.0.1:8765`
- Known follow-up:
  - native runtime summary can later consume richer health payload fields if the backend grows a fuller appliance health model

Cockpit report workflow verification (2026-11-08): 81 model-free regression tests passed; production preflight passed 54 checks with zero errors (one expected occupied-port warning while the installed app was running; inference was not rechecked). Native bundle built and installed at `/Applications/spot.app`. The installed UI showed the preserved German comparison at 26.7% (8/30), all 30 cases awaiting decision, and the human decision/PDF controls. Current Operator role correctly leaves decision/export controls disabled with a Reviewer access link. No real sample decisions or threat exports were created. A synthetic three-page Unicode PDF was visually checked for pagination and readable layout.

Full workbook system test started at the user’s request: `german-full-system-20261108-160954`, upload `upload-1794150590-93fd44c2`, German language, full human review, no row limit. Intake accepted all 62,024 posts with zero quarantined/rejected rows; 125 segments. Installed cockpit showed PROCESSING and the first saved case under Reports. Original workbook and prior acceptance runs retained. No human case decisions were made. This is an active long-running workload, not a completed evaluation or acceptance decision.

Reviewer queue update verified (2026-11-08): 84 model-free regressions passed, including exclusive bucket transitions, follow-up separation, oldest-created ordering/ties, filtering across pages, pagination clamping and new arrivals. Native Swift build, bundle/install, shell syntax and Info.plist checks passed. Installed UI verified Row 3 selected automatically in Waiting for review and the user’s saved Row 2 only in Not antisemitic; temporary unsaved note survived Refresh Queue and was then removed without saving. Full German run was safely suspended for installation and recovered to PROCESSING; 218 canonical cases and the original single user decision verified intact after restart. No additional real human decisions were made.

Exception-only review correction (2026-11-08): the full German run was mistakenly started in full mode, and Review queued all undecided posts. Review now queues only canonical `review_required` exceptions; confident results appear in Automatic with no implied human confirmation. Intake labels partial mode as Automatic / review exceptions, and full as Manual review / every post. Generative drafter normalization was replaced by deterministic whitespace-only preparation: a three-post local reproduction showed the legacy model changed all three texts (1,028→65, 520→512, and 1,964→84 characters), while deterministic preparation preserved every source. Original stored evidence was already protected by rejection and fallback to the original.

The stopped German run was converted to partial mode with `review_routing_service.reconcile_exception_review`: 411 existing rows, 368 verified source-preserving drafter recoveries, 275 genuine review exceptions, 136 eligible automatic results (one has the user’s existing human decision). The original human decision, audit history, and classification evidence were retained; a SQLite backup, previous run record and per-row routing explanation were saved under the run’s `review_policy_history/`. Only review_required and run policy changed. Historical warning flags remain as evidence; current routing and future workbook Review Required cells use canonical review state. Low confidence (<0.65), soft signals, malformed/missing analysis, model disagreement and failed quality checks continue requiring review. Numeric confidence alone does not bypass these checks. Automatically classified threats remain distinct from human-confirmed threats; official confirmed PDF export still requires an explicit human confirmation.

Installed exception-only workflow verification: 89 regression checks passed; native build/bundle/install and syntax/plist checks passed. Installed UI showed Waiting for review and Automatic buckets separately, a reason for each queued exception, and the original Row 2 human decision intact. All 411 original canonical rows matched a full before/after fingerprint excluding only the intentionally changed review_required bit; decision, history and export records matched exactly. The run recovered to PROCESSING in partial mode and produced 5 new results with zero new preparation warnings. At verification: {'total': 416, 'waiting': 278, 'automatic': 137, 'follow_up': 0, 'confirmed_threat': 0, 'false_alarm': 1}. Production preflight passed with 54 checks and zero errors; occupied-port warning expected while the cockpit was running. No actual human case decisions were added or modified by the agent.

Independent-resolution improvement (2026-11-08): SSOT 0.3 / prompt-v0.3-independent-checks activates schema-constrained Qwen 2.5 7B, Gemma 2 9B independent verification, and Llama 3.1 8B quality checks. The old snapshot had 281 review-required rows among 419: 223 second-pass markers, 221 soft-signal review flags, 93 invalid metadata, 47 unstructured outputs (overlapping causes). Source-exact evidence validation replaced the previous single-token overlap acceptance. One bounded structured retry retains both responses. A model cannot grant itself an automatic resolution marker. Automatic completion requires distinct model identities, >=0.85 independent classifier scores, matching categories, a third distinct model PASS >=0.85, no unresolved failure/context flags, source-bound audit traces and exact source evidence for positive classifications. Confidence is the minimum independent score, not the maximum. Full manual-review mode remains available. Oversized prompts fail explicitly instead of being silently truncated.

Controlled pilot: 9/12 oldest waiting cases passed independent checks and were applied; three stayed human exceptions. All 30 balanced German reference posts stayed exceptions under the stricter checks; reference agreement was 9/30, so no taxonomy accuracy improvement or formal acceptance is claimed. Diagnostic evidence and recipes are under `runs/automation-investigation-20261108/`. The pilot is small and ordered, not a prevalence estimate.

A resumable automatic recheck plan now covers 420 earlier machine-analyzed rows and skips the single saved human decision. Machine replacements are transactional, retain the entire previous canonical row in `analysis_revisions`, and refuse to overwrite a human decision or changed evidence. The cockpit shows recheck progress, independent answers/quality results, and Earlier analyses retained. Unfinished notes survive refresh and background rechecks. A full DB backup and preservation baseline precede activation. Installed UI verified automatic Row 3, its previous warnings, preserved human Row 2 and the next waiting exception. At verification all 421 source rows were unchanged, the complete human-reviewed row/decision/history/export records matched the baseline exactly; 16 cases checked, 12 resolved automatically, 404 still scheduled. The live run is PROCESSING: it finishes rechecking prior machine results, then continues the full workbook. 97 regressions passed, native build/install checks passed; production preflight: 49 checks, 0 errors, one expected occupied-port warning. No new real human decisions were made.

Automatic-pending queue separation verified (2026-11-08): Review now defaults to Needs your review and offers a distinct Automatic checks pending bucket. The durable row-level completion markers gate the entire run before pagination. Previous automatic results scheduled for recheck are also pending until finished. A saved human decision takes precedence. Pending cases show no-action-needed text, disabled decision controls, and an API conflict if a premature decision is attempted; pending/ready tokens differ so a stale pre-check view cannot save after completion. Reports and dashboard totals use the same split. Tests cover unresolved/successful completion transitions, page-wide filtering, human precedence, paused plans, incomplete completion state, invalid plans, stale tokens and dashboard totals. 99 regressions passed; native build/bundle/install, syntax/plist, and production preflight passed (49 checks, no errors, one expected occupied-port warning). Installed UI verified both buckets and left the oldest completed exception selected. Live verification: {'total': 421, 'waiting': 77, 'automatic_pending': 300, 'automatic': 43, 'follow_up': 0, 'confirmed_threat': 0, 'false_alarm': 1}; recheck {'state': 'running', 'total': 420, 'processed': 120, 'resolved': 43, 'remaining': 300}. The saved human decision/history, all 421 original source rows, and completed recheck markers were preserved. The run resumed in PROCESSING.
