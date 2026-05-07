# {spot} Brief

`{spot}` stands for `Smart Platform for Observing Threats`.

Current workspace implementation baseline: `0.4.1`
Pipeline baseline: `mvp-0.4.1`
SSOT baseline: `0.2`
Date: `2026-05-03`

## 1. What {spot} Is

{spot} is a local, offline, deterministic classification system for large Excel batches of social media post text.

Its purpose is to help identify antisemitic and related harmful content at scale with:
- high confidence where possible
- explicit fallback and review handling where confidence is lower
- auditable outputs suitable for internal review and potential legal or regulatory escalation

{spot} is designed to operate on `.xlsx` files only.

## 2. The Main Goal

The main goal of {spot} is to take rows of social media text from Excel files and classify each row into a strict, closed antisemitism taxonomy in a way that is:
- reproducible
- explainable
- deterministic
- operationally defensible
- locally controllable

In plain terms:
- you provide one or more Excel files to the local queue
- {spot} validates each workbook and segments accepted rows into manageable chunks
- {spot} reads each text row
- {spot} assigns exactly one category
- {spot} writes the governed result back into an output Excel file
- {spot} preserves enough evidence to explain what happened later

## 3. What {spot} Is Not

{spot} is not:
- OCR
- document scanning
- image analysis
- video analysis
- URL crawling
- automatic language detection
- multi-label classification
- a system for editing taxonomy or schema in production

This matters because {spot} is intentionally narrow and governed.
It is not trying to solve every moderation or content-understanding problem.

## 4. The Problem {spot} Solves

Manual review of large quantities of social media posts does not scale.
A client may receive thousands of rows in Excel files and need a first-pass system that:
- classifies content consistently
- reduces manual workload
- highlights lower-confidence cases for review
- keeps a strong audit trail

{spot} solves that problem with a closed-set classification pipeline.

## 5. The Taxonomy

{spot} classifies every row into exactly one of the following categories:
- `Anti-Israel`
- `Anti-Judaism`
- `Classical Antisemitism`
- `Structural Antisemitism`
- `Conspiracy Theories`
- `Not Antisemitic`

Important rules:
- no row is allowed to remain uncategorised
- `Not Antisemitic` is the fallback category
- low-confidence or problematic rows are flagged, not hidden

## 6. Input and Output Contract

### Input

{spot} accepts:
- `.xlsx` files only
- one language per run
- first worksheet only

Required first columns:
1. `Item number`
2. `Post text`
3. `Category`

### Output

{spot} writes a new `.xlsx` file and appends governed metadata, including:
- `Assigned Category`
- `Fallback Events`
- `Confidence Score`
- `Explanation / Reasoning`
- `Flags`
- `Model Version`
- `Prompt Version`
- `Taxonomy Version`
- `SSOT Version`
- `Pipeline Version`
- `Run ID`
- `Run Language`
- `Review Mode`
- `Review Required`
- `Row Hash`

## 7. How {spot} Works

The control path is:

`LLM output -> normalization -> validation -> canonical category -> write`

The pipeline is:
1. load and validate SSOT
2. validate input workbook schema
3. read rows from the workbook
4. normalise text through the drafter lane
5. classify through the classifier lane
6. enforce the closed taxonomy
7. apply review policy and flags
8. write governed metadata into the output workbook
9. persist run artefacts for audit

## 8. The 3-Agent System Inside {spot}

{spot} uses three internal roles:
- `drafter`
- `classifier`
- `judge`

### Drafter
Purpose:
- internal preprocessing only
- normalises text
- removes non-semantic noise
- helps prepare text for classification

### Classifier
Purpose:
- final category authority
- assigns exactly one category from the closed taxonomy

### Judge
Purpose:
- disagreement scoring only
- used in ensemble-style quality paths
- not the category authority

Important:
- the standard single-model runtime path does not call the judge for every row
- the standard row path is `drafter -> classifier`
- there is no writer lane in {spot}
- the judge does not override the classifier as the final category authority

## 9. Why Apertus

Apertus is the intended primary classifier because it is the strongest fit for the language capacity and model behaviour required for this project.

The production baseline now treats Apertus as the primary route, not as a side option.

Current primary classifier route:
- `mlx://mlx-community/Apertus-8B-Instruct-2509-4bit`

Fallback classifier route:
- `ollama://qwen2.5:7b`

Support lanes:
- drafter: `ollama://granite4:350m`
- drafter fallbacks: `ollama://gemma3:1b` -> `ollama://llama3.2:1b`
- judge: `ollama://llama3.2:3b`
- judge fallback: `ollama://gemma2:2b`

## 10. Why MLX and Why Local

