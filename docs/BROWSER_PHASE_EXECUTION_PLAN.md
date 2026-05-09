# {spot} Browser Phase Execution Plan

Historical note:
- this execution plan is preserved for browser-phase history only
- it is no longer the active implementation plan

This document breaks the browser operator phase into deliverable units under the active project-board stack.

Primary contract:
- [`docs/BROWSER_OPERATOR_CONTRACT.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_OPERATOR_CONTRACT.md)

Board SSOT:
- GitHub Project `{spot}` items `#1` through `#11`

## Execution Order

1. `#1` browser operator workflow and UX acceptance contract
2. `#2` workbook upload intake API and browser submission flow
3. `#3` run state persistence and review data model
4. `#4` browser app shell and operations dashboard baseline
5. `#5` run detail page with live status, progress, and operator actions
6. `#6` review queue for flagged rows and reviewer triage
7. `#7` row inspector with explanations, fallback evidence, and annotations
8. `#8` output and audit artifact download center
9. `#9` local browser auth and operator permission model
10. `#10` operator-safe error handling, retry, cancel, and recovery flows
11. `#11` frontend design system and responsive browser UX polish baseline

## Deliverable Units

### `#1` Contract

- define operator personas and action boundaries
- define upload-to-sign-off workflow
- define required browser screens
- define persistence and API contract areas
- define non-goals and scope guardrails

Exit condition:
- repo contract is published and linked from main docs

### `#2` Upload Intake

- add browser-safe upload endpoint
- persist upload record with local file location and metadata
- validate workbook file type and workbook readability
- validate required columns and runtime guardrails
- return structured acceptance or rejection payload
- connect accepted upload to run creation input contract

Exit condition:
- a browser upload can be accepted or rejected deterministically with auditable intake metadata

### `#3` Persistent Run And Review State

- define storage shape for upload records
- define storage shape for run records and lifecycle states
- define storage shape for row review state
- define storage shape for annotations and reviewer decisions
- define storage shape for operator action log and sign-off record
- expose read/write access patterns required by dashboard and review surfaces

Exit condition:
- run, review, and sign-off state survive restart and are queryable without reading raw workbook files directly

### `#4` Dashboard Shell

- define browser app shell and navigation layout
- add local dashboard entry route
- list runs with core metadata and next action
- expose upload and review entry points
- show appliance readiness state

Exit condition:
- operator can open a local dashboard and navigate the browser workflow baseline

### `#5` Run Detail

- expose run detail API
- display run metadata and lifecycle stage
- show runtime progress and completion/failure state
- expose actions appropriate to current run state
- link to review queue and artifacts

Exit condition:
- operator can understand one run fully without shell access

### `#6` Review Queue

- expose flagged-row query API by run
- support filter and sort semantics
- persist triage state changes
- support reviewer movement through the queue

Exit condition:
- reviewer can process review-required rows from the browser

### `#7` Row Inspector

- expose row-level detail API
- render row text, label, confidence, explanation, and flags
- render fallback events and disagreement evidence when present
- persist reviewer notes and review decisions

Exit condition:
- reviewer can make and store a row-level decision from the browser

### `#8` Artifact Center

- expose artifact listing API by run
- expose output workbook download
- expose key audit artifact downloads
- present artifact purpose clearly in the UI

Exit condition:
- operator can retrieve the full run package without browsing the filesystem manually

### `#9` Local Auth And Permissions

- define local session/auth approach
- define operator roles and action matrix
- gate upload, review, and download actions
- record actor identity in action logs where applicable

Exit condition:
- browser actions are permission-gated consistently for the appliance phase

### `#10` Recovery Flows

- define validation failure UI state
- define runtime failure UI state
- define supported retry and cancel actions
- define blocked-acceptance guidance and operator recovery steps

Exit condition:
- common operator failure paths are recoverable without shell intervention

### `#11` Design System And UX Polish

- define layout and navigation primitives
- define table, status, alert, and action component patterns
- define upload, review, and artifact state patterns
- validate desktop-first responsive behavior across core screens

Exit condition:
- core screens feel visually consistent and client-demo ready

## Cross-Cutting Rules

- preserve `{spot}` branding exactly
- keep `.xlsx` as the only intake/output format
- preserve local-first appliance deployment
- preserve deterministic and auditable runtime behavior
- do not route standard rows through `judge`
- do not broaden the taxonomy or product scope in this phase

## Immediate Build Target

The immediate build target after the contract is:

1. issue `#2` upload intake
2. issue `#3` persistent run/review state

These two cards are the blocking foundations for the browser product surface.
