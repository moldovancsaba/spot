# {spot} Native App Build Handoff

This document is the exact handoff path for how `{spot}` builds and ships its native macOS app scaffold.

Use it when another agent needs the native app boundary without reverse-engineering the repo.

## Canonical Path

- document: `/Users/moldovancsaba/Projects/spot/docs/NATIVE_APP_BUILD_HANDOFF.md`
- app root: `/Users/moldovancsaba/Projects/spot/app/spot-app`
- packaged bundle output: `/Users/moldovancsaba/Projects/spot/app/spot-app/dist/spot.app`
- installed app target: `/Applications/spot.app`

## What The Native App Is

`spot.app` is a native macOS shell built with `SwiftUI`.

It is not the full product runtime by itself.

The app bundle contains and launches:

1. a native executable shell
2. a bundled `{spot}` runtime snapshot
3. a bundled launcher script for the local appliance runtime
4. generated icon and bundle metadata

The native shell is the operator-facing entrypoint. The Python classification runtime remains the runtime authority behind it.

## Source Of Truth Files

These files define the native app build and launch contract:

- package manifest: `/Users/moldovancsaba/Projects/spot/app/spot-app/Package.swift`
- app metadata: `/Users/moldovancsaba/Projects/spot/app/spot-app/Info.plist`
- icon build script: `/Users/moldovancsaba/Projects/spot/app/spot-app/build-icon.sh`
- bundle build script: `/Users/moldovancsaba/Projects/spot/app/spot-app/build-bundle.sh`
- bundle install script: `/Users/moldovancsaba/Projects/spot/app/spot-app/install-bundle.sh`
- dev build-and-launch script: `/Users/moldovancsaba/Projects/spot/script/build_and_run.sh`
- app entrypoint: `/Users/moldovancsaba/Projects/spot/app/spot-app/Sources/SpotApp.swift`
- runtime supervisor and health probing: `/Users/moldovancsaba/Projects/spot/app/spot-app/Sources/SpotCoreService.swift`

If any of those files change, this document must be reviewed.

## Build Contract

### Platform contract

- toolchain: `Swift 6`
- package platform: `macOS 15`
- bundle minimum system version: `15.0`
- bundle identifier: `com.spot.desktop`
- bundle executable: `spot`
- bundle icon file key: `spot`

### Swift package targets

The native workspace currently builds one executable:

- `spot`

### Bundle assembly

`app/spot-app/build-bundle.sh` is the canonical bundle assembly script.

It performs these steps in order:

1. resolve `PROJECT_DIR` and `REPO_ROOT`
2. run `swift build`
3. generate the icon by calling `build-icon.sh`
4. recreate `dist/spot.app`
5. copy the native executable into `Contents/MacOS/spot`
6. rsync `backend/` into `Contents/Resources/spot-core/backend/`
7. rsync `src/` into `Contents/Resources/spot-core/src/`
8. rsync `ssot/` into `Contents/Resources/spot-core/ssot/`
9. copy `requirements.txt`
10. generate `Contents/Resources/spot-core/bin/launch-bundled-appliance.sh`
11. copy `Info.plist`
12. copy `spot.icns`
13. write `Contents/PkgInfo`
14. attempt ad hoc codesign

### Build-time path assumptions

The bundle builder assumes:

- the `{spot}` repo root is two levels above `app/spot-app`
- the runtime assets live in the same repo
- Python is not bundled in phase 1

### Runtime configuration contract

The bundled launcher expects runtime configuration in:

- `~/Library/Application Support/spot/native-runtime.env`

The native shell now creates a template for this file on first run if it is missing.

The dev wrapper also writes this file directly before launch.

Key values:

- `SPOT_NATIVE_PYTHON_BIN`
- `SPOT_NATIVE_RUNS_DIR`
- `SPOT_NATIVE_LOGS_DIR`
- `SPOT_LOCKED_SSOT_PATH`
- `SPOT_NATIVE_PORT`
- `SPOT_NATIVE_INTAKE_WATCH_DIR`
- `SPOT_NATIVE_INTAKE_ARCHIVE_DIR`
- `SPOT_NATIVE_INTAKE_FAILED_DIR`
- `SPOT_NATIVE_AUTO_START_WATCH_FOLDER`
- `SPOT_LOCAL_ACCESS_CODE`

The native app and `script/build_and_run.sh` both rely on that config file.

Expected permissions:

- config directory: `0700`
- runs directory: `0700`
- logs directory: `0700`
- native runtime config file: `0600`

## Install Contract

`app/spot-app/install-bundle.sh` is the only accepted install or update path for `/Applications/spot.app`.

The install script enforces this sequence:

1. require `dist/spot.app` to exist
2. verify required bundle contents before install
3. rsync to a staging bundle
4. verify the staged bundle again
5. stop running app and related runtime processes
6. remove any existing `/Applications/spot.app`
7. rsync the staged bundle into `/Applications/spot.app`
8. verify the installed bundle again
9. refresh LaunchServices registration
10. restart Dock metadata handling

### Required bundle paths

- `Contents/Info.plist`
- `Contents/MacOS/spot`
- `Contents/Resources/spot.icns`
- `Contents/Resources/spot-core`
- `Contents/Resources/spot-core/bin/launch-bundled-appliance.sh`

## Launch Contract

For local development, `script/build_and_run.sh` is the native app launch wrapper.

It does four important things beyond just opening the app:

1. kills previous native and bundled backend processes
2. writes `~/Library/Application Support/spot/native-runtime.env`
3. tightens local permissions on config and writable runtime directories
4. builds the bundle by calling `app/spot-app/build-bundle.sh`
5. opens the generated bundle with `open -n`

If called with `--verify`, it also:

1. probes `http://127.0.0.1:8765/api/health`
2. waits for readiness
3. fails if the native process exits before readiness is confirmed

## Runtime Ownership

The native app entrypoint lives in `app/spot-app/Sources/SpotApp.swift`.

The app creates a `SpotCoreService`, starts monitoring immediately, refreshes health on launch, and exposes workspace and control-center surfaces.

`SpotCoreService` currently owns:

- health polling
- runtime state tracking
- preflight/security validation
- native launch, restart, stop, and termination behavior
- graceful supervisor suspend before runtime shutdown
- automatic recovery of interrupted resumable runs after native restart
- native config loading
- log capture
- watched-folder intake and automatic run start
- inbox-activity persistence at `~/Library/Application Support/spot/inbox-activity.json`
- native workspace entrypoints

## Current Operational Truth

The native app currently runs in native local mode with local auth disabled by launch environment.

The dashboard does not rely only on the backend summary endpoints. It also falls back to:

- local `run_record.json` files under the configured runs directory
- local `upload.json` files under `runs/uploads/`
- local inbox activity history

This fallback exists so the native dashboard can still show run and intake state when a heavy workbook makes one backend route slow or unavailable.

The backend summary routes were also hardened so `/runs` no longer rescans `output.xlsx` for every run refresh. Workbook review synchronization is restricted to review-specific endpoints.

The preferred bundled runtime port is:

- `8765`

The preferred bundled health probe is:

- `GET /api/health`

## Exact Commands

### Build only

```bash
cd /Users/moldovancsaba/Projects/spot/app/spot-app
./build-bundle.sh
```

### Install into `/Applications`

```bash
cd /Users/moldovancsaba/Projects/spot/app/spot-app
./install-bundle.sh
```

### Build and launch for development

```bash
cd /Users/moldovancsaba/Projects/spot
bash ./script/build_and_run.sh --verify
```

## Validation Checklist

```bash
cd /Users/moldovancsaba/Projects/spot/app/spot-app
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
