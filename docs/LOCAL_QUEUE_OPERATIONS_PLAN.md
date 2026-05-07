# {spot} Local Queue Operations Plan

Document date: `2026-05-03`
Workspace baseline: `0.4.1`

## Purpose

This plan defines the next operational step for `{spot}`: turn local uploads and runs into a durable queue-backed appliance without weakening determinism or auditability.

## Brutal Truth

`{spot}` already had enough persisted files to behave like an early appliance, but it did not yet have a real local operations index.

That meant:
- upload and run state existed
- review state existed
- artifacts existed
- but chunk-level progress, queue phases, and segment-wide operational metrics did not

The result was a browser dashboard that could show runs, but not the actual shape of the work waiting behind those runs.

## Delivered In This Phase

This phase adds a local SQLite-backed operations layer under `runs/spot_ops.sqlite3`.

Current schema:
- `uploads`
- `runs`
- `segments`
- `feedback_items`
- `events`

Current queue behavior:
- accepted uploads are segmented automatically at intake time
- the default segment size is `500` rows
- segment rows are durable and linked back to the upload
- when a run is created from an upload, the segment set is attached to that run
- segment phase counts are derived continuously from persisted run progress

Current browser visibility:
- total segments across tracked uploads
- queue progress percentage
- per-upload segment count
- per-upload phase breakdown
- queue overview JSON from `/operations/overview`

## Why SQLite

SQLite is the correct next step here because `{spot}` is intentionally:
- single-node
- local-first
- audit-oriented
- not a distributed cloud service

A local SQLite file is enough to support queue state, operator metrics, and feedback capture without introducing network or service complexity.

## What This Does Not Do Yet

This phase does not introduce:
- multi-worker background execution
- true segment-by-segment processing dispatch
- automatic retry scheduling
- throughput-tuned ETA modeling
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

## Next Phases

1. Background worker
Add a local long-running worker loop that claims queued segments, runs classification for those row ranges, and updates segment lifecycle state directly.

2. Segment-native processing
Move from run-level progress inference to actual segment dispatch and completion records so the queue reflects real execution units rather than derived approximations.

3. Better ETA and throughput metrics
Persist per-segment timings and use them to estimate time remaining based on recent local throughput instead of a simple run-level heuristic.

4. War-room expansion
Add first-class dashboard panels for:
- queued segments
- failed segments
- reviewer backlog
- soft-signal backlog
- sign-off blockers

5. Feedback operations
Persist reviewer overrides and notes as explicit feedback items, then expose them as governed operational evidence rather than as live runtime learning.
