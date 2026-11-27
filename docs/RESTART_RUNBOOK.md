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


## Memory ceiling (learned 2026-11-19)

The primary lane holds an 8B 4-bit model per segment child (~8 GB GPU). **Two workers is the ceiling** on
this 32 GB machine: a 3-worker experiment drove ~20 GB into swap, collapsed throughput from ~7 s/row to
>100 s/row, and left the machine degraded until reboot (macOS does not drain stale swap while the system
runs). More workers require a smaller resident primary (the trained small-model direction), not a config
change. `SPOT_PARALLEL_WORKERS` stays at 2 by default.

## Reboot recovery (fully automatic)

1. **launchd `RunAtLoad`** restarts the JEV service, the retrainer cadence, the swap watchdog, and
   `com.spot.app` opens the app shell at login - no manual step.
2. The app auto-resumes the interrupted run; if it does not, `POST /runs/{run_id}/heal`.
3. Verify: `/api/health`, `/runs/{id}/sla`, `curl 127.0.0.1:8770/health`, `launchctl list | grep -E "jev|spot"`.

## Swap can never silently return

- **Hard ceiling:** `SPOT_MAX_PARALLEL_WORKERS=2` (enforced in code, action-logged) - the 8B-primary
  configuration that thrashed cannot be recreated by any env change.
- **Watchdog:** `com.spot.swapwatch` logs swap every 15 minutes; above 12 GB WARNING, above 20 GB
  CRITICAL with the memory leaders captured. It never kills anything.
- **Permanent fix path:** a smaller resident primary (the trained 1.5-2B adapter experiment) is the only
  change that raises the worker ceiling - recorded here so the trade stays explicit.


## Nightly reboot (01:00 GMT window)

- LaunchDaemon `com.spot.nightly-reboot` runs `script/nightly_reboot.sh` hourly; the script reboots only
  when the UTC hour is 01 (timezone/DST safe) and logs to `/Library/Logs/spot-nightly-reboot.log`.
- `--force` is the operator test path; it requires the one-time sudoers grant installed by
  `script/install_reboot_job.sh` (grants ONLY that script, nothing else).
- After every reboot: launchd restarts the JEV service, retrainer and swap watchdog; `com.spot.app` opens
  the app; the app auto-resumes the interrupted run (else `POST /runs/{run_id}/heal`).


## Post-reboot gaps fixed 2026-11-27 (the first real reboot)

The first reboot exposed the two remaining gaps:

1. **Auto-login was off** - the Mac sat at the login screen, so NO user LaunchAgent ran (JEV, retrainer,
   watchdog, spot.app, the harness). Enable it once in System Settings > Users & Groups > Login Options >
   "Automatically log in as: chappie" (password required once; with FileVault the option may be hidden -
   disable FileVault first if auto-login must work). Nothing user-level can run before login; this is the
   one setting the whole automatic recovery depends on.
2. **DeepSeek Harness had no supervisor.** `com.dsh.web` (KeepAlive, RunAtLoad) now starts
   `dsh web --patch .../ollama.cordis.yml`. It is staged but intentionally NOT loaded while a live
   instance owns port 3080 - it takes over from the next login/reboot.

Verified after the reboot: swap 25 GB -> 301 MB, throughput restored, JEV/backend/workers/app all
self-recovered, the run auto-resumed (31,826 rows), and the nightly-reboot daemon remained armed.


## Harness supervisor loaded (2026-11-27)

com.dsh.web is now LOADED (not just staged) with an idempotent port guard: while a live instance owns
port 3080 the guard exits 1 and launchd retries; after a reboot the port is free and the guard execs the
real harness. The guard script lives at /Users/Shared/Projects/settings/bin/dsh-web-guard.sh.

**The single remaining human dependency is auto-login** (System Settings > Users & Groups > Login
Options > Automatically log in as chappie). Without it every reboot stops at the login screen and no user
agent runs until a manual login - verified as NOT set on 2026-11-27.


## Second reboot lesson (2026-11-27): Ollama was the hidden dependency

The second reboot exposed that the app's preflight hard-fails when Ollama is absent
(ollama_listener check) - the backend refuses to start, so the run stays INTERRUPTED until Ollama returns.
Ollama was not supervised; it is now: com.ollama.serve (KeepAlive + port guard, same pattern as the
harness) execs `ollama serve` at boot when port 11434 is free. Auto-login remains the human gate;
script/enable_autologin.sh sets it from the CLI (FileVault must be off), the System Settings GUI path is
authoritative. Recovery order after a boot: login -> ollama serve (launchd) -> com.dsh.web harness ->
JEV/retrainer/watchdog -> com.spot.app -> backend preflight passes -> run auto-resumes (else heal).
