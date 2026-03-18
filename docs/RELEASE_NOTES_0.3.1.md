# {spot} Release Notes - v0.3.1

This file documents the shipped `0.3.1` release state represented by tag `v0.3.1`.

Release date: 2026-03-17  
Implementation version: `0.3.1`  
Pipeline version: `mvp-0.3.1`  
SSOT version: `0.2`

## Executive Summary

This release turns `{spot}` into an aligned local-appliance baseline with:
- SSOT-governed Apertus-first runtime defaults
- `{spot}` / `SPOT_*` product naming consistency
- local bootstrap and preflight commands
- stronger production-mode controls
- audit hardening for fallback and disagreement paths
- client-facing package and delivery documentation

## Delivered in 0.3.1

### 1) Runtime And SSOT Alignment

Delivered:
- SSOT baseline upgraded to `0.2`
- Apertus on MLX established as the primary classifier route
- Ollama retained as deterministic fallback and support runtime
- runtime defaults aligned to SSOT-driven configuration

Primary runtime:
- classifier: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Support runtime:
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://gemma3:1b`
- drafter fallback: `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`

### 2) Local Appliance Operations

New CLI support:
- `bootstrap`
- `preflight`

Operational effect:
- local directories and Python environment can be prepared in a repeatable way
- appliance readiness can be checked before runtime use
- local permissions and locked SSOT posture can be verified in production mode

### 3) Security Hardening

Delivered:
- `SPOT_*` runtime namespace
- `SPOT_PRODUCTION_MODE`
- locked SSOT path support
- production-mode restrictions on evaluation and unsafe runtime overrides
- loopback-first local posture

Production-mode behavior:
- blocks ad hoc evaluation starts
- restricts classification to SSOT-approved routes
- enforces SSOT-aligned lane routing for classifier, drafter, and judge

### 4) Audit And Artefact Hardening

New/updated artefacts:
- `artifact_manifest.json`
- `disagreement_report.json` for disagreement paths
- workbook `Fallback Events` metadata

Operational effect:
- completed runs now carry file-hash evidence
- fallback behavior is explicitly visible
- disagreement paths are more reconstructable during audit

### 5) Input And Output Contract Hardening

Delivered:
- stricter workbook guardrails
- size and content checks for input rows
- explanation sanitisation against internal control-text leakage

Workbook output metadata now includes:
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

### 6) Product And Delivery Documentation

Added or aligned:
- `README_BRIEF.md`
- `docs/FOUNDATION_HARDENING_PLAN.md`
- `docs/LOCAL_APPLIANCE_RUNBOOK.md`
- `docs/CLIENT_PACKAGE.md`
- `docs/PRODUCTION_PLAN.md`
- `quote.md`

### 7) Branding Alignment

Delivered:
- public product naming aligned to `{spot} - Smart Platform for Observing Threats`
- active TEV-era runtime naming removed from the working repo surface
- backend UI titles aligned to `{spot}`

## Validation Summary

Validated during release preparation:
- Python compile pass across runtime and backend modules
- bootstrap command execution
- preflight command execution in production mode
- deterministic empty-text smoke classification
- artifact manifest generation
- workbook fallback metadata output
- local and remote branch/tag sync

## Known Limits

Intentional limits still remain:
- OCR is out of scope
- scanned document processing is out of scope
- media analysis is out of scope
- automatic language detection is out of scope
- taxonomy CRUD is out of scope
- schema CRUD is out of scope

## Release References

- Tag: `v0.3.1`
- Client package: [`docs/CLIENT_PACKAGE.md`](/Users/moldovancsaba/Projects/spot/docs/CLIENT_PACKAGE.md)
- Brief: [`README_BRIEF.md`](/Users/moldovancsaba/Projects/spot/README_BRIEF.md)
- Production plan: [`docs/PRODUCTION_PLAN.md`](/Users/moldovancsaba/Projects/spot/docs/PRODUCTION_PLAN.md)
