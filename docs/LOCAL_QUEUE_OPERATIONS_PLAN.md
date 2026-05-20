# {spot} Local Queue Operations Plan

Document date: `2026-05-03`
Workspace baseline: `0.5.2`

## Purpose

This document records the active queue-backed appliance posture for `{spot}` and the remaining execution work that still sits on top of it.

## Brutal Truth

`{spot}` now has a real local operations index, but the important remaining work is still about execution correctness, not about adding more dashboard surface area.

What is already true:
- accepted uploads are indexed durably
- canonical upload rows are persisted with immutable provenance
- canonical run rows are persisted with upload lineage
- run attempts and segment ownership are indexed
- native recovery candidates are projected from backend truth
- read surfaces no longer mutate run snapshots as a side effect

What still needs hardening:
- row commit and segment progress must advance transactionally
- queue summaries should continue shrinking compatibility bridges to file-era state
- native/runtime consumers should depend even less on fallback local reconstruction over time

## Delivered In This Phase

The local SQLite-backed operations layer lives under `runs/spot_ops.sqlite3`.

Current schema:
- `uploads`
- `runs`
- `segments`
- `upload_rows`
- `run_attempts`
- `run_rows`
- `feedback_items`
- `events`

Current queue behavior:
- accepted uploads are segmented automatically at intake time
- the default segment size is `500` rows
- canonical intake rows are durable and linked back to the upload
- when a run is created from an upload, the segment set is attached to that run
- segment claims are atomic and concurrency-safe
- upload-backed `run_rows` persist explicit source lineage
- managed upload drift now fails explicitly instead of silently degrading to `None`

Current native/backend visibility:
- total segments across tracked uploads
- queue progress percentage
- per-upload segment count
- per-upload phase breakdown
- per-run recovery candidate state
- canonical row-backed review counts
- queue overview JSON from `/operations/overview`
- run detail, review queue, artifact center, and classify-status reads resolved without state mutation

## Why SQLite

SQLite is the correct next step here because `{spot}` is intentionally:
- single-node
- local-first
- audit-oriented
- not a distributed cloud service

A local SQLite file is enough to support queue state, operator metrics, and feedback capture without introducing network or service complexity.

## What This Does Not Do Yet

This queue baseline still does not finish:
- transactional row-commit execution boundaries
- full attempt-aware recovery accounting
- fully normalized metric semantics
- artifact/audit closure on top of the stabilized queue model
- autonomous classifier self-learning

Those are separate phases.

## Hard Product Position On Learning

Reviewer feedback should be stored.
Reviewer feedback should not silently retrain or mutate live classification behavior.

For `{spot}`, uncontrolled self-learning would damage:
- determinism
- reproducibility
- acceptance defensibility
- audit traceability

The correct posture is:
- collect feedback
- analyze feedback
- turn feedback into explicit SSOT, prompt, or release changes
- ship those changes deliberately

## Remaining Queue Work

1. Transactional segment execution
Make row completion and segment progress advance atomically from canonical state rather than across file and DB seams.

2. Attempt-aware recovery closure
Finish explicit attempt lifecycle semantics so retry, recover, heal, and suspend-resume are attributable across one run history.

3. Metric normalization
Finish normalizing progress, ETA, and lifecycle fields so every consumer reads the same semantics from one backend contract.

4. Native/backend consolidation
Reduce native-side fallback reconstruction as backend truth surfaces become more complete and faster.

5. Audit closure
Project the stabilized queue and canonical row model outward into manifests and acceptance evidence without relying on legacy compatibility bridges.
