# {spot} Browser Operator Contract

Historical note:
- this document is retained as an archive of the former browser operator phase
- the active operator surface is now the native macOS workspace under `app/macos`

This document is the implementation contract for the browser operator phase tracked by GitHub issue `#1`.

Current contract milestone: `{spot} browser operator baseline`

Note:
- this document describes the browser operator surface
- the native supervisor shell under `app/macos/` is a separate implementation layer around the same runtime

## Purpose

Define the browser-first operator workflow for `{spot}` without changing the product boundary:

- `{spot}` remains a local, deterministic, auditable `.xlsx` classification system
- the browser experience is an operator surface over the existing runtime
- the taxonomy remains the closed antisemitism taxonomy already defined in SSOT
- the standard runtime path remains `drafter -> classifier`
- the disagreement and evaluation path remains `drafter -> classifier -> judge`

## Phase Boundary

This phase introduces a professional browser operator experience for:

- uploading approved `.xlsx` workbooks
- validating intake guardrails
- starting runs
- monitoring run state
- reviewing flagged rows
- annotating review-required rows
- downloading output workbooks and audit artifacts

This phase does not introduce:

- OCR
- generic document scanning
- image or video ingestion
- cloud-first architecture
- taxonomy editing
- multi-label classification
- broad multi-tenant collaboration

## Operator Personas

### Appliance Operator

Primary responsibilities:

- upload approved workbooks
- start and monitor runs
- inspect run failures
- retrieve outputs and audit artifacts

Required permissions:

- create run
- view run and system state
- download completed outputs and artifacts

### Reviewer

Primary responsibilities:

- work through `Review Required` rows
- inspect row-level evidence
- add annotations or reviewer notes
- record row-level review decisions

Required permissions:

- view review queue
- view row inspector evidence
- persist review notes and decisions

### Acceptance Lead

Primary responsibilities:

- verify that a run is operationally acceptable
- confirm required evidence exists
- complete sign-off on accepted output

Required permissions:

- see run status and artifact set
- read reviewer activity
- mark run accepted or not accepted

For the local appliance phase, one person may hold all three roles, but the action model must still distinguish them.

## End-to-End Workflow

### 1. Upload

The operator opens the local browser app and submits one or more `.xlsx` workbooks into the local intake queue.

System behavior:

- stores the workbook in local controlled storage
- validates file type and workbook readability
- validates required worksheet and required columns
- validates current runtime guardrails such as row count and maximum text length
- segments accepted workbook rows into manageable local queue records

Outcome:

- accepted upload with intake record
- or structured rejection with explicit operator-facing reasons

### 2. Run Creation

For an accepted upload, the operator starts a run with the allowed runtime inputs:

- language
- review mode
- optional run label or operator note

System behavior:

- creates a persistent run record
- binds the run to the accepted upload
- records resolved SSOT and route configuration
- schedules the local pipeline execution

### 3. Processing

The system runs the existing deterministic pipeline:

- workbook validation
- row read
- drafter normalization
- classifier decision
- review policy application
- workbook write
- integrity and artifact generation

The browser must reflect real runtime state rather than synthetic progress invented by the UI.

### 4. Review

If rows are flagged, the reviewer opens the review queue.

System behavior:

- lists only rows requiring review for that run
- supports filter and sort for efficient triage
- opens a row inspector with row text, assigned category, explanation, flags, fallback events, and disagreement evidence when present
- persists reviewer notes and review state changes

### 5. Retrieval

When a run completes, the operator can retrieve:

- output workbook
- integrity report
- artifact manifest
- disagreement report when present
- evaluation artifacts when the run type produced them

### 6. Sign-off

The acceptance lead verifies:

- run completed or completed with known conditions
- required artifacts exist
- review-required rows were handled appropriately
- the result is accepted, accepted with conditions, or not accepted

The sign-off decision must be persisted and auditable.

## Required Browser Surfaces

### App Shell

Must provide:

- local entry point
- navigation between upload, runs, review, and artifacts
- visible system readiness and operator identity/session state
- responsive layout and a consistent visual language across dashboard, run detail, review, row inspection, and artifact retrieval

Current backend foundation for this phase:

- `GET /app` serves the local operator dashboard shell
- `GET /` also resolves to the same dashboard
- the dashboard currently exposes upload queue intake, accepted upload selection, recent runs, queue metrics, and run-detail inspection
- the active browser surfaces now share a consistent navigation treatment, stronger selection states, denser operator-facing status cards, and main-dashboard run controls

### Upload Intake Page

Must provide:

- workbook selection/upload
- immediate validation result
- clear acceptance or rejection reasons
- transition into run creation

Current backend foundation for this phase:

- `POST /uploads/intake?filename=<workbook.xlsx>` accepts raw `.xlsx` bytes with legacy `X-Filename` header fallback
- `GET /uploads` lists persisted intake records
- `GET /uploads/{upload_id}` returns the stored intake result
- `GET /operations/overview` returns queue-backed upload, run, and segment summaries
- accepted `upload_id` values can be handed into run creation

### Runs Dashboard

Must provide:

- recent runs
- status, language, review mode, timestamps, and next action
- entry points to run details and pending review work
- queue-backed metrics for row progress, segment progress, throughput, and estimated remaining work

### Run Detail Page

Must provide:

- run metadata
- progress and current stage
- validation or failure messages
- actions available for the current run state
- operator-safe recovery actions for pause, resume, cancel, retry, and state recovery when supported

