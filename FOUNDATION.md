# {spot} Foundation Baseline

Current workspace implementation: `0.5.2`
Pipeline version: `mvp-0.5.2`
SSOT version: `0.4`

## Purpose

This document defines the non-negotiable engineering baseline that keeps {spot} deterministic, explainable, auditable, and locally governable.

## Non-Negotiable Controls

- Closed taxonomy enforcement with canonical-set validation
- Deterministic decoding (`temperature=0`, `top_p=1`, fixed seed)
- Exactly one category per row
- Fallback assignment to `Not Antisemitic` when uncertain or invalid
- Flags for `EMPTY_TEXT`, `LOW_CONFIDENCE`, taxonomy violations, and runtime fallback events
- Persisted run artifacts for forensic, operational, and regulatory review
- Primary classifier route fixed by SSOT to ollama Gemma with independent ollama Qwen verification
- Ollama restricted to loopback by default
- Model confidence is a self-reported score, never a calibrated probability of harm

## Runtime Baseline

SSOT runtime defaults:
- classifier primary: `ollama://gemma2:9b`
- independent verifier / classifier fallback: `ollama://qwen2.5:7b`
- judge: `ollama://llama3.1:8b` (fallback `ollama://gemma2:2b`)
- drafter lane: configured (`ollama://granite4:350m`) but **not invoked**; text preparation is deterministic whitespace normalization
- evaluation single-model baseline: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit` (historical comparison only)

These defaults are loaded from [`ssot/ssot.json`](/Users/Shared/Projects/spot/ssot/ssot.json). Environment overrides are allowed, but they are override behavior, not the architectural truth.

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
- Local Ollama endpoint only unless `SPOT_ALLOW_REMOTE_OLLAMA=1`
- No secrets or personal data are written into code or documentation
- No client-data training is part of the product baseline

## Known Constraints

- Input must be valid `.xlsx`
- One language per run; language is externally guaranteed
- MLX runtime depends on locally available `mlx_lm` and model weights
- If primary MLX classifier route fails, {spot} falls back deterministically and flags the event
