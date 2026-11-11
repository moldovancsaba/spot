# {spot} Design Baseline

Current workspace implementation: `0.5.2`
Pipeline version: `mvp-0.5.2`
SSOT version: `0.4`

## Product Intent

{spot} is a governed Excel-classification system for antisemitism-related social media text.
The design target is high-confidence classification with deterministic behavior, auditability, and explicit fallback handling.

## Pipeline Design

1. Load and validate SSOT.
2. Validate `.xlsx` schema and reject malformed workbooks early.
3. Read rows from the first sheet using required columns only.
4. Normalize text deterministically (whitespace only; no model call).
5. Classify through the `classifier` lane.
6. Verify independently through the second classifier lane.
7. Enforce one valid canonical category.
8. Apply review-mode policy and flags.
9. Write enriched output workbook.
10. Persist policy, progress, logs, and integrity artifacts.

## Lane Design

- `classifier`: final category authority
- `classifier` (second pass): independent verification of the primary result
- `drafter`: configured lane, **not invoked**; text preparation is deterministic whitespace normalization
- `judge`: disagreement scoring and quality check only

There is no writer lane in {spot}.

## Runtime Design

Primary runtime route is SSOT-driven:
- classifier primary: `ollama://gemma2:9b`
- independent verifier / classifier fallback: `ollama://qwen2.5:7b`
- judge: `ollama://llama3.1:8b` (fallback `gemma2:2b`)
- drafter: configured but not invoked; text preparation is deterministic whitespace normalization

Runtime overrides remain environment-driven, but the default source of truth is `ssot/ssot.json`.

## Evaluation Design

Evaluation is deterministic single-vs-ensemble comparison.
Default benchmark set:
- single: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- ensemble: `ollama://qwen2.5:7b`, `ollama://gemma2:9b`, `ollama://llama3.1:8b`

Model specs now support explicit backend-qualified syntax: `backend://model`.
Legacy Ollama tags such as `qwen2.5:7b` still resolve to Ollama for backward compatibility.
This removes ambiguity when MLX and Ollama coexist in the same evaluation run.

## Output Design

Output remains `.xlsx` and preserves the input sheet structure where possible.
{spot} appends metadata columns for:
- assigned category
- confidence
- explanation
- flags
- resolved model version
- prompt / taxonomy / SSOT / pipeline versioning
- review metadata
- row hash

## Security Design

- Local-first inference
- Ollama loopback-only by default
- remote Ollama blocked unless explicitly overridden
- no cloud dependency required for normal runtime
- no training loop on client data

## Non-goals

- OCR
- document scanning
- media analysis
- URL analysis
- automatic language detection
- multi-label outputs
- taxonomy CRUD
- schema CRUD
