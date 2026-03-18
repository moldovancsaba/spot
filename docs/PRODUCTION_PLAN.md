# {spot} Production Plan

Current workspace implementation baseline: `0.4.0`
SSOT baseline: `0.2`
Document date: `2026-03-18`

## Objective

Deliver {spot} as a local, offline, single-node production system for high-confidence antisemitism classification from `.xlsx` files, with Apertus on MLX as the primary classifier route and deterministic Ollama fallback.

## Production Scope

In scope:
- local/offline `.xlsx` ingestion
- row-level antisemitism classification
- deterministic review and fallback behavior
- monitoring and process control
- audit artifacts suitable for client review and regulatory escalation

Out of scope:
- OCR
- scanned documents
- media analysis
- auto language detection
- taxonomy/schema editing in production

## Deployment Target

Single-node Apple Silicon deployment.

Functional target:
- primary classifier: `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`
- classifier fallback: `ollama://qwen2.5:7b`
- drafter: `ollama://granite4:350m`
- drafter fallbacks: `ollama://gemma3:1b`, `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`
- local API/UI on loopback
- local artifact storage in `runs/`

## Recommended Hardware Baseline

Operational recommendation:
- Apple Silicon Mac mini class machine
- 64GB unified memory target
- 2TB SSD target minimum
- external backup SSD
- UPS

Reasoning:
- Apertus on MLX benefits more from memory headroom than from peripheral scale-out in this single-node design.
- {spot} keeps local run artifacts and benchmark outputs, so storage headroom is required.

## Delivery Workstreams

### 1. Runtime Hardening

Goal:
- stable MLX primary path
- deterministic fallback path
- secure local-only defaults

Outputs:
- validated MLX classifier route
- validated fallback route
- clean policy/integrity reporting
- artifact manifest with file hashes
- disagreement report for ensemble disagreement paths

### 2. Data Contract Hardening

Goal:
- predictable `.xlsx` ingestion
- explicit schema rejection
- reliable output metadata for every row

Outputs:
- input validation checklist
- sample client import pack
- reviewed output workbook contract

### 3. Model Calibration

Goal:
- benchmark Apertus primary classifier against agreed evaluation set
- tune low-confidence handling and review threshold behavior

Outputs:
- benchmark run package
- confusion analysis
- review-threshold recommendation

### 4. Operations Package

Goal:
- make {spot} operable by non-developers on a client machine

Outputs:
- startup/shutdown procedure
- monitoring usage guide
- runbook for failed runs and fallback events
- backup and export procedure

### 5. Client Acceptance

Goal:
- prove production-readiness against agreed acceptance data

Outputs:
- acceptance evidence package
- approved production cutover checklist

## Suggested Phase Plan

### Phase A: Machine Bring-up

Tasks:
- provision Mac mini
- install {spot} runtime
- validate MLX/Apertus availability
- validate local storage and backup path

Exit gate:
- local smoke run completes with SSOT-aligned artifacts

### Phase B: Benchmark and Threshold Calibration

Tasks:
- run controlled evaluation set
- review false positives / false negatives
- confirm review-mode policy

Exit gate:
- approved confidence/review posture

### Phase C: Operational Packaging

Tasks:
- harden service start procedure
- verify monitoring flows
- verify operator instructions

Exit gate:
- operator can run {spot} without engineering intervention

### Phase D: Client UAT

Tasks:
- run client-owned representative dataset
- review flagged rows
- sign off output format and confidence behavior

Exit gate:
- signed UAT and go-live approval

## Quality Gates

Production is not ready until all are true:
- SSOT loads without exceptions
- code compiles cleanly
- supported browser startup path works on the target machine
- browser smoke passes as integration verification
- MLX primary route completes a real classification run
- output workbook contains current model/prompt/SSOT/pipeline metadata
- fallback behavior is deterministic and flagged
- artifact manifest is produced for completed runs
- client acceptance dataset reviewed

Current status:
- the runtime and browser operator workflow are implemented
- the current repo still requires fresh live client-machine acceptance evidence and release cutover before first delivery

## Deliverables To Client

- {spot} runtime package
- SSOT package
- local appliance runbook
- operator guide
- monitoring guide
- acceptance evidence pack
- benchmark summary
- risk register and support model

## Commercial Model

Sentinel Squad uses a Value Credit model instead of hourly or daily billing.

Value Credit pricing:
- 1 credit = `$100`
- monthly product and management component = `$2,500`

Credit sizing baseline:
- small improvement = `1` credit
- minor feature = `2` credits
- standard feature = `3` credits
- larger module = `5` credits
- major or strategic feature = `8` credits

## Recommended {spot} Delivery Packaging

### Package 1: Production Bring-up

Scope:
- runtime hardening
- secure local defaults
- machine bring-up
- smoke validation

Estimated size:
- `8` credits
- cost = `$800`

### Package 2: Calibration and Acceptance

Scope:
- benchmark run package
- threshold review
- client representative dataset validation
- acceptance evidence pack

Estimated size:
- `8` credits
- cost = `$800`

### Package 3: Operational Enablement

Scope:
- operator guide
- monitoring and failure handling walkthrough
- backup and export procedure

Estimated size:
- `5` credits
- cost = `$500`

## Base Delivery Calculation

One-time delivery:
- `21` credits total
- `$2,100` one-time implementation value

Monthly product and management:
- `$2,500 / month`

Hardware:
- separate client-paid infrastructure line item

## Client Quote Structure

Recommended quote structure:
- one-time Sentinel Squad delivery: `$2,100`
- monthly product and management: `$2,500`
- hardware and accessories: pass-through or separately quoted

## Risk Register

### MLX runtime availability
Mitigation:
- verify local model availability during machine bring-up
- retain deterministic Ollama fallback

### Low-confidence row volume too high
Mitigation:
- benchmark calibration before go-live
- tune review policy against real client examples

### Input schema drift
Mitigation:
- enforce sample schema contract
- provide client import checklist

### Single-node operational failure
Mitigation:
- local backup strategy
- exportable run artifacts
- documented restart/recovery procedure