{spot} is designed for a local/offline operating model because:
- data governance matters
- local control matters
- client data should not need to leave the machine
- the system needs to remain usable without cloud dependencies

MLX is used to run Apertus efficiently on Apple Silicon.
Ollama remains part of the architecture as a deterministic fallback and support runtime.

## 11. Determinism and Governance

{spot} is governed by non-negotiable rules:
- `temperature=0`
- `top_p=1`
- fixed seed
- one category per row
- closed taxonomy only
- fallback on uncertainty or invalid output
- run artefacts persisted for audit

That means {spot} does not blindly trust raw model output.
It always validates, normalises, and enforces the taxonomy before writing the result.

## 12. Confidence and Review

{spot} is not built to pretend certainty.

It supports review modes:
- `full`
- `partial`
- `none`

In `partial` mode:
- low-confidence rows are flagged for review

In `full` mode:
- all processed rows are flagged for review

This allows the system to balance scale with human oversight.

## 13. Security Model

{spot} is local-first and conservative by default.

Current security posture:
- API/UI bind to loopback
- default Ollama URL is loopback only
- remote Ollama is blocked unless explicitly overridden
- no client-data training loop is part of the product
- no cloud dependency is required for normal runtime

## 14. Monitoring and Operations

{spot} provides monitoring and process control through the local backend UI.

Operational capabilities include:
- start classification run
- pause run
- resume run
- stop run
- monitor progress
- inspect run status and artefacts

This makes the system operable beyond simple CLI-only use.

Current implementation stage:
- the core runtime and browser operator surface are implemented
- the browser surface is currently delivered from the FastAPI backend rather than a separate frontend application
- release cutover and fresh client acceptance evidence on the `0.4.1` baseline remain pending

## 15. Audit Artefacts

Each run stores evidence such as:
- `progress.json`
- `integrity_report.json`
- `artifact_manifest.json`
- `policy.json`
- `output.xlsx`
- `logs.txt`
- `disagreement_report.json` for disagreement paths
- `control.json` for monitor-started runs

These artefacts are important because they preserve:
- what was run
- which model route was used
- what policy applied
- what categories and flags were produced
- whether integrity checks passed

## 16. Production Delivery Model

The recommended deployment model is:
- single-node Apple Silicon appliance
- local/offline runtime
- Mac mini class hardware
- 64GB unified memory target
- 2TB SSD minimum
- external backup SSD
- UPS

{spot} is therefore positioned as a practical local appliance rather than a cloud SaaS moderation platform.

## 17. How Sentinel Squad Delivers It

Sentinel Squad does not sell {spot} on hourly or day-rate billing.

Instead, Sentinel Squad uses:
- a Value Credit model for implementation value
- a monthly product and management component
- a subscription model when Sentinel Squad provides the hardware

Current commercial structure in this repository:
- implementation packaged into Value Credits
- hardware costs rolled into a subscription structure
- monthly product and management retained as part of the service model

## 18. Current Project Truth

The project is now aligned so that:
- SSOT reflects Apertus as primary
- code defaults reflect SSOT
- reporting reflects the real resolved model route
- docs reflect the actual {spot} architecture
- production planning and quote materials are consistent with the implementation baseline

## 19. The Most Important Documents

If you want to understand {spot} in layers, read these documents in this order:
1. this file: [`README_BRIEF.md`](/Users/moldovancsaba/Projects/spot/README_BRIEF.md)
2. SSOT contract: [`ssot/SSOT.md`](/Users/moldovancsaba/Projects/spot/ssot/SSOT.md)
3. machine/runtime SSOT: [`ssot/ssot.json`](/Users/moldovancsaba/Projects/spot/ssot/ssot.json)
4. main operational overview: [`README.md`](/Users/moldovancsaba/Projects/spot/README.md)
5. architecture: [`docs/ARCHITECTURE.md`](/Users/moldovancsaba/Projects/spot/docs/ARCHITECTURE.md)
6. foundation baseline: [`FOUNDATION.md`](/Users/moldovancsaba/Projects/spot/FOUNDATION.md)
7. ingestion contract: [`docs/INGESTION.md`](/Users/moldovancsaba/Projects/spot/docs/INGESTION.md)
8. production plan: [`docs/PRODUCTION_PLAN.md`](/Users/moldovancsaba/Projects/spot/docs/PRODUCTION_PLAN.md)
9. client quote: [`quote.md`](/Users/moldovancsaba/Projects/spot/quote.md)
10. handover log: [`docs/HANDOVER.md`](/Users/moldovancsaba/Projects/spot/docs/HANDOVER.md)

## 20. Bottom Line

{spot} is a governed, local, Apertus-first Excel classification system designed to identify antisemitic and related harmful content with deterministic behaviour, explicit review handling, and strong auditability.

That is the project.
