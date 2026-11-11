# {spot} Developer Readme

Document date: `2026-11-08`
Workspace baseline: `0.5.2`
Latest shipped release: `v0.3.1`
SSOT baseline: `0.4`

## Purpose

This file is the first-read developer handover for agents working inside the `{spot}` workspace.

Repository distribution truth:
- this repo does not currently declare an open-source license
- treat it as a private maintainer workspace unless the owner adds an explicit license
- the supported install/update posture is source-checkout maintenance plus `app/macos/install-bundle.sh`
- there is no current public package-manager or installer distribution contract

Read this first, then read:
- [`README.md`](/Users/Shared/Projects/spot/README.md)
- [`README_BRIEF.md`](/Users/Shared/Projects/spot/README_BRIEF.md)
- [`docs/ARCHITECTURE.md`](/Users/Shared/Projects/spot/docs/ARCHITECTURE.md)
- [`docs/HANDOVER.md`](/Users/Shared/Projects/spot/docs/HANDOVER.md)
- [`ssot/SSOT.md`](/Users/Shared/Projects/spot/ssot/SSOT.md)
- [`ssot/ssot.json`](/Users/Shared/Projects/spot/ssot/ssot.json)

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
- `judge` scores classifier candidates; targeted adjudication may select an alternate classifier category based on those scores
- `judge` is not called on every row in the standard path

## Runtime Truth

Primary route:
- `classifier`: `ollama://qwen2.5:7b`

Fallback and support routes:
- `classifier fallback / independent verifier`: `ollama://gemma2:9b`
- `drafter`: `ollama://granite4:350m`
- `drafter fallbacks`: `ollama://gemma3:1b`, `ollama://llama3.2:1b`
- `judge`: `ollama://llama3.1:8b`
- `judge fallback`: `ollama://gemma2:2b`

Configuration namespace:
- use `SPOT_*`
- do not reintroduce `TEV_*`

Security posture:
- loopback-first backend
- loopback-only Ollama by default
- production mode via `SPOT_PRODUCTION_MODE=1`
- locked SSOT path via `SPOT_LOCKED_SSOT_PATH`

Shared model install baseline:
- shared model root: `/Users/Shared/Models`
- shared Hugging Face cache: `/Users/Shared/Models/huggingface`
- shared Ollama store: `/Users/Shared/Models`
- use `preflight` as the final gate after populating those roots on a new machine
- if compatibility with legacy user-cache probing is needed, point `~/.cache/huggingface` at the shared Hugging Face root via symlink

## Current Delivery Baseline

The repo already includes:
- bootstrap command
- preflight command
- native macOS supervisor app under `app/macos`
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
- build and install the native macOS app
- run the native acceptance smoke
- run benchmark checklist
- run UAT checklist
- record evidence with the acceptance template

## Versioning Rules

- Workspace baseline is the current repo state under development.
- Shipped release is the latest tagged, published baseline.
- Keep these distinct.

Current state:
- workspace baseline: `0.5.2`
- pipeline baseline: `mvp-0.5.2`
- latest shipped release: `v0.3.1`

