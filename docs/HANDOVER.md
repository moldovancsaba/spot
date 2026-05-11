# {spot} Handover Log

Historical note:
- this file is a chronological delivery log, not the active operating contract
- older entries intentionally preserve the browser-phase and `app/spot-app` wording that was true when those entries were written
- current operator and startup guidance lives in [`README.md`](/Users/moldovancsaba/Projects/spot/README.md), [`READMEDEV.md`](/Users/moldovancsaba/Projects/spot/READMEDEV.md), and [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/moldovancsaba/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)

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
