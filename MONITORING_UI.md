# {spot} Monitoring UI

Current workspace implementation: `0.3.1`

## Purpose

Provides near-real-time monitoring and process control for:
- classification runs (`classify`)
- evaluation runs (`evaluate`)

## URLs

- Classify monitor UI: `http://127.0.0.1:8765/classify-monitor`
- Eval monitor UI: `http://127.0.0.1:8765/agent-eval`

## Classify Monitor

### Endpoints

- `GET /classify/status/{run_id}`
- `POST /classify/start/{run_id}`
- `POST /classify/pause/{run_id}`
- `POST /classify/resume/{run_id}`
- `POST /classify/stop/{run_id}`

### Features

- live progress bar and row counters
- effective state rendering
- start / restart control
- pause / resume control
- stop control
- PID, running, paused, and output visibility
- raw JSON status for audit/debug

## Eval Monitor

### Endpoints

- `GET /agent-eval/status/{evaluation_run_id}`
- `POST /agent-eval/start/{evaluation_run_id}`

### Features

- single-vs-ensemble stage progress
- overall progress percentage
- evaluation report rendering when completed

## Runtime Defaults Used By UI

Defaults now come from [`src/defaults.py`](/Users/moldovancsaba/Projects/spot/src/defaults.py), which resolves its baseline from [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json).

Relevant values:
- `DEFAULT_SSOT_PATH`
- `DEFAULT_SINGLE_MODEL`
- `DEFAULT_ENSEMBLE_MODELS`
- `DEFAULT_INPUT_PATH`
- `DEFAULT_LANGUAGE`
- `DEFAULT_REVIEW_MODE`
- `DEFAULT_MAX_WORKERS`
- `DEFAULT_LIMIT`
- `DEFAULT_PROGRESS_EVERY`
- `DEFAULT_PRODUCTION_MODE`
- `DEFAULT_LOCKED_SSOT_PATH`

## Security Notes

- Backend binds to `127.0.0.1`
- Default Ollama endpoint is loopback-only
- Remote Ollama use requires `SPOT_ALLOW_REMOTE_OLLAMA=1`
- Evaluation start should be disabled when `SPOT_PRODUCTION_MODE=1`

## Artifact Paths

- Classify progress: `runs/<run-id>/progress.json`
- Classify log: `runs/<run-id>/logs.txt`
- Classify policy: `runs/<run-id>/policy.json`
- Eval single progress: `runs/<eval-id>-single/progress.json`
- Eval ensemble progress: `runs/<eval-id>-ensemble/progress.json`
- Eval report: `runs/<eval-id>/evaluation_report.json`
