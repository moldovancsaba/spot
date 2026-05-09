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
