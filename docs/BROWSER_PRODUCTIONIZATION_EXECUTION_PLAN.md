# {spot} Browser Productionization Execution Plan

Primary contract:
- [`docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md`](/Users/moldovancsaba/Projects/spot/docs/BROWSER_PRODUCTIONIZATION_CONTRACT.md)

Board SSOT:
- GitHub Project `{spot}` items `#12` through `#16`

## Execution Order

1. `#12` browser phase release readiness contract
2. `#13` automated API and browser operator smoke coverage
3. `#15` browser appliance packaging and startup path
4. `#14` browser acceptance evidence and release candidate package
5. `#16` browser baseline release cutover and post-release handover

## Deliverable Units

### `#12` Contract

- publish productionization contract
- define browser release DoD
- define verification, packaging, evidence, and cutover boundaries

Exit condition:
- repo contract is published and linked from project management docs

### `#13` Automated Smoke Coverage

- add deterministic smoke script for browser operator surfaces
- cover auth, upload intake, run detail, review, artifacts, sign-off, and recovery seams
- document the verification command

Exit condition:
- one in-repo command verifies the browser surface on a delivery machine

### `#15` Packaging And Startup

- define one supported browser startup path
- align runbook and client package docs with that path
- ensure browser-enabled launch is treated as delivery truth

Exit condition:
- appliance operator has a single documented browser launch path

### `#14` Acceptance Evidence

- update benchmark/UAT evidence for browser workflow proof
- align checklists with browser-enabled appliance operation
- capture release-candidate evidence

Exit condition:
- browser baseline has explicit acceptance evidence, not only implementation notes

### `#16` Release Cutover

- prepare release notes and release draft
- finalize handover with exact cutover status
- capture remaining known limits

Exit condition:
- browser baseline can be reviewed as a shippable increment

## Current Status

- `#12` contract: implemented
- `#13` automated browser smoke: implemented
- `#15` startup path and packaging docs: implemented
- `#14` browser-aware evidence templates/checklists: implemented
- `#16` release cutover and fresh live acceptance evidence: remaining
