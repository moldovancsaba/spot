# {spot} Code Comment Audit

Date: `2026-05-03`
Workspace baseline: `0.5.0`

## Scope

Reviewed active runtime and operator-surface paths:
- [`src/pipeline.py`](/Users/moldovancsaba/Projects/spot/src/pipeline.py)
- [`src/classifier.py`](/Users/moldovancsaba/Projects/spot/src/classifier.py)
- [`src/ensemble/ensemble_runner.py`](/Users/moldovancsaba/Projects/spot/src/ensemble/ensemble_runner.py)
- [`backend/main.py`](/Users/moldovancsaba/Projects/spot/backend/main.py)
- [`backend/services/run_state_service.py`](/Users/moldovancsaba/Projects/spot/backend/services/run_state_service.py)
- [`backend/services/ops_db_service.py`](/Users/moldovancsaba/Projects/spot/backend/services/ops_db_service.py)

## Findings

1. The staged processing percentage comment in `src/pipeline.py` was easy to misread as true row completion.
2. Active operator docs had drifted from the implemented intake contract and queue-backed dashboard behavior.
3. Operator-surface terminology in current docs under-described the main-dashboard run controls and live queue metrics now present in code.

## Fixes Applied

- Clarified the lifecycle-progress comment in [`src/pipeline.py`](/Users/moldovancsaba/Projects/spot/src/pipeline.py) so staged artifact progress is explicitly distinguished from operator-facing row progress.
- Aligned active current-state docs to the implemented intake contract: `POST /uploads/intake?filename=<workbook.xlsx>` with legacy `X-Filename` fallback.
- Aligned active current-state docs to the implemented queue-backed native dashboard, local segmentation model, and main-page pause/resume/stop controls.
- Aligned executable smoke coverage to the current intake contract and current operator-surface title strings.

## Result

No critical stale code comments remain in the actively reviewed runtime and operator-surface paths covered by this audit pass.
