# {spot} Foundation Baseline

Current workspace implementation: `0.3.1`
Pipeline version: `mvp-0.3.1`
SSOT version: `0.2`

## Purpose

This document defines the non-negotiable engineering baseline that keeps {spot} deterministic, explainable, auditable, and locally governable.

## Non-Negotiable Controls

- Closed taxonomy enforcement with canonical-set validation
- Deterministic decoding (`temperature=0`, `top_p=1`, fixed seed)
- Exactly one category per row
- Fallback assignment to `Not Antisemitic` when uncertain or invalid
- Flags for `EMPTY_TEXT`, `LOW_CONFIDENCE`, taxonomy violations, and runtime fallback events
- Persisted run artifacts for forensic, operational, and regulatory review
- Primary classifier route fixed by SSOT to Apertus on MLX
- Ollama fallback restricted to loopback by default

## Runtime Baseline

SSOT runtime defaults:
- classifier primary: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://gemma3:1b`
- judge: `ollama://llama3.2:3b`

These defaults are loaded from [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json). Environment overrides are allowed, but they are override behavior, not the architectural truth.

## Control Layers

1. `LLM output` (never trusted directly)
2. `Normalization`
3. `Validation` (closed set + fallback)
4. `Canonical category`
5. `Excel write`
6. `Post-write integrity checks`

## Evidence Baseline

Each run must preserve:
- progress state
- resolved lane configuration
- resolved model versions
- prompt / taxonomy / SSOT / pipeline versions
- review policy
- category and flag distributions
- integrity checks

## Evaluation Baseline

- Deterministic single-vs-ensemble comparison supported
- Explicit backend-qualified model specs supported
- Consensus tiers:
  - `HIGH` = 3/3
  - `MEDIUM` = 2/3
  - `LOW` = 1/1/1
- Judge participates only on disagreement paths

## Security Baseline

- Local API/UI bind on `127.0.0.1`
- Local Ollama endpoint only unless `TEV_ALLOW_REMOTE_OLLAMA=1`
- No secrets or personal data are written into code or documentation
- No client-data training is part of the product baseline

## Known Constraints

- Input must be valid `.xlsx`
- One language per run; language is externally guaranteed
- MLX runtime depends on locally available `mlx_lm` and model weights
- If primary MLX classifier route fails, {spot} falls back deterministically and flags the event
