# {spot} Benchmark Checklist

Document date: `2026-11-08`
Workspace baseline: `0.5.2`
SSOT: `0.2`

## Purpose

This checklist is used to benchmark `{spot}` on the target Apple Silicon production machine before client acceptance.

## Pre-Benchmark Requirements

- target machine is provisioned
- local runtime bootstrap completed
- preflight passes
- supported native app build/install path is available under `app/macos`
- native acceptance smoke passes: `.venv/bin/python app/macos/native_acceptance_smoke.py --run-id <actual-run-id> --check-intake`
- benchmark workbook satisfies runtime input guardrails: `.xlsx`, <= `25 MiB`, <= `100000` rows, <= `20000` characters per `Post text` cell
- Apertus MLX model weights are available locally
- Ollama fallback and support models are available locally
- benchmark input workbook is approved for use
- benchmark output location is writable

## Benchmark Inputs

Record before execution:
- machine model
- unified memory size
- SSD size
- macOS version
- Python version
- `{spot}` commit hash
- tag or release baseline
- SSOT path
- review mode
- input workbook path
- row count
- language

## Native Baseline Verification

Run before benchmark execution:
- build and install `/Applications/spot.app`
- launch `/Applications/spot.app`
- run `.venv/bin/python app/macos/native_acceptance_smoke.py --run-id <actual-run-id> --check-intake`

Validate:
- native workspace launches
- local auth succeeds when enabled
- upload intake path is responsive
- review, artifact, and recovery seams respond through the native-supported runtime contract

## Benchmark Run 1: Primary Path

Run:
- classification with MLX primary route enabled

Capture:
- run ID
- total rows
- start time
- completion time
- duration
- rows per minute
- output workbook path
- artifact manifest path

Validate:
- run completes
- `policy.json` shows expected primary classifier route
- `integrity_report.json` passes canonical validation
- output workbook contains current metadata columns
- fallback events are absent unless genuinely triggered

## Benchmark Run 2: Fallback Visibility

Run:
- controlled fallback scenario or observed fallback on representative data

Capture:
- run ID
- fallback trigger reason
- fallback events recorded
- affected row count

Validate:
- fallback is visible in workbook `Fallback Events`
- fallback is visible in run artefacts
- final output remains canonical and deterministic

## Benchmark Run 3: Disagreement Path

Run:
- ensemble evaluation or controlled disagreement scenario

Capture:
- evaluation run ID
- disagreement row count
- consensus tier distribution
- judge participation evidence

Validate:
- `disagreement_report.json` exists when disagreement occurs
- disagreement rows preserve votes, final label, judge score, and flags
- disagreement path remains auditable

## Benchmark Outcome Review

Review and record:
- false positives observed
- false negatives observed
- low-confidence row volume
- rows requiring manual review
- whether review threshold feels too high or too low
- whether explanation quality is sufficient for operator use

## Exit Criteria

Benchmark is considered acceptable when:
- primary route completes successfully
- fallback visibility is demonstrated
- disagreement path is auditable
- output metadata is correct
- operator can retrieve all artefacts without engineering help

## Reproducible German acceptance sample

The project owner approved `samples/sample_germany.xlsx` for acceptance on 2026-11-08 and is the designated reviewer. `script/acceptance_german.py prepare` selects five unique, labelled, nonempty posts per canonical category using seed 20261108. Label spelling/case variants are normalized using the runtime taxonomy mapping; Holocaust Denial maps to Classical Antisemitism. Existing reference labels are kept separately and hidden from classifier input. Unlabelled/empty posts and duplicate text are excluded.

Run the sample through the native watched inbox and use `full` review. Score the actual output with the script's `score` command. Failed-analysis fallback placeholders must not count as correct negatives. Report the confusion matrix, failures and review burden, and obtain reviewer adjudication before treating source-label agreement as accuracy. A balanced 30-row sample is preliminary evidence; it does not estimate natural prevalence or establish production accuracy.

The native acceptance smoke attaches to an actual run and validates auth, review access, output download and hashes. It does not construct fictitious completed/recoverable runs or save client review decisions. Launch the installed app first. `--wait-seconds 0` reports pending checks while a run is processing; default waiting is bounded to 30 minutes.