Current backend foundation for this phase:

- `GET /runs/{run_id}/detail` returns a shaped run-detail contract
- `GET /runs/{run_id}/view` serves a dedicated browser run-detail page
- `POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/retry`, and `POST /runs/{run_id}/recover` now support browser recovery flows
- `POST /classify/pause/{run_id}`, `POST /classify/resume/{run_id}`, and `POST /classify/stop/{run_id}` support active-run control from the main dashboard
- the current page exposes progress, review summary, next actions, recovery status, pause/resume/stop/cancel/retry/recover controls, review-row updates, artifact visibility, and sign-off controls

### Review Queue

Must provide:

- list of review-required rows for a selected run
- sort and filter controls
- triage state visibility

Current backend foundation for this phase:

- `GET /runs/{run_id}/review-rows` supports filter and sort parameters
- `GET /runs/{run_id}/review` serves a dedicated browser review queue page
- the current queue supports filter-by-state, filter-by-decision, confidence/category/state sorting, and row-level triage updates

### Row Inspector

Must provide:

- source row text and row identity
- assigned category
- confidence and explanation fields already emitted by runtime
- fallback and disagreement evidence when present
- reviewer notes and review decisions

Current backend foundation for this phase:

- `GET /runs/{run_id}/review-rows/{row_index}` returns a shaped row-inspector contract
- `GET /runs/{run_id}/review-rows/{row_index}/view` serves a dedicated browser row-inspector page
- the current inspector exposes source row data, explanation, flags, fallback events, disagreement evidence, and persistent reviewer controls

### Artifact Center

Must provide:

- downloadable output workbook
- downloadable audit artifacts
- clear mapping from run to artifact set

Current backend foundation for this phase:

- `GET /runs/{run_id}/artifacts` returns a shaped artifact-center contract
- `GET /runs/{run_id}/artifacts/download/{artifact_name}` downloads a specific run artifact
- `GET /runs/{run_id}/artifacts/view` serves a dedicated browser artifact-center page
- the current page exposes artifact purpose, size, and direct download actions

### Auth And Permission Boundary

Must provide:

- explicit local operator identity/session state
- role-gated browser actions for upload, run start, review, sign-off, and artifact download
- a local appliance auth mode that does not imply cloud identity infrastructure
- auditable actor attribution for state-changing actions

Current backend foundation for this phase:

- `GET /auth/config` returns auth enablement, allowed roles, and local access-code guidance
- `GET /auth/session` returns the current browser session state
- `POST /auth/login` creates a local role session using the shared local access code
- `POST /auth/logout` clears the current session
- the current dashboard exposes actor name, role selection, local access-code entry, and session state
- state-changing browser endpoints now enforce role permissions:
  - `operator`: upload intake, run start, artifact download
  - `reviewer`: row review and annotation updates
  - `acceptance_lead`: sign-off and artifact download
  - `admin`: all current local browser actions

Current polish baseline:

- dashboard cards provide clearer run/upload selection affordances
- run detail presents action guidance and recovery status more clearly
- review queue, row inspector, and artifact center use tighter operator-facing summaries instead of raw status blobs by default
- mobile layout remains supported across the browser pages currently in scope
- shared operator-page chrome is now generated from backend helpers so the local browser surfaces are easier to keep visually aligned

## Persistence Contract

The browser phase requires persistent state beyond workbook files alone.

Minimum required records:

- upload record
- run record
- run lifecycle state
- row review record
- reviewer annotations
- operator action log
- run acceptance/sign-off record

The existing run artifacts remain audit truth. Browser state must reference them, not replace them.

## API Contract Areas

The backend must expose stable operator-facing APIs for:

- workbook upload and intake validation
- run creation
- run listing
- run detail and progress
- review queue retrieval
- row detail retrieval
- annotation and review state updates
- artifact listing and download
- sign-off and acceptance state

Current implemented foundation:

- intake validation persists upload records under local `runs/uploads/`
- `classify/start` accepts `upload_id` and resolves the stored local workbook path
- run records persist under each run directory as `run_record.json`
- review state persists under each run directory as `review_state.json`
- acceptance sign-off persists under each run directory as `signoff.json`
- operator actions persist under each run directory as `action_log.jsonl`

## Security And Locality Constraints

- local-first only for this phase
- no remote object storage redesign
- no remote Ollama broadening implied by the browser work
- browser UI and backend remain on the same appliance
- actions must be permission-gated even when appliance usage is single-user in practice
- local shared-code auth is acceptable for the appliance phase, but actor identity must still be explicit in persisted review, sign-off, and action records
- lifecycle-changing run operations must prefer deterministic local recovery over destructive cleanup, and browser guidance must reflect the actual run state rather than optimistic UI assumptions

## Acceptance Criteria For The Contract

- the operator journey is fully defined from upload to sign-off
- every browser screen has a clear purpose and minimum behavior
- persistence requirements are explicit enough for implementation
- backend contract areas are explicit enough for issue `#2` and `#3`
- non-goals are explicit enough to prevent product drift

## Execution Mapping

This contract feeds the next implementation cards in order:

1. `#2` workbook upload intake API and browser submission flow
2. `#3` run state persistence and review data model
3. `#4` dashboard shell
4. `#5` run detail
5. `#6` review queue
6. `#7` row inspector
7. `#8` artifact center
8. `#9` auth and permission model
9. `#10` recovery flows
10. `#11` design-system polish
