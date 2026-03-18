# {spot} Browser Productionization Contract

This document is the implementation contract for GitHub issue `#12`.

Current contract milestone: `{spot} v0.4.3 Browser Productionization`

## Purpose

Turn the completed browser operator baseline into a release-ready local appliance increment with:

- repeatable automated verification
- explicit browser startup and packaging guidance
- browser-era acceptance evidence
- release-cutover documentation that does not rewrite historical releases

This phase does not introduce a new product surface. It hardens and packages the browser baseline already delivered in issues `#1` through `#11`.

## Release Boundary

This phase is in scope for:

- automated smoke coverage for the browser operator workflow
- supported startup path for the browser-enabled local appliance
- browser-aware benchmark and UAT evidence
- release-candidate notes and handover for the browser baseline

This phase is out of scope for:

- new taxonomy or runtime behavior
- cloud hosting or remote storage
- OCR or non-`.xlsx` ingestion
- multi-user collaboration expansion
- broad frontend rewrites beyond packaging or maintainability support

## Productionization Done Definition

The browser baseline is productionized only when all of the following are true:

- automated smoke verification exists in-repo and passes on the delivery machine
- the browser-enabled appliance has one supported startup path
- runbook and client package docs describe the browser surface as part of delivery truth
- acceptance evidence includes browser operator workflow proof
- release-candidate handover captures exact commands, outcomes, and known limits

## Required Verification Surface

Automated verification must cover at least:

- local auth login/session
- upload intake acceptance path
- shaped run detail retrieval
- review queue retrieval
- row inspector retrieval
- artifact center retrieval
- review update persistence
- sign-off persistence
- recovery endpoints for recover and cancel/retry-ready state
- browser page render checks for dashboard, run detail, review queue, row inspector, and artifact center

Verification should prefer deterministic synthetic run fixtures over heavyweight live model execution when testing browser integration seams.
That smoke coverage is necessary but not sufficient for client acceptance: live benchmark and UAT evidence on the target machine remain separate release gates.

## Packaging Contract

The browser-enabled appliance must have a single documented operator startup path that:

- preserves loopback-only local access
- starts the backend/browser surface predictably
- remains compatible with bootstrap and preflight
- does not require undocumented developer-only shell steps

## Evidence Contract

Browser-era acceptance evidence must show:

- operator can access the browser surface
- operator can authenticate locally
- operator can intake a valid workbook
- operator can inspect a run in the browser
- reviewer can work a flagged row in the browser
- operator can retrieve artifacts in the browser
- acceptance lead can complete sign-off in the browser

## Execution Mapping

1. `#12` release-readiness contract
2. `#13` automated API and browser operator smoke coverage
3. `#15` browser appliance packaging and startup path
4. `#14` browser acceptance evidence and release candidate package
5. `#16` browser baseline release cutover and post-release handover

## Cross-Cutting Rules

- preserve `{spot}` branding exactly
- preserve local-first, deterministic, auditable `.xlsx` operation
- do not broaden taxonomy or runtime scope
- do not rewrite historical `v0.3.1` release records to match the browser baseline
- use the GitHub project board as the implementation SSOT for this phase
