# {spot} GitHub Release Draft - v0.3.1

## Release Title

`{spot} v0.3.1 - Aligned Local Appliance Baseline`

## Executive Summary

`{spot}` is now packaged as a locally deployable, auditable classification system for Excel-based social media review.
The release aligns the runtime, SSOT, and documentation around an Apertus-first local architecture.
It adds appliance bootstrap and preflight commands to support repeatable local hardware delivery.
It strengthens production safety with tighter runtime controls, structured fallback visibility, and hashed audit artefacts.
It also provides a final client package and release documentation so commercial, operational, and technical materials now match the shipped baseline.

## Full Release Body

# {spot} v0.3.1

{spot} - Smart Platform for Observing Threats

## Summary

This release establishes the aligned local-appliance baseline for `{spot}` with:
- SSOT-governed Apertus-first runtime defaults
- `{spot}` / `SPOT_*` product naming consistency
- bootstrap and preflight commands for local delivery
- stronger production-mode controls
- audit hardening for fallback and disagreement paths
- aligned client-facing and production documentation

## Delivered

### Runtime and SSOT alignment
- SSOT baseline upgraded to `0.2`
- Apertus on MLX established as the primary classifier route
- Ollama retained as deterministic fallback and support runtime

Primary runtime:
- classifier: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Support runtime:
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://gemma3:1b`
- drafter fallback: `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`

### Local appliance operations
- added `bootstrap`
- added `preflight`

### Security hardening
- moved to `SPOT_*` runtime namespace
- added `SPOT_PRODUCTION_MODE`
- added locked SSOT path support
- added production-mode restrictions on evaluation and unsafe overrides
- kept loopback-first local posture

### Audit and artefact hardening
- added `artifact_manifest.json`
- added `disagreement_report.json` for disagreement paths
- added workbook `Fallback Events` metadata

### Input and output hardening
- stricter workbook guardrails
- size and content checks for input rows
- explanation sanitisation against prompt/control leakage

### Documentation and client package
- added `docs/CLIENT_PACKAGE.md`
- added `docs/LOCAL_APPLIANCE_RUNBOOK.md`
- added `docs/FOUNDATION_HARDENING_PLAN.md`
- added `docs/RELEASE_NOTES_0.3.1.md`
- aligned `quote.md`, `README_BRIEF.md`, and `docs/PRODUCTION_PLAN.md`

## Validation

Validated during release preparation:
- Python compile pass across runtime and backend modules
- bootstrap command execution
- preflight command execution in production mode
- deterministic empty-text smoke classification
- artifact manifest generation
- workbook fallback metadata output
- local and remote branch/tag sync

## References
- Client package: `docs/CLIENT_PACKAGE.md`
- Brief: `README_BRIEF.md`
- Production plan: `docs/PRODUCTION_PLAN.md`
- Release notes: `docs/RELEASE_NOTES_0.3.1.md`
