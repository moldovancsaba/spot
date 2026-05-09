# {spot} Native App Scaffold Spec

Historical note:
- this scaffold spec was written during the first native-shell bring-up phase
- references to browser startup paths below are historical implementation context, not the current delivery contract

Document date: `2026-05-05`
Target baseline: `0.5.0`

## Purpose

This document is the implementation scaffold for a native macOS `{spot}` app.

It translates the learned `{reply}` native-app pattern into a concrete `{spot}` file-by-file plan without changing `{spot}` product boundaries.

The native app must be:

- a thin native shell
- local-first
- audit-safe
- loopback-only for the bundled backend
- explicit about build, install, and launch contracts

It must not rewrite the existing Python classification runtime into Swift.

## Security Position

This plan can be hardened materially, but it cannot be guaranteed "100% secure".

For `{spot}`, the correct standard is:

- explicit trust boundaries
- secure-by-default local behavior
- minimal privilege
- deterministic validation
- no silent fallback to weaker behavior

Every native-app implementation step must preserve the repo's existing security posture:

- loopback-first backend
- loopback-only Ollama by default
- locked SSOT support
- local-first artifacts
- explicit operator authentication

## Native App Boundary

`spot.app` is the operator-facing shell around the existing `{spot}` local appliance runtime.

Stage 1 scope:

- native launch and stop controls
- preflight visibility
- runtime health visibility
- current run visibility
- review-workspace entrypoint
- artifacts/logs entrypoints

Stage 1 non-goals:

- reimplementing the browser review UI in SwiftUI
- moving classification logic into Swift
- changing the SSOT or audit model
- broadening `{spot}` beyond the current `.xlsx` contract

Stage 1 security non-goals:

- exposing the backend on non-loopback interfaces
- embedding secrets in the app bundle
- weakening local auth just to simplify native launch
- bypassing production-mode or locked-SSOT constraints
- allowing arbitrary external runtime roots at launch time

## Required Files

Create these files:

- `/Users/moldovancsaba/Projects/spot/app/macos/Package.swift`
- `/Users/moldovancsaba/Projects/spot/app/macos/Info.plist`
- `/Users/moldovancsaba/Projects/spot/app/macos/build-icon.sh`
- `/Users/moldovancsaba/Projects/spot/app/macos/build-bundle.sh`
- `/Users/moldovancsaba/Projects/spot/app/macos/install-bundle.sh`
- `/Users/moldovancsaba/Projects/spot/script/build_and_run.sh`
- `/Users/moldovancsaba/Projects/spot/app/macos/Sources/SpotApp.swift`
- `/Users/moldovancsaba/Projects/spot/app/macos/Sources/SpotCoreService.swift`
- `/Users/moldovancsaba/Projects/spot/docs/NATIVE_APP_BUILD_HANDOFF.md`

Optional helper:

- `/Users/moldovancsaba/Projects/spot/app/macos/Sources/SpotHelper/main.swift`

Only add the helper target if the app genuinely needs a protected local helper for file or mirror operations.

## Mandatory Security Constraints

These are non-negotiable implementation rules for `spot.app`:

1. The bundled backend must bind to `127.0.0.1` only by default.
2. The native shell must not disable `{spot}` auth by default.
3. The native shell must not ship a hard-coded production access code in source control as the final production answer.
4. The app bundle must not contain operator data, prior run artifacts, logs, `.env` files, or mutable secrets.
5. The native shell must not allow arbitrary SSOT replacement in production-mode launch.
6. The native shell must not silently permit remote Ollama endpoints unless the underlying runtime is explicitly configured to allow them.
7. The install path must remain full-bundle verified replacement only.
8. The runtime must write to operator-local writable directories, never inside the installed app bundle.
9. Native launch verification must fail closed when preflight or runtime readiness fails.
10. The native shell must treat browser review/auth surfaces as protected operator UI, not public local web pages.

## Directory Shape

Expected phase-1 directory layout:

