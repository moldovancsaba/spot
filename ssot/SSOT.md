# {spot} Single Source of Truth

Version: `0.2`

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
- `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Fallback classifier route:
- `ollama://qwen2.5:7b`

Support lanes:
- drafter: `ollama://granite4:350m`
- drafter fallbacks: `ollama://gemma3:1b` -> `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`
- judge fallback: `ollama://gemma2:2b`

Apertus on MLX is the primary classification architecture.
Ollama is retained for deterministic fallback and benchmark evaluation.

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

- A local browser operator surface may exist over the runtime
- That operator surface does not broaden the product boundary beyond local `.xlsx` classification
- The browser surface is an operational interface, not a second source of product truth
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
