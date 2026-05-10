# {spot} Native macOS App

This directory contains the native macOS application source for `{spot}`.

Structure:
- `Package.swift`: SwiftPM package manifest for the native shell
- `Info.plist`: app bundle metadata and version markers
- `Sources/`: SwiftUI application, runtime supervisor, models, and views
- `Scripts/`: source assets used during app packaging
- `build-icon.sh`: local icon generation pipeline
- `build-bundle.sh`: canonical bundle assembly script
- `install-bundle.sh`: canonical `/Applications/spot.app` install/update path

Generated output:
- `.build/`: SwiftPM build cache and temporary compiler output
- `dist/`: locally built `spot.app` bundle

Generated output is disposable and must not be committed.

Supported native maintainer path:
- build bundle: `bash build-bundle.sh`
- install or update `/Applications/spot.app`: `bash install-bundle.sh`
- launch installed app: `open /Applications/spot.app`

Distribution note:
- the repository currently has no declared open-source license file
- this directory documents a source-checkout maintainer workflow, not a public installer or package-manager contract
