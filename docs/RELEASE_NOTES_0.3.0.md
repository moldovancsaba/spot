# {spot} Release Notes - v0.3.0

This file documents the shipped `0.3.0` release state. The current workspace implementation may be newer.

Release date: 2026-02-28  
Implementation version: `0.3.0`  
Pipeline version: `mvp-0.3.0`  
SSOT version: `0.1` (unchanged)

## Executive Summary

This release hardens {spot} from a CLI-first engine into a governed, monitorable operational system with real-time run visibility and process controls.

Key outcomes:
- Full classify run monitoring UI is now live.
- Start/pause/resume/stop controls are available through API and UI.
- Deterministic and SSOT-governed behavior remains enforced.
- MLX runtime support is installed and integrated for classifier/judge lanes (optional backend).

## Delivered in 0.3.0

### 1) Classify Monitoring UI

New endpoint:
- `GET /classify-monitor`

Capabilities:
- Live state visibility (`NOT_STARTED`, `STARTING`, `PROCESSING`, `PAUSED`, `WRITING`, `COMPLETED`, `FAILED`)
- Live row counters and progress bar
- PID/running/paused visibility
- Raw JSON status panel for audit/debug

### 2) Classify Process Controls

New endpoints:
- `POST /classify/start/{run_id}`
- `POST /classify/pause/{run_id}`
- `POST /classify/resume/{run_id}`
- `POST /classify/stop/{run_id}`
- `GET /classify/status/{run_id}`

Operational behavior:
- Controls work for runs started in UI.
- Controls also work for externally started CLI runs (PID auto-discovery).

### 3) MLX Runtime Integration (Optional)

Installed and pinned:
- `mlx==0.30.6`
- `mlx-lm==0.30.7`

System behavior:
- {spot} can route `classifier`/`judge` lanes to MLX.
- Unstructured MLX outputs are safely handled through deterministic extraction + guard flags.

### 4) Documentation and Versioning Upgrade

Added/updated:
- `README.md` (production-grade onboarding and operations guide)
- `MONITORING_UI.md` (monitoring + control reference)
- `FOUNDATION.md` (baseline guarantees)
- `DESIGN.md` (architecture updates)
- `CHANGELOG.md` (release entries)
- `VERSION` (project version anchor)

## Governance and Compliance Posture

Still enforced in 0.3.0:
- Closed-set taxonomy only
- Exactly one category per row
- Fallback category enforcement (`Not Antisemitic`)
- Deterministic inference policy
- Explainable metadata output
- Run artifact persistence for audit/review

## Operational URLs

Backend base:
- `http://127.0.0.1:8765`

UIs:
- Classify monitor: `http://127.0.0.1:8765/classify-monitor`
- Evaluation monitor: `http://127.0.0.1:8765/agent-eval`

## Known Limits (Intentional)

- SSOT schema CRUD is out of scope.
- Multi-label classification is out of scope.
- Category CRUD is out of scope.
- Media/URL analysis is out of scope.
- Language detection is out of scope.

## Recommended Next Step

Run one full production-like sample with classify monitor controls enabled and archive the resulting:
- `output.xlsx`
- `integrity_report.json`
- `policy.json`
- `progress.json`

as the formal `v0.3.0` operational acceptance package.
