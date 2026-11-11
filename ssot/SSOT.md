# {spot} Single Source of Truth

Version: `0.4`

## 1. Purpose

This document defines the authoritative scope, runtime posture, input/output contract, and non-negotiable controls for {spot}.
Any implementation, documentation, or operational behavior that contradicts this document is out of policy.

## 2. Product Boundary

{spot} is an offline/local Excel classification system for social media post text.
It classifies rows into a closed antisemitism taxonomy with deterministic and auditable behavior.

{spot} is not:
- OCR
- document scanning
- image/video analysis
- URL analysis
- automatic language detection
- multi-label classification

## 3. Input Contract

- Input format: `.xlsx`
- One language per run
- First worksheet is authoritative
- Required first columns:
  - `Item number`
  - `Post text`
  - `Category`
- Empty or corrupted workbooks must fail explicitly

## 4. Supported Languages

- Hungarian
- German
- Russian
- Other languages via separate runs

Language is externally guaranteed. {spot} does not perform automatic language detection.

## 5. Closed Taxonomy

Exactly one category per row:
- `Anti-Israel`
- `Anti-Judaism`
- `Classical Antisemitism`
- `Structural Antisemitism`
- `Conspiracy Theories`
- `Not Antisemitic`

`Not Antisemitic` is the fallback category.
No row may remain uncategorized.

## 6. Runtime Policy

Primary classifier route:
- `ollama://gemma2:9b`

Independent verifier / fallback classifier route:
- `ollama://qwen2.5:7b`

Support lanes:
- drafter: `ollama://granite4:350m`
- drafter fallbacks: `ollama://gemma3:1b` -> `ollama://llama3.2:1b`
- judge: `ollama://llama3.1:8b`
- judge fallback: `ollama://gemma2:2b`

The active local architecture uses schema-constrained Gemma classification, independent Qwen verification, and a Llama quality check. Apertus/MLX remains available for historical comparison; the controlled German investigation found frequent malformed and ungrounded responses on that route. Text preparation is deterministic whitespace-only normalization; the configured generative drafter is not invoked.

## 7. Determinism

- `temperature=0`
- `top_p=1`
- fixed seed
- no stochastic rerun policy
- versioned SSOT / prompt / model route / pipeline in artifacts

## 8. Output Contract

Output remains `.xlsx`.
{spot} may append governed metadata columns including:
- assigned category
- confidence score
- explanation / reasoning
- flags
- resolved model version
- prompt version
- taxonomy version
- SSOT version
- pipeline version
- run metadata
- row hash

## 9. Review Policy

Supported modes:
- `full`
- `partial`
- `none`

Failed analysis and unresolved fallback evidence require review in every mode, including `none`. A successful alternate verification is informational only when a complete source-bound independent-consensus certificate verifies: distinct classifiers agree, both scores are at least 0.85, positive claims have exact source quotes, and the quality check passes at 0.85 or above with no unresolved problems. Earlier warnings, retries and answers remain in the analysis trace. Full mode still requires human review of every case. A fallback category is a governed output placeholder and must not be treated as a successful negative classification.

Low-confidence rows must be flaggable.
`partial` review flags low-confidence rows.
`full` review flags every processed row.

## 10. Security Posture

- Local execution is the default security model
- API/UI bind to loopback by default
- Ollama loopback URL is the default runtime endpoint
- Remote Ollama is blocked unless explicitly overridden
- No training on client data is part of {spot}

## 11. Operator Surface

- A native macOS operator surface exists over the runtime
- That operator surface does not broaden the product boundary beyond local `.xlsx` classification
- The native surface is an operational interface, not a second source of product truth
- Core runtime policy remains governed by this SSOT and `ssot/ssot.json`

## 12. Auditability

Each run must persist enough evidence to reconstruct:
- what input was processed
- what runtime route was configured
- what model version was used
- what policy and threshold were active
- what flags and outcomes were produced

## 13. Explicit Non-Goals

Out of scope:
- schema CRUD
- taxonomy CRUD
- multi-label classification
- OCR
- media analysis
- URL analysis
- auto language detection

## 14. Automatic AI Reporting

Under the approved any-positive rule, any current canonical, primary, independent, or structured-retry
analysis assigning a positive antisemitism category at confidence `>= 0.30` routes directly to AI reports
and generates a branded PDF. No human review or cross-model agreement is required for that reporting
route; warnings, disagreement, failed quality checks and a negative final classification remain visible
in the report.

- Confidence is the score for a category, not a calibrated probability of harm.
- Only the closed antisemitism taxonomy is scored; generic harmful-content categories are not inferred.
- Reports are explicitly AI-generated and unconfirmed.
- Saved human decisions, including false alarms and follow-up decisions, take precedence and suppress
  automatic reports.
- Later analyses may supersede a report; all exported snapshots remain in audit history.
- Human-confirmed reports retain their separate confirmation and permission gates.
- The policy is snapshotted per run; new native runs inherit it automatically, and current runs require
  explicit activation/backfill.

**Current policy state: this route is DISABLED.** `automatic_reporting.enabled` is `false` in the
governed default, so a new run does not generate automatic AI reports and writes no reporting policy
snapshot. Activation is per run and explicit: it requires `enabled: true` in the SSOT plus an accepted
decision record. Re-enabling requires an adjudicated gold set and a decision record; measured
reference-label agreement does not support unassisted publication. See
`docs/MODEL_SELECTION_DECISION_2026-11-11.md`.
