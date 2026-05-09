# {spot} Project Management Notes

## Functional SSOT

The functional and technical single source of truth inside this repository is:
- [`ssot/SSOT.md`](/Users/moldovancsaba/Projects/spot/ssot/SSOT.md)
- [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json)

## Documentation Hierarchy

1. SSOT files define product/runtime truth.
2. Architecture/foundation docs explain implementation of that truth.
3. Monitoring and README docs explain operations.
4. Historical release notes describe previously shipped states only.

## Active Product Contract

The active operator baseline is the native macOS workspace plus its supervised local runtime contract.

Browser-phase planning documents remain historical records and are no longer the active implementation contract.

## Active Productionization Contract

The active implementation contract for the next milestone is the native-only hardening and release cutover tracked in the current repo baseline.

## Current Implementation Status

- Core runtime: implemented
- Native macOS supervisor baseline: implemented
- Queue-backed local operations dashboard: implemented
- Native-only delivery baseline: in progress
- Live client acceptance on the native-only baseline: pending
- Current remaining milestone focus: foundation hardening, DB-centered execution migration, release cutover, and post-release handover
