# {spot} Developer Readme

Document date: `2026-03-18`
Workspace baseline: `0.4.0`
Latest shipped release: `v0.3.1`
SSOT baseline: `0.2`

## Purpose

This file is the first-read developer handover for agents working inside the `{spot}` workspace.

Read this first, then read:
- [`README.md`](/Users/moldovancsaba/Projects/spot/README.md)
- [`README_BRIEF.md`](/Users/moldovancsaba/Projects/spot/README_BRIEF.md)
- [`docs/ARCHITECTURE.md`](/Users/moldovancsaba/Projects/spot/docs/ARCHITECTURE.md)
- [`docs/HANDOVER.md`](/Users/moldovancsaba/Projects/spot/docs/HANDOVER.md)
- [`ssot/SSOT.md`](/Users/moldovancsaba/Projects/spot/ssot/SSOT.md)
- [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json)

## Product Truth

`{spot}` is a local, deterministic, auditable `.xlsx` classification system for social media post text.

The governed scope is narrow:
- `.xlsx` input and output only
- one language per run
- exactly one category per row
- closed antisemitism taxonomy only
- local-first runtime
- persisted audit artefacts per run

Out of scope:
- OCR
- document scanning
- image or video analysis
- URL crawling
- automatic language detection
- production taxonomy editing

## Architecture Truth

Internal three-role structure:
- `drafter`
- `classifier`
- `judge`

Actual runtime paths:
- standard path: `drafter -> classifier`
- disagreement/evaluation path: `drafter -> classifier -> judge`

Important:
- `classifier` is the final category authority
- `judge` does not override the category
- `judge` is not called on every row in the standard path

## Runtime Truth

Primary route:
- `classifier`: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Fallback and support routes:
- `classifier fallback`: `ollama://qwen2.5:7b`
- `drafter`: `ollama://granite4:350m`
- `drafter fallbacks`: `ollama://gemma3:1b`, `ollama://llama3.2:1b`
- `judge`: `ollama://llama3.2:3b`
- `judge fallback`: `ollama://gemma2:2b`

Configuration namespace:
- use `SPOT_*`
- do not reintroduce `TEV_*`

Security posture:
- loopback-first backend
- loopback-only Ollama by default
- production mode via `SPOT_PRODUCTION_MODE=1`
- locked SSOT path via `SPOT_LOCKED_SSOT_PATH`

## Current Delivery Baseline

The repo already includes:
- bootstrap command
- preflight command
- browser appliance startup path
- browser operator smoke coverage
- production-mode restrictions
- audit manifest generation
- fallback event reporting
- disagreement reporting
- benchmark checklist
- UAT checklist
- acceptance evidence template
- client package
- release notes for `v0.3.1`

Current local acceptance path:
- bootstrap the machine
- run preflight
- run the supported browser startup path
- run browser smoke verification
- run benchmark checklist
- run UAT checklist
- record evidence with the acceptance template

## Versioning Rules

- Workspace baseline is the current repo state under development.
- Shipped release is the latest tagged, published baseline.
- Keep these distinct.

Current state:
- workspace baseline: `0.4.0`
- pipeline baseline: `mvp-0.4.0`
- latest shipped release: `v0.3.1`

Update these surfaces together when the workspace baseline changes:
- [`VERSION`](/Users/moldovancsaba/Projects/spot/VERSION)
- [`src/__init__.py`](/Users/moldovancsaba/Projects/spot/src/__init__.py)
- [`backend/main.py`](/Users/moldovancsaba/Projects/spot/backend/main.py)
- current-baseline docs such as [`README.md`](/Users/moldovancsaba/Projects/spot/README.md), [`README_BRIEF.md`](/Users/moldovancsaba/Projects/spot/README_BRIEF.md), and active planning/operational docs

Do not rewrite historical release notes just to match the workspace baseline.

## Working Rules

- Inspect the repo directly before changing it.
- Check `git status` first.
- Preserve `{spot}` branding exactly as written.
- Keep docs aligned with code in the same change.
- Use minimal, reversible edits.
- Do not add dependencies unless necessary.
- Do not weaken local-first or audit guarantees.
- Do not broaden scope from antisemitism classification into generic moderation language unless explicitly requested.

## Validation Expectations

Minimum validation for routine repo work:

```bash
git status --short --branch
python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py backend/browser_operator_smoke.py
```

Operational validation when touching delivery/runtime behaviour:

```bash
python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --ssot ssot/ssot.json --runs-dir runs --logs-dir logs --skip-install
SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765
```

## Current Next Step Priority

The active milestone is browser productionization:
- current workspace baseline is `0.4.0`; `VERSION` and active docs are aligned to that baseline
- browser operator baseline is implemented in code
- browser smoke is synthetic integration verification, not live client acceptance proof
- remaining pre-delivery work is release cutover plus fresh client-machine acceptance evidence on the current baseline