```text
app/
  macos/
    Package.swift
    Info.plist
    build-icon.sh
    build-bundle.sh
    install-bundle.sh
    Scripts/
      generate_app_icon.swift
    Sources/
      SpotApp.swift
      SpotCoreService.swift
      SpotModels.swift
      SpotViews/
        SpotWorkspaceView.swift
        SpotControlCenterView.swift
        SpotSettingsView.swift
```

Minimal implementation may start without `SpotModels.swift` or `SpotViews/`, but that is the preferred shape.

## File Spec

### `Package.swift`

Purpose:

- define the native package
- pin Swift toolchain and platform floor
- define executable targets

Required contract:

- `swift-tools-version: 6.0`
- `platforms: [.macOS(.v15)]`
- main product executable name: `spot`

Recommended first target structure:

- executable target `spotshell`
- optional executable target `spothelper`

Starter structure:

- package name: `spot-macos`
- product `spot`
- optional product `spot-helper`

Do not add third-party Swift dependencies in phase 1 unless a real need appears.

Security requirements:

- no unnecessary networking libraries
- no embedded update/downloader logic in phase 1
- no dependency that broadens the trust boundary without a documented reason

### `Info.plist`

Purpose:

- define bundle metadata

Required values:

- `CFBundleIdentifier = com.spot.desktop`
- `CFBundleExecutable = spot`
- `CFBundleName = spot`
- `CFBundleDisplayName = spot`
- `CFBundleIconFile = spot`
- `CFBundlePackageType = APPL`
- `LSMinimumSystemVersion = 15.0`

Version fields should align with active `{spot}` versioning policy.

Security requirements:

- no entitlements should be added unless a specific local capability requires them
- do not request broader sandbox or Apple permissions speculatively
- document every entitlement before adding it

### `build-icon.sh`

Purpose:

- generate `spot.icns` deterministically during bundle assembly

Required behavior:

1. resolve project dir
2. generate a 1024 base icon
3. derive iconset sizes
4. compile `.icns` with `iconutil`

Do not depend on manual Finder-generated icons.

### `build-bundle.sh`

Purpose:

- canonical bundle assembly path

Required behavior:

1. resolve `PROJECT_DIR` and `{spot}` repo root
2. run `swift build`
3. run `build-icon.sh`
4. recreate `dist/spot.app`
5. copy native executable to `Contents/MacOS/spot`
6. copy helper if present
7. copy runtime assets into `Contents/Resources/spot-core/`
8. copy `Info.plist`
9. copy `spot.icns`
10. write `Contents/PkgInfo`
11. attempt ad hoc codesign

Required bundled runtime content in phase 1:

- `backend/`
- `src/`
- `ssot/`
- `requirements.txt`
- `start_browser_appliance.sh`

Bundle only what the runtime needs.

Do not bundle:

- `.venv/`
- `runs/`
- `logs/`
- `.env`
- `.env.*`
- `.git/`
- test caches
- unrelated samples unless the operator app explicitly needs them

Security requirements:

- exclude any local credentials, tokens, caches, databases, and development leftovers from the bundle
- if a file is writable or environment-specific, prefer not bundling it
- if a resource is bundled and mutable, document why

### `install-bundle.sh`

Purpose:

- only accepted install/update path for `/Applications/spot.app`

Required behavior:

1. require `dist/spot.app`
2. verify mandatory bundle paths
3. stage into temp root
4. verify staged bundle
5. stop running app/runtime
6. remove existing `/Applications/spot.app`
7. rsync staged bundle into `/Applications/spot.app`
8. verify installed bundle
9. refresh LaunchServices
10. refresh Dock metadata

Required verification paths:

- `Contents/Info.plist`
- `Contents/MacOS/spot`
- `Contents/Resources/spot.icns`
- `Contents/Resources/spot-core`

If a helper is adopted:

- `Contents/Helpers/spot-helper`

Security requirements:

- verify `CFBundleExecutable == spot`
- verify `CFBundleIconFile == spot`
- reject installation if unexpected helper or runtime paths are present
- reject installation if required resources are missing

