# Changelog

## 0.3.1 - 2026-03-12

- Promoted SSOT to `0.2` and made runtime routing/security defaults explicit in `ssot/ssot.json`.
- Switched {spot} architectural baseline to Apertus-first classification on MLX.
- Made lane defaults derive from SSOT instead of duplicated hard-coded literals.
- Added explicit `backend://model` model-spec support for evaluation and mixed-backend runs.
- Fixed audit reporting so MLX/Apertus runs record the resolved classifier route instead of being mislabeled as Qwen.
- Updated output workbook metadata so `Model Version` reflects the resolved runtime route used for each row.
- Added loopback-only Ollama security guard with explicit opt-out via `TEV_ALLOW_REMOTE_OLLAMA=1`.
- Rewrote architecture/foundation/runtime docs to match the real implementation baseline.

## 0.3.0 - 2026-02-28

- Added full classify monitoring workflow UI at `/classify-monitor`.
- Added classify process control endpoints:
  - `POST /classify/start/{run_id}`
  - `POST /classify/pause/{run_id}`
  - `POST /classify/resume/{run_id}`
  - `POST /classify/stop/{run_id}`
  - `GET /classify/status/{run_id}`
- Added PID auto-discovery so monitor/control also works for classify runs started outside UI.
- Hardened MLX output handling for unstructured model responses:
  - deterministic category extraction guardrails
  - controlled explanation fallback
  - `UNSTRUCTURED_MODEL_OUTPUT` flag
- Installed and pinned MLX runtime dependencies in project requirements.
- Upgraded project documentation to production handover quality.

## 0.2.0 - 2026-02-27

- Replaced `HATORI_*` routing keys with `TEV_*`.
- Removed writer lane from {spot} architecture.
- Added explicit {spot} lane model: `classifier`, `drafter`, `judge`.
- Added optional MLX backend support for classifier and judge lanes.
- Added backend fallback behavior for classifier/judge/drafter routing failures.
- Kept closed-set taxonomy enforcement and fallback category controls intact.
- Preserved deterministic ensemble logic and minority-report evidence.
- Updated documentation for workflow, guarantees, and versioning boundaries.

## 0.1.0

- Initial SSOT-aligned MVP pipeline.
- Deterministic single-label classification.
- Deterministic evaluation framework (single vs ensemble).
- Agent Eval UI with near-real-time progress tracking.
