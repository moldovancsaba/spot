# {spot} Foundation Hardening Plan

Current workspace implementation baseline: `0.3.2`
SSOT baseline: `0.2`
Document date: `2026-03-17`

## Objective

Turn `{spot}` from an aligned prototype baseline into a delivery-safe local appliance package that can run on client-owned Apple Silicon hardware with deterministic behavior, clear operational controls, and minimal legacy ambiguity.

This plan is intentionally focused on production readiness, not broad refactoring for its own sake.

## Hardening Principles

- Preserve the public product name: `{spot} - Smart Platform for Observing Threats`
- Preserve `{spot}` public naming and use `SPOT_*` as the primary environment namespace
- Treat `ssot/SSOT.md` and `ssot/ssot.json` as the authoritative product and runtime contract
- Prefer compatibility-preserving cleanup over invasive renaming
- Prioritise deterministic local operation, auditability, and operator safety

## Current Truth To Preserve

- `{spot}` is a local `.xlsx` classification system for social media post text
- `{spot}` assigns exactly one category per row from a closed antisemitism taxonomy
- Standard runtime flow is `drafter -> classifier`
- `judge` is used only on disagreement and evaluation paths; it is not the category authority
- Apertus on MLX is the primary classifier route
- Ollama remains deterministic fallback and support infrastructure
- Output must remain auditable and versioned

## Workstream 1: Contract And Naming Cleanup

Goal:
- remove legacy ambiguity in public-facing materials without breaking technical compatibility

Tasks:
- align public documents around the same product boundary
- remove generic “problematic content” wording where the actual scope is antisemitism taxonomy classification
- make the standard classification path explicit in architecture and brief documents
- isolate any remaining legacy TEV references as compatibility-only or historical-only
- clean default labels and run IDs that still read as pre-{spot} artifacts where safe

Success criteria:
- no public-facing document implies that three agents vote on every row
- no public-facing document broadens the scope beyond the implemented taxonomy without an explicit product decision
- legacy TEV references remain only where they are intentionally historical or compatibility-related

## Workstream 2: Runtime And Security Hardening

Goal:
- ensure the local appliance behaves predictably and safely on a single machine

Tasks:
- verify loopback-only defaults across backend and model endpoints
- verify remote Ollama remains explicitly opt-in
- document expected disk layout for input, output, runs, logs, and backups
- define retention and cleanup posture for local artifacts
- add a preflight checklist for model availability, disk space, writable directories, and SSOT validity
- define operator-visible failure modes for MLX failure, fallback activation, malformed input, and interrupted runs

Success criteria:
- a clean machine can be validated before first use
- fallback events are visible and auditable
- local-only guarantees are documented and easy to verify

## Workstream 3: Delivery Packaging

Goal:
- make `{spot}` installable and operable as a repeatable local system

Tasks:
- define one supported Apple Silicon hardware baseline
- define one supported installation flow
- define one supported run/start/stop procedure
- package backend/UI startup and CLI entry points into simple operator-facing commands
- document where model weights and runtime dependencies are expected to exist

Success criteria:
- an operator can install, preflight, start, classify, and inspect runs without ad hoc engineering steps

## Workstream 4: Quality And Validation

Goal:
- prove the documented architecture and output contract hold in practice

Tasks:
- expand SSOT and routing validation checks
- add or tighten tests for workbook schema rejection
- add or tighten tests for deterministic fallback behavior
- validate workbook output metadata and audit artifacts
- verify ensemble disagreement flow and judge-path metadata
- run a fresh smoke classification against the current baseline

Success criteria:
- classification path, fallback path, and disagreement path are all verifiable from repo evidence
- a fresh local smoke run produces current version metadata and valid artifacts

## Workstream 5: Operational Readiness

Goal:
- make the local hardware deployment supportable after handover

Tasks:
- write operator runbook
- write failure and recovery guide
- write backup and restore guide
- define acceptance checklist for client machine bring-up
- define go-live checklist for production use

Success criteria:
- support and operations do not depend on oral history
- a future engineer can take over the appliance from the repo alone

## Execution Phases

### Phase A: Truth Freeze

Outputs:
- aligned core docs
- explicit standard-path vs disagreement-path architecture wording
- legacy cleanup register

Exit gate:
- README, brief, architecture, SSOT, and production plan no longer contradict one another

### Phase B: Local Appliance Baseline

Outputs:
- supported hardware profile
- install and preflight procedure
- local runtime directory layout

Exit gate:
- clean-machine setup path is documented end-to-end

### Phase C: Runtime Verification

Outputs:
- fresh smoke evidence
- fallback evidence
- disagreement/judge evidence

Exit gate:
- runtime behavior is demonstrated, not merely described

### Phase D: Operations Package

Outputs:
- operator guide
- recovery guide
- acceptance checklist

Exit gate:
- system is handover-safe for local deployment

## Priority Order

1. Contract and naming cleanup
2. Runtime and security hardening
3. Delivery packaging
4. Quality and validation refresh
5. Operational readiness package

## Explicit Non-Goals For This Hardening Pass

- broad internal symbol refactors without delivery impact
- changing the taxonomy or product scope
- adding cloud dependencies
- converting the system into a media-analysis or document-analysis platform

## Release Gates

`{spot}` should not be treated as delivery-ready until all of the following are true:

1. Public naming and scope are consistent across docs and UI.
2. SSOT, defaults, and runtime behavior match.
3. Local-only security defaults are verified.
4. Primary MLX route works on supported hardware.
5. Deterministic fallback path is visible and flagged.
6. Output workbook metadata is correct and current.
7. Operator runbook and recovery steps exist.
8. A fresh acceptance-ready smoke package exists under the current baseline.

## Immediate Next Steps

- add this hardening plan to the documentation map
- tighten wording in core docs around the actual 3-agent behavior
- refresh production-facing documents where scope wording is too broad
- start a concrete local appliance runbook and preflight checklist
