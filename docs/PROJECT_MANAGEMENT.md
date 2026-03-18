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

The active browser operator baseline contract is:
- [`docs/BROWSER_OPERATOR_CONTRACT.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_OPERATOR_CONTRACT.md)

This document is the repo-side implementation contract for GitHub issue `#1` and the `{spot} v0.4.0 Browser Contract & Foundations` milestone.

Execution breakdown for the active phase:
- [`docs/BROWSER_PHASE_EXECUTION_PLAN.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_PHASE_EXECUTION_PLAN.md)

## Active Productionization Contract

The active implementation contract for the next milestone is:
- [`docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md)

This document is the repo-side implementation contract for GitHub issue `#12` and the `{spot} v0.4.3 Browser Productionization` milestone.

Execution breakdown for the current active milestone:
- [`docs/BROWSER_PRODUCTIONIZATION_EXECUTION_PLAN.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_PRODUCTIONIZATION_EXECUTION_PLAN.md)

## Current Implementation Status

- Core runtime: implemented
- Browser operator baseline: implemented
- Browser productionization verification: implemented as deterministic smoke plus startup contract
- Live client acceptance on the browser-enabled baseline: pending
- Current remaining milestone focus: release cutover and post-release handover
