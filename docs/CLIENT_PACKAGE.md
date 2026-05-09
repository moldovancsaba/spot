# {spot} Client Package

Document date: `2026-05-07`
Workspace baseline: `0.5.0`
Pipeline baseline: `mvp-0.5.0`
SSOT baseline: `0.2`

## Overview

`{spot}` is a local, offline, auditable classification system for large Excel batches of social media post text.

Its purpose is to classify rows into a strict antisemitism taxonomy with:
- deterministic behaviour
- explainable row-level output
- structured review handling
- local data control
- full audit evidence

`{spot}` is designed for local Apple Silicon delivery and does not require normal cloud runtime dependencies.

## What The Client Receives

The delivered `{spot}` package consists of:
- local runtime package
- native macOS supervisor app source under `app/macos` for maintainers
- SSOT-governed configuration baseline
- local appliance runbook
- supported native macOS app build/install path
- operator guidance
- native operator surface with queue intake, monitoring, and process-control interface
- benchmark and acceptance support package
- audit artefact structure for completed runs

## Product Scope

In scope:
- `.xlsx` ingestion
- row-level classification
- exactly one category per row
- deterministic fallback handling
- review flagging for uncertain rows
- local native operator workflow
- local monitoring and run control
- auditable artefact generation

Out of scope:
- OCR
- scanned documents
- image or video analysis
- URL crawling
- automatic language detection
- taxonomy editing in production
- schema editing in production

## Taxonomy

Each row is classified into exactly one of:
- `Anti-Israel`
- `Anti-Judaism`
- `Classical Antisemitism`
- `Structural Antisemitism`
- `Conspiracy Theories`
- `Not Antisemitic`

`Not Antisemitic` is the enforced fallback category.

## Architecture Summary

`{spot}` uses a governed three-role internal architecture:
- `drafter`
- `classifier`
- `judge`

Standard row path:
- `drafter -> classifier`

Disagreement and evaluation path:
- `drafter -> classifier -> judge`

Important:
- the `classifier` remains the category authority
- the `judge` does not override the final category
- the `judge` is used on disagreement and quality-control paths

## Runtime Baseline

Primary route:
- classifier: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Fallback and support routes:
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://granite4:350m`
- drafter fallbacks: `ollama://gemma3:1b`, `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`

## Security Posture

`{spot}` is local-first and conservative by default.

Current posture:
- backend binds to loopback
- Ollama defaults to loopback-only access
- remote Ollama requires explicit override
- production mode can restrict runtime to the locked SSOT path
- production mode can restrict operator-visible override surface
- run artefacts include structured hashes for tamper evidence
- disagreement paths produce dedicated audit output

## Output And Audit Evidence

Completed runs can produce:
- `output.xlsx`
- `progress.json`
- `policy.json`
- `integrity_report.json`
- `artifact_manifest.json`
- `logs.txt`
- `disagreement_report.json` when disagreement paths are used
- `control.json` when started from the monitor

Workbook output metadata includes:
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

## Local Delivery Baseline

Recommended delivery target:
- Apple Silicon Mac mini class machine
- 64GB unified memory target
- 2TB SSD minimum target
- external backup SSD
- UPS

## Commercial Model

Sentinel Squad uses a Value Credit model.

Commercial baseline:
- `1` credit = `$100`
- monthly product and management component = `$2,500`

Recommended delivery packaging:
- Production Bring-up: `8` credits / `$800`
- Calibration and Acceptance: `8` credits / `$800`
- Operational Enablement: `5` credits / `$500`

Base delivery calculation:
- one-time delivery: `21` credits / `$2,100`
- monthly product and management: `$2,500`
- hardware: separate infrastructure line item or managed-appliance commercial treatment

## Acceptance Position

`{spot}` should be treated as ready for structured client acceptance when:
- SSOT loads cleanly
- code compiles cleanly
- supported native macOS app build/install path works on the target machine
- native acceptance smoke verification passes
- preflight passes on the target machine
- the primary MLX route completes a real run
- fallback behaviour is visible and auditable
- output workbook metadata is correct
- acceptance evidence is reviewed against client-owned sample data

Current pre-delivery status:
- native operator workflow is implemented in the local appliance
- native macOS supervisor shell is implemented in the local appliance repository
- native acceptance smoke verification is available as deterministic integration coverage
- fresh live acceptance evidence on the current `0.5.0` native-only baseline is still required before first client delivery

## Maintainer Notes

- native app source root: [`app/macos/`](/Users/moldovancsaba/Projects/spot/app/macos)
- native generated folders: `app/macos/.build/` and `app/macos/dist/`
- current repo does not declare an open-source license file

## Reference Documents

- Brief: [`README_BRIEF.md`](/Users/moldovancsaba/Projects/spot/README_BRIEF.md)
- Production plan: [`docs/PRODUCTION_PLAN.md`](/Users/moldovancsaba/Projects/spot/docs/PRODUCTION_PLAN.md)
- Quote: [`quote.md`](/Users/moldovancsaba/Projects/spot/quote.md)
- Local appliance runbook: [`docs/LOCAL_APPLIANCE_RUNBOOK.md`](/Users/moldovancsaba/Projects/spot/docs/LOCAL_APPLIANCE_RUNBOOK.md)
- Benchmark checklist: [`docs/BENCHMARK_CHECKLIST.md`](/Users/moldovancsaba/Projects/spot/docs/BENCHMARK_CHECKLIST.md)
- UAT checklist: [`docs/UAT_CHECKLIST.md`](/Users/moldovancsaba/Projects/spot/docs/UAT_CHECKLIST.md)
- Acceptance evidence template: [`docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md`](/Users/moldovancsaba/Projects/spot/docs/ACCEPTANCE_EVIDENCE_TEMPLATE.md)
- Architecture: [`docs/ARCHITECTURE.md`](/Users/moldovancsaba/Projects/spot/docs/ARCHITECTURE.md)
- SSOT contract: [`ssot/SSOT.md`](/Users/moldovancsaba/Projects/spot/ssot/SSOT.md)

Supported local startup:

```bash
cd /Users/moldovancsaba/Projects/spot/app/macos
swift build
bash build-bundle.sh
bash install-bundle.sh
open /Applications/spot.app
```
