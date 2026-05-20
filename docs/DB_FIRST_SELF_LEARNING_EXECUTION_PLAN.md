# {spot} DB-First Self-Learning Execution Plan

Document date: `2026-05-13`

## Objective

Evolve `{spot}` from a workbook-first local appliance into a canonical-row local intelligence platform with:
- governed import adapters
- deterministic health-check and normalization
- DB-backed canonical working state
- classifier and review workflows operating on canonical rows
- governed export adapters
- a bounded offline learning loop from operator feedback

## Non-Negotiable Guardrails

- `{spot}` remains local-first and auditable
- canonical row schema is the internal contract
- source format is an adapter concern, not the runtime truth model
- operator feedback can improve future models, but must not silently mutate live production behavior
- candidate models must pass offline evaluation and explicit promotion gates before they replace the live route

## Target Architecture

1. Import adapters ingest `.xlsx`, later `.csv`, `.json`, `.txt`, API, DB, and CLI payloads.
2. Staging stores raw source metadata and import diagnostics.
3. Health-check and normalization map source records into one canonical row schema.
4. Canonical rows are persisted in the DB with provenance, validation, and lineage.
5. `{spot}` classifies, reviews, recovers, and exports from canonical DB state.
6. Reviewer actions are persisted as durable feedback records.
7. A bounded offline learning lane curates reviewed examples, runs evaluations, trains candidate adapters, and promotes only validated candidates.

## Canonical Schema Principle

The critical contract is not `.xlsx` versus `.json` versus API. The critical contract is one canonical row schema with explicit semantics for:
- source identity
- row identity
- message text payload
- language
- timestamps
- optional contextual metadata
- provenance and normalization history
- classification state
- review state
- audit lineage

If the schema is strong, adding input and output adapters is manageable. If the schema is weak, `.xlsx` alone is already fragile.

## Recommended Local Learning Stack

### Runtime

- keep live `{spot}` inference on local `mlx` and `ollama` routes
- keep deterministic routing and audit behaviour in `{spot}`, not in the training stack

### Fine-Tuning Method

- use `QLoRA` as the default first training method for reviewed `{spot}` data
- keep `LoRA` available when adapter-serving constraints require it

### Fine-Tuning Tooling

- primary Apple Silicon lane: `mlx-lm` LoRA / QLoRA
- `{spot}` should plan only for Apple Silicon local training and serving
- do not include `Axolotl`, `LLaMA-Factory`, or `Unsloth` in the active `{spot}` delivery plan
- use `Ollama` adapter import only for serving validated adapters locally, not as the training framework

## Why This Recommendation

- `{spot}` already runs on Apple Silicon and already depends on `mlx` / `mlx-lm`
- official `mlx-lm` supports LoRA and QLoRA fine-tuning on Apple Silicon
- `Axolotl`, `LLaMA-Factory`, and `Unsloth` are out of scope for the active `{spot}` Apple-Silicon-only plan
- `Ollama + LoRA` is a deployment option after training, not the core learning strategy

## Safe Self-Learning Loop

The correct loop is not “live automatic retraining.” The correct loop is:

1. capture operator review actions and corrections
2. curate governed training examples with lineage and filters
3. build evaluation splits and benchmark packs
4. train candidate adapters offline
5. compare candidates against the production baseline
6. promote only if acceptance gates pass
7. retain rollback metadata and full model lineage

This allows `{spot}` to improve over time without breaking auditability or silently changing live behaviour.

## Delivery Phases

### Phase 1: Finish Canonical State

- complete DB-centered execution truth
- remove file-backed competing truth paths
- finish attempt, review, metrics, native-consumption, and artifact hardening

### Phase 2: Make Import And Export Adapter-Based

- formalize canonical intake schema
- add importer framework and staging diagnostics
- add `.csv`, `.json`, and `.txt` imports
- add governed export renderers from canonical rows

### Phase 3: Make Feedback Durable And Learnable

- persist reviewer corrections as governed training examples
- attach lineage, review quality, and curation state
- build dataset export and evaluation packs

### Phase 4: Add Offline Training And Promotion

- add Apple Silicon local fine-tuning with `mlx-lm`
- evaluate candidate adapters offline
- add candidate registry, promotion rules, and rollback

### Phase 5: Add Active Learning

- queue uncertain, drifting, and disagreement-heavy rows for review
- use feedback to improve future candidate datasets
- keep the production route stable until explicit promotion

## GitHub Delivery Map

Current hardening lane that should complete first:
- `#3` canonical execution and review state epic
- `#17` canonical run-row persistence
- `#18` transactional segment execution
- `#19` side-effect-free read models
- `#20` unified review persistence
- `#21` metrics semantics
- `#22` explicit run-attempt semantics
- `#23` native/backend state consolidation
- `#24` artifact and audit contract hardening

DB-first ingest and learning-loop lane:
- `#50` DB-first ingest and bounded self-learning architecture epic
- `#51` canonical intake row schema and provenance contract
- `#52` importer adapters, staging, and normalization diagnostics
- `#53` first non-workbook importer set plus governed API and CLI intake
- `#54` canonical DB rows as the only live classification input contract
- `#55` governed export adapters from canonical rows
- `#56` operator feedback as governed learning candidates
- `#57` offline evaluation and candidate promotion gates
- `#58` Apple-Silicon local fine-tuning with `mlx-lm` LoRA / QLoRA
- `#59` candidate model registry with promotion and rollback controls
- `#60` active-learning review queue

## Delivery Rule

Do not begin “self-learning” implementation by wiring automatic model mutation into the live runtime.

Do begin by:
- making canonical DB state authoritative
- making feedback durable and queryable
- making evaluation and promotion explicit
- making training reproducible

That is the only credible way to build a stronger `{spot}` that improves day by day without turning into an opaque system.
