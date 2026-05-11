# {spot} UAT Checklist

Document date: `2026-05-03`
Workspace baseline: `0.5.2`
SSOT: `0.2`

## Purpose

This checklist is used for structured user acceptance testing on the target local `{spot}` appliance.

## Preconditions

- target Apple Silicon machine is provisioned
- `{spot}` bootstrap completed
- `{spot}` preflight passes
- approved client-owned workbook is available
- workbook satisfies runtime input guardrails: `.xlsx`, <= `25 MiB`, <= `100000` rows, <= `20000` characters per `Post text` cell
- operator has access to the native macOS app and output location
- SSOT path is confirmed
- production mode settings are confirmed

## UAT Scope

The UAT confirms that `{spot}`:
- accepts the agreed `.xlsx` input structure
- classifies rows into the governed closed taxonomy
- writes workbook output with the expected metadata
- surfaces review-required cases clearly
- produces auditable run artefacts
- can be operated locally without engineering intervention

## Test 1: Input Acceptance

Validate:
- workbook opens successfully
- required columns are present
- language is set explicitly for the run
- invalid schema is rejected with a clear error

Record:
- input workbook path
- row count
- run language
- validation result

## Test 2: Standard Classification Run

Validate:
- run starts from the agreed operator flow
- run completes successfully
- workbook output is created
- expected metadata columns are present
- assigned categories are canonical

Record:
- run ID
- start time
- completion time
- output workbook path
- artefact directory path

## Test 3: Review Handling

Validate:
- low-confidence rows are visibly flagged
- `Review Required` is populated correctly
- explanations are readable and useful for operators
- review-required rows can be located without engineering help

Record:
- review-required row count
- example row identifiers
- operator assessment of explanation quality

## Test 4: Audit Evidence

Validate:
- `policy.json` exists
- `integrity_report.json` exists
- `artifact_manifest.json` exists
- `logs.txt` exists
- run artefacts are accessible from the local machine

Record:
- artefact directory contents
- manifest verification status
- any fallback or disagreement evidence

## Test 5: Fallback Visibility

Validate when fallback occurs:
- `Fallback Events` is written into the workbook
- fallback is visible in run artefacts
- fallback does not break canonical output

Record:
- fallback event type
- affected rows
- operator visibility assessment

## Test 6: Local Operations

Validate:
- operator can run preflight
- operator can build/install and launch the supported native app
- operator can start and monitor a run
- operator can retrieve outputs and artefacts
- operator can identify the next action when a row requires review

Record:
- operator performing the test
- actions completed without engineering help
- any points of confusion

## Test 7: Native Operator Workflow

Validate:
- operator can sign in through the local native flow when auth is enabled
- operator can upload an `.xlsx` workbook through the supported native intake flow
- operator can open review queue, row inspector, and artifact center views
- operator can complete at least one review annotation and retrieve one output artefact

Record:
- native app build and launch steps used
- upload ID and run ID
- views confirmed by the operator
- any native workflow confusion or blocked actions

## Acceptance Criteria

UAT is acceptable when:
- the agreed workbook runs successfully
- output workbook metadata is correct
- review-required handling is understandable
- run artefacts are complete and accessible
- local operation is workable for the client team
- no critical blocking defect is found

## Sign-Off Record

Record:
- UAT date
- operator name
- reviewer name
- client decision: accepted / accepted with conditions / not accepted
- conditions or follow-up actions