Update these surfaces together when the workspace baseline changes:
- [`VERSION`](/Users/Shared/Projects/spot/VERSION)
- [`src/__init__.py`](/Users/Shared/Projects/spot/src/__init__.py)
- [`backend/main.py`](/Users/Shared/Projects/spot/backend/main.py)
- native bundle metadata under [`app/macos/`](/Users/Shared/Projects/spot/app/macos)
- current-baseline docs such as [`README.md`](/Users/Shared/Projects/spot/README.md), [`README_BRIEF.md`](/Users/Shared/Projects/spot/README_BRIEF.md), and active planning/operational docs

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
python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py backend/services/*.py
```

Operational validation when touching delivery/runtime behaviour:

```bash
python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --ssot ssot/ssot.json --runs-dir runs --logs-dir logs --skip-install
SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765
```

Native app validation when touching `app/macos`:

```bash
cd /Users/Shared/Projects/spot/app/macos
swift package dump-package >/dev/null
swift build
bash -n ./build-icon.sh
bash -n ./build-bundle.sh
bash -n ./install-bundle.sh
plutil -lint ./Info.plist
```

## Current Next Step Priority

The active maintainability baseline is:
- current workspace baseline is `0.5.2`; `VERSION` and active docs are aligned to that baseline
- native macOS supervisor baseline is implemented in code
- queue-backed local operations and dashboard monitoring are implemented behind the native macOS workspace
- canonical run-row migration is now started, but read-path compatibility backfill still exists and must be retired deliberately in a later hardening step
- remaining work is foundation hardening, DB-centered execution migration, release cutover, and fresh client-machine acceptance evidence on the current baseline

## Audit hardening verification

Run `bash script/verify-contracts.sh` for the model-free regression suite. The GitHub workflow runs the same suite; native builds and inference verification still require the target Apple Silicon machine.

Run production preflight with `--inference-smoke` before accepting a machine. Ordinary preflight validates prerequisites; it does not prove inference works. `/api/health` reports startup readiness and explicitly reports inference as `not_checked`. Never treat `launch.ready` as classification acceptance.

Inference requests default to 120 seconds, with bounded 512-token responses. Override the deadline with `SPOT_INFERENCE_TIMEOUT_SEC`; `OLLAMA_TIMEOUT_SEC` remains a compatibility fallback. MLX uses response-only stdout; diagnostics are kept out of model response parsing.

The native supervisor enables local authentication and generates a per-install access code when the stored value is empty or the historical default. Native settings let operators choose their role and actor; this remains shared-code local authentication rather than independently verified organizational identities.

Canonical DB writes and workbook output enforce failure review even in `none` mode. Missing/invalid categories retain the governed fallback label only as a placeholder with `ANALYSIS_FAILED`, confidence zero, and `REVIEW_REQUIRED`. Escalation does not count as a completed review. Learning exports exclude escalated rows and rows carrying failure/fallback evidence. Existing artifacts are not rewritten; keep the interim safeguard for historical runs.

Acceptance follow-up now includes `script/acceptance_german.py` for reproducible stratified reference-label comparison and an updated native smoke that attaches to real runs. The production start handler imports its progress default explicitly and closes its parent log handle after worker launch. Drafter output is accepted only when it preserves the source text modulo whitespace; changed evidence is rejected, the original text is classified, and the row is flagged for review. Malformed metadata arrays are flagged instead of being split into character flags.

The cockpit case/report feature adds `case_decisions`, immutable `case_decision_history`, and `threat_report_exports` in the operations DB. SQLite evidence-change triggers and legacy review edits invalidate current confirmations; historical decisions/exports remain available for audit until the run is explicitly purged. `case_report_regression` covers authorization, stale/concurrent decisions, false alarms, integrity checks and PDF pagination/Unicode. reportlab is pinned in runtime requirements; pypdf is used only by regression verification. Case PDFs are generated from an evidence-locked snapshot and do not overwrite the governed classification output.

Reviewer workflow: Review defaults to Waiting for review, with server-side buckets for untouched cases, Needs follow-up (an explicit unresolved decision), Confirmed threats, and Not antisemitic. Buckets are exclusive across the whole run, ordered by the original canonical case creation time then source row index. After a committed decision, the case moves to its bucket and Review returns to the first page of Waiting for review, selecting the next oldest case. Counts include every page; Reviewed includes follow-up cases. New inference results preserve the current case and unfinished note. Confirmed cases remain accessible for PDF export or correction; all prior decisions retain their audit history. Evidence changes invalidate a decision and return the case to Waiting for review.

Exception routing supersedes the earlier all-undecided queue: Waiting includes only rows with `review_required=1` and no saved case decision. Automatic includes non-exception rows without a human decision; a human override moves the row to its explicit decision bucket. Text preparation is deterministic whitespace normalization and no longer calls the configured generative drafter. Historical, rejected drafter outputs can be recognized as recovered only when the actual classifier input matches the source modulo whitespace and the source lineage hash verifies. Use `reconcile_exception_review` only while the run is stopped; it backs up the DB/record, preserves human decisions and evidence, and writes routing audit evidence. Failures and other uncertainty remain exceptions.

Independent automatic checks (SSOT 0.3): partial mode obtains two distinct classifier opinions and a third-model quality check. Automatic completion requires agreement, both classifier scores >=0.85, quality PASS >=0.85, valid structured responses, verified original source, and exact source evidence for positive claims. An automatic marker alone is insufficient. Context/format failures and disagreements remain human exceptions. Schema-constrained Ollama responses replace the unreliable primary MLX response path; Apertus remains available for comparison. The generative drafter configuration is legacy and unused; text preparation is deterministic. Model confidence is a self-reported score, not a measured accuracy probability.

Pending-check separation: an existing case listed in `automatic_recheck.json` stays in Automatic checks pending until its row is acknowledged in `done_rows` after the check commits. It is excluded from both the human review queue and Automatic complete, regardless of its previous review_required value. Completed unresolved cases enter Needs your review; successful checks enter Automatic complete. Saved human decisions always take precedence. The partition is applied before pagination and reused by Reports and dashboard review totals. Pending cases are read-only, and the decision endpoint rejects premature decisions. Invalid or incomplete plan state is not silently interpreted as a completed check.

Automatic AI reporting (SSOT 0.4): under the approved any-positive rule, any current canonical, primary, independent, or structured-retry analysis assigning a positive antisemitism category at confidence >=0.30 routes directly to AI reports and generates a branded PDF. No human review or cross-model agreement is required for that reporting route; warnings, disagreement, failed quality checks and a negative final classification remain visible in the report. Confidence is the score for a category, not calibrated probability of harm. Only the closed antisemitism taxonomy is scored; generic harmful-content categories are not inferred. Reports are explicitly AI-generated and unconfirmed. Saved human decisions, including false alarms and follow-up decisions, take precedence and suppress automatic reports. Later analyses may supersede a report; all exported snapshots remain in audit history. Human-confirmed reports retain their separate confirmation and permission gates. The policy is snapshotted per run; new native runs inherit it automatically, and current runs require explicit activation/backfill.
