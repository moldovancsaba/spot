# Restart runbook — every component and its crash-recovery path

Every component has exactly one supervisor. After any crash the recovery is automatic or one command.
Nothing in this document is a manual state repair unless labelled DRY-RUN.

| Component | Supervisor | Crash recovery | Verify |
|---|---|---|---|
| `spot.app` (native shell) | macOS (user-launched) | relaunch: `open -a /Applications/spot.app` | app window, `/api/health` |
| Backend (`uvicorn backend.main`) | spot.app watchdog (SPOT_NATIVE_SUPERVISOR_PID) | automatic restart by the app | `curl http://127.0.0.1:8765/api/health` |
| Segment workers (`segment_worker.py`) | backend `heal` path | `POST /runs/{run_id}/heal` respawns workers; segments reconcile from checkpoint; completed rows are canonical and never re-lost | `GET /classify/status/{run_id}`, worker processes |
| JEV decision service (:8770) | **launchd** `com.jev.decision-service` (KeepAlive, RunAtLoad) | automatic respawn (verified: SIGKILL → healthy in <15 s) | `curl http://127.0.0.1:8770/health` |
| JEV retrain cadence (every 6 h) | **launchd** `com.jev.retrain` (StartInterval 21600) | next scheduled run; wrapper holds a lock so runs never overlap | `launchctl list \| grep jev`, `reports/retrain.log` |
| Ollama | macOS system service | `ollama serve` if down; models re-download-free | `ollama ps` |
| Production run itself | backend + heal path | a failed segment is isolated (never fails the queue); heal requeues only failed segments; rows are committed per row | `progress.json`, segment states |

## Failure-proofing guarantees in place

- **JEV judge falls back to llama3.1 automatically** on any connection failure or `abstained` verdict;
  opposite PASS/FAIL splits route to review — no crash can silently change a verdict.
- **Training cannot corrupt the live model**: promotion gates on the fixed human test, swaps the
  `jev-active` symlink atomically, and restarts the service; during the seconds-long gap the SPOT judge
  falls back to llama3.1.
- **The retraining wrapper holds a lock**; concurrent or overlapping runs exit immediately.
- **Ollama lane residency** is per-model (`SPOT_OLLAMA_KEEP_ALIVE_MODELS`); small lanes stay loaded,
  large corroboration models release after each call.

## Manual restart drill (only if a supervisor is also down)

```bash
# 1) shell + backend
open -a /Applications/spot.app
# 2) run
curl -s -X POST http://127.0.0.1:8765/runs/<run_id>/heal -H 'Content-Type: application/json' -d '{}'
# 3) JEV
launchctl unload ~/Library/LaunchAgents/com.jev.decision-service.plist
launchctl load ~/Library/LaunchAgents/com.jev.decision-service.plist
# 4) verify
curl http://127.0.0.1:8770/health && curl http://127.0.0.1:8765/api/health
```

## DRY-RUN-only repairs (never part of normal recovery)

- Purging a run: `purge_run_state` — destroys segments; re-intake afterwards.
- Killing orphan workers: `pkill -f "segment_worker.py --run-id <id>"` after `kill -CONT` (a SIGSTOPped
  worker ignores TERM; CONT first, then KILL, then heal).
