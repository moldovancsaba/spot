# {spot} Design Baseline

Current workspace implementation: `0.3.1`
Pipeline version: `mvp-0.3.1`
SSOT version: `0.2`

## Product Intent

{spot} is a governed Excel-classification system for antisemitism-related social media text.
The design target is high-confidence classification with deterministic behavior, auditability, and explicit fallback handling.

## Pipeline Design

1. Load and validate SSOT.
2. Validate `.xlsx` schema and reject malformed workbooks early.
3. Read rows from the first sheet using required columns only.
4. Normalize text in the `drafter` lane.
5. Classify through the `classifier` lane.
6. Enforce one valid canonical category.
7. Apply review-mode policy and flags.
8. Write enriched output workbook.
9. Persist policy, progress, logs, and integrity artifacts.

## Lane Design

- `classifier`: final category authority
- `drafter`: internal cleanup / normalization helper
- `judge`: disagreement scoring only

There is no writer lane in {spot}.

## Runtime Design

Primary runtime route is SSOT-driven:
- classifier primary: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://gemma3:1b`
- judge: `ollama://llama3.2:3b`

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