### `script/build_and_run.sh`

Purpose:

- developer build-and-launch wrapper

Required behavior:

1. stop previous native app process if present
2. stop previous bundled backend process if present
3. build bundle via `app/macos/build-bundle.sh`
4. open built bundle with `open -n`
5. if `--verify`, poll runtime health

Preferred verification target:

- `http://127.0.0.1:8765/`

Preferred health contract:

- add a dedicated `/api/health` later if needed
- phase 1 may validate via a stable lightweight route if that is what `{spot}` already exposes

Verification must be readiness-based, not process-based.

Security requirements:

- `--verify` must fail if preflight reports blocking errors
- `--verify` must fail if the backend responds on a non-loopback host expectation
- `--verify` must fail if the app exits before readiness

### `SpotApp.swift`

Purpose:

- native app entrypoint
- own the high-level windows and commands

Required app responsibilities:

- create `SpotCoreService`
- start monitoring on launch
- expose workspace window
- expose control center or status window
- expose settings window

Required commands:

- show workspace
- refresh status
- launch runtime
- restart runtime
- stop runtime
- open logs
- open runs/artifacts directory

### `SpotCoreService.swift`

Purpose:

- runtime supervisor for bundled `{spot}`

Required published state:

- runtime state
- base URL
- last health refresh time
- launch error message
- preflight summary
- selected run id
- active run summary
- pending review count
- log lines

Required methods:

- `startMonitoring()`
- `refreshHealth() async`
- `launchSpot()`
- `restartSpot()`
- `stopSpot()`
- `runPreflight() async`
- `openBrowserWorkspace()`
- `openReviewWorkspace(runID: String)`
- `openLogs()`
- `openRunsDirectory()`
- `openArtifactsDirectory(runID: String)`

Required security-related methods:

- `validatePreflightSecurity() async`
- `validateLaunchConfiguration() throws`
- `resolveLockedSSOTPath() throws`
- `validateWritablePaths() throws`
- `validateLoopbackBaseURL(_:)`
- `redactSensitiveLogLine(_:)`

Required internal helpers:

- `resolveRuntimeRoot()`
- `resolveBundledLauncher()`
- `detectReachableRuntime() async`
- `isRuntimeReady(_:)`
- `appendLog(_:)`
- `bundledCoreRootURL()`
- `spotDataHome`
- `spotLogHome`

Required environment contract for launch:

- loopback bind only
- `SPOT_RUN_PREFLIGHT=1` by default
- `SPOT_PRODUCTION_MODE=1` only if the native app is explicitly production-mode
- `SPOT_LOCKED_SSOT_PATH` when using a locked bundled SSOT
- writable `RUNS_DIR`
- writable logs path

Recommended phase-1 environment contract additions:

- `SPOT_AUTH_ENABLED=1`
- `SPOT_LOCAL_ACCESS_CODE` sourced from operator environment or first-run setup, not hard-coded into the shipped bundle

Security rules for launch:

- never set `SPOT_AUTH_ENABLED=0` in the native app's default launch path
- never auto-enable remote runtime allowances
- never point `RUNS_DIR` or logs inside `/Applications/spot.app`
- never launch with an unlocked arbitrary SSOT in explicit production mode

Phase 1 launch strategy should prefer wrapping the existing supported entrypoint:

- `bash start_browser_appliance.sh`

That keeps the native app aligned with current repo-supported runtime behavior.

## Runtime Packaging Strategy

Phase 1 should not attempt to invent a fully self-contained Python distribution unless there is a hard requirement.

Use this staged approach:

1. native shell bundles `{spot}` runtime assets
2. native shell expects a valid local Python environment contract
3. native shell runs preflight and shows failures clearly
4. only later consider bundling Python if operator deployment requires it

This is the fastest path that stays truthful to the current repo.

Security note:

Bundling Python should be treated as a later hardening step, not a shortcut.

Phase 1 is safer if the runtime prerequisites remain explicit and preflight-validated, rather than hiding an opaque embedded interpreter contract prematurely.

