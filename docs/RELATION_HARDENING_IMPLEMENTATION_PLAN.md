# {spot} Relation Hardening Implementation Plan

Document date: `2026-05-19`
Current workspace implementation baseline: `0.5.2`
SSOT baseline: `0.2`

## Objective

Turn the remaining weak runtime relations in `{spot}` into explicit, durable, and testable contracts before broader DB-first ingest and learning work proceeds.

This plan is narrower than the full foundation hardening plan.
It focuses specifically on the live relations between:
- accepted uploads and canonical upload rows
- canonical upload rows and canonical run rows
- runs, run attempts, and queued segments
- managed recovery state and the native supervisor surface
- canonical state and final audit artifacts

## Current Assessment

Current health status on the maintainer machine:
- bootstrap passed and now provisions the shared model-root directories
- preflight passed with `48` checks, `0` errors, and `0` warnings
- backend contract regressions passed
- queue regressions passed
- native Swift package and bundle-script validation passed

Current architecture opinion:
- the runtime is operationally healthy
- the remaining risks are integrity risks, not obvious day-one breakage
- the weakest remaining relations are row lineage, queue ownership, and managed recovery linkage

## Deliverable Issues

Hardening epic:
- [#3](https://github.com/moldovancsaba/spot/issues/3) `{spot}: Refactor onto one canonical execution and review state model`

Existing issues already carrying most of the lane:
- [#17](https://github.com/moldovancsaba/spot/issues/17) canonical run-row persistence and migration
- [#18](https://github.com/moldovancsaba/spot/issues/18) transactional segment execution
- [#19](https://github.com/moldovancsaba/spot/issues/19) side-effect-free read models
- [#20](https://github.com/moldovancsaba/spot/issues/20) unified review persistence
- [#21](https://github.com/moldovancsaba/spot/issues/21) metrics semantics
- [#22](https://github.com/moldovancsaba/spot/issues/22) explicit run-attempt lifecycle
- [#23](https://github.com/moldovancsaba/spot/issues/23) native/backend state consolidation
- [#24](https://github.com/moldovancsaba/spot/issues/24) artifact and audit contract hardening

New deliverable issues created from the May 2026 relation audit:
- [#61](https://github.com/moldovancsaba/spot/issues/61) immutable row lineage between `upload_rows` and `run_rows`
- [#62](https://github.com/moldovancsaba/spot/issues/62) atomic and concurrency-safe segment claiming
- [#63](https://github.com/moldovancsaba/spot/issues/63) fail-fast managed upload and recovery relation handling

## Recommended Delivery Order

1. `#17` close the remaining canonical run-row persistence and migration work
2. `#61` enforce immutable row lineage so canonical row truth is DB-enforced rather than reconstructed
3. `#18` finish transactional segment execution around durable row commits
4. `#62` tighten segment claiming so queue ownership is correct by construction
5. `#19` keep read paths observational and centralize state resolution
6. `#20` finish review-state unification on top of the stronger canonical row model
7. `#21` normalize progress, ETA, and lifecycle field semantics after the truth model is stable
8. `#22` finish explicit run-attempt semantics for retry, recover, heal, and suspend-resume
9. `#63` fail fast on managed relation drift and surface repair-needed states explicitly
10. `#23` remove native-side competing state synthesis and consume backend truth first
11. `#24` finalize manifests and governed evidence only after the recovery and relation contracts are stable

## Phase Breakdown

### Phase 1: Canonical Row Integrity

Issues:
- `#17`
- `#61`

Target outcome:
- one classified row maps to one canonical accepted source row
- lineage is durable enough for rebuild, review, export, and future learning lanes

Exit gate:
- row identity and provenance are explicit and no longer depend on heuristic reconstruction

### Phase 2: Queue Ownership And Execution Safety

Issues:
- `#18`
- `#62`

Target outcome:
- committed row progress and queue ownership cannot drift silently
- one segment can only be owned by one worker at a time

Exit gate:
- retry and recovery no longer depend on best-effort reconciliation of weak segment ownership

### Phase 3: Read And Review Consistency

Issues:
- `#19`
- `#20`
- `#21`

Target outcome:
- GET paths are observational only
- review counts, queue contents, and metrics semantics come from the same canonical contract

Exit gate:
- backend and native consumers can trust the same read semantics without hidden mutation

### Phase 4: Recovery And Native Relation Hardening

Issues:
- `#22`
- `#63`
- `#23`

Target outcome:
- restart and suspend-resume operate from explicit attempt semantics
- managed relation failures are surfaced clearly
- the native app becomes a thin consumer of backend lifecycle truth

Exit gate:
- operators can distinguish resumable, retryable, broken, and purgeable runs from one backend contract

### Phase 5: Audit Closure

Issues:
- `#24`

Target outcome:
- manifests and evidence files project the stabilized canonical truth model

Exit gate:
- artifact outputs can be trusted as external proof of the internal state model

## Dependency Rule For 0.6.0 Work

The DB-first ingest and learning loop epic [#50](https://github.com/moldovancsaba/spot/issues/50) should stay sequenced behind this relation-hardening lane.

Most important follow-on dependency:
- [#54](https://github.com/moldovancsaba/spot/issues/54) should not broaden runtime input contracts until `#61`, `#22`, `#23`, and `#63` are closed or deliberately accepted as residual risk

## Definition Of Done

This lane is done when all of the following are true:
- canonical row lineage is explicit and durable
- segment ownership is atomic and regression-tested
- read paths do not mutate runtime truth
- recovery actions use explicit attempt semantics
- managed relation failures are surfaced instead of silently downgraded
- native runtime views consume backend truth first
- manifests describe the stable governed artifact set