## Operator-Local Paths

Preferred phase-1 local writable paths:

- data root: `~/Library/Application Support/spot`
- logs root: `~/Library/Logs/spot`
- runs root: `~/Library/Application Support/spot/runs`

The native shell should not write audit artifacts inside the app bundle.

Security rules for writable paths:

- create directories with restrictive permissions
- fail clearly if permissions are broader than expected in production-mode flows
- never downgrade to world-writable paths as a fallback

## UI Surface Spec

### Workspace window

Must show:

- runtime state
- last health refresh
- preflight status
- active run id
- active run state
- processed rows
- total rows
- pending review rows

Actions:

- launch
- restart
- stop
- open browser workspace
- open review page for active run

### Settings window

Phase 1 should remain operational, not decorative.

Show:

- SSOT path
- runs directory
- logs directory
- port
- production mode state

The settings shell can be read-mostly in phase 1.

Sensitive values such as access codes or future tokens must never be rendered back in plaintext once saved.

### Control center window

Show:

- runtime log tail
- validation/preflight messages
- quick links to logs and artifacts

## Exact Implementation Order

1. create `app/macos/Package.swift`
2. create `app/macos/Info.plist`
3. create `app/macos/Sources/SpotApp.swift`
4. create `app/macos/Sources/SpotCoreService.swift`
5. create `app/macos/build-icon.sh`
6. create `app/macos/build-bundle.sh`
7. create `app/macos/install-bundle.sh`
8. create `script/build_and_run.sh`
9. create `docs/NATIVE_APP_BUILD_HANDOFF.md`
10. add validation notes to active docs once the scaffold exists

Do not start by porting the browser review UI into SwiftUI.

## Native Security Checklist

The scaffold is not ready to implement until each item below has a concrete owner:

- define where `SPOT_LOCAL_ACCESS_CODE` comes from for native launches
- define whether phase 1 uses a bundled SSOT copy or an operator-provided locked path
- define exact app-support and log directories
- define whether any helper binary is truly needed
- define the phase-1 health endpoint contract
- define which runtime files are bundled and which are explicitly excluded
- define what the app does when preflight passes with warnings but not errors

## Forbidden Shortcuts

Do not use these implementation shortcuts:

- launching uvicorn directly with a broad host bind
- disabling auth to simplify local navigation
- storing access codes in checked-in plist or Swift source
- copying the whole repo into the bundle blindly
- writing runs or logs into the bundle
- using Finder drag-and-drop as the install story
- claiming security based on process existence rather than verified health and config

## Validation Gates

Required syntax validation once scaffold files exist:

```bash
cd /Users/moldovancsaba/Projects/spot/app/macos
swift package dump-package >/dev/null
bash -n ./build-icon.sh
bash -n ./build-bundle.sh
bash -n ./install-bundle.sh
plutil -lint ./Info.plist
```

```bash
cd /Users/moldovancsaba/Projects/spot
bash -n ./script/build_and_run.sh
```

Required runtime validation after first implementation:

- bundle builds successfully
- native app launches
- bundled runtime reaches loopback readiness
- browser workspace opens from the native shell
- review workspace opens from the native shell
- logs and runs directory open correctly
- stop/restart behavior is deterministic

Required security validation after first implementation:

- native launch fails closed when preflight has blocking errors
- backend health resolves only on loopback
- production-mode launch uses a locked SSOT path
- auth remains enabled in the native launch path
- remote Ollama remains blocked by default
- writable app-support and log paths are outside the bundle
- bundle contents contain no `.env`, prior run data, or local logs
- install verification rejects malformed or partial bundles
- sensitive values are redacted from operator-visible logs where appropriate

## Non-Negotiable Rules

- preserve `{spot}` branding exactly as written
- preserve local-first execution
- preserve audit artifacts and run retention
- preserve SSOT authority
- preserve loopback-only backend binding by default
- preserve auth-enabled local operator access by default
- preserve remote-runtime denial by default
- do not broaden `{spot}` product scope while building the native shell
