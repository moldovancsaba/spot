# {spot} Handover Log

## 2026-03-12 Europe/Budapest - Codex

- Objective: align {spot} SSOT, runtime defaults, audit reporting, and public docs around the actual Apertus-first architecture.
- Changes:
  - promoted SSOT to `0.2` with explicit runtime and security defaults
  - made lane defaults derive from SSOT
  - added backend-qualified model-spec support for evaluation routing
  - preserved backward compatibility for legacy Ollama tags such as `qwen2.5:7b`
  - fixed resolved model-version reporting for MLX/Apertus runs
  - documented local-only security defaults and current architecture
- Files touched:
  - `ssot/SSOT.md`
  - `ssot/ssot.json`
  - `ssot/ssot.example.json`
  - `src/models.py`
  - `src/ssot_loader.py`
  - `src/defaults.py`
  - `src/lanes.py`
  - `src/classifier.py`
  - `src/pipeline.py`
  - `src/ensemble/ensemble_runner.py`
  - `src/excel_io.py`
  - `src/cli.py`
  - `src/__init__.py`
  - `backend/main.py`
  - `README.md`
  - `DESIGN.md`
  - `FOUNDATION.md`
  - `MONITORING_UI.md`
  - `CHANGELOG.md`
  - `docs/ARCHITECTURE.md`
  - `docs/INGESTION.md`
  - `docs/BRAIN_DUMP.md`
  - `docs/PROJECT_MANAGEMENT.md`
  - `docs/HANDOVER.md`
  - `docs/RELEASE_NOTES_0.3.0.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py` => passed
  - `python3 - <<... load_ssot/defaults ...` => SSOT `0.2`, policy model `mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`, defaults aligned
  - `./.venv/bin/python -m src.cli classify --input samples/tev_apertus_mlx_classifier_smoke4.xlsx ... --run-id ssot-align-smoke --limit 1` => completed successfully
  - smoke artifact proof: `runs/ssot-align-smoke/integrity_report.json` shows `ssot_version=0.2`, `policy_profile=prompt-v0.2`, `model_version=mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`
  - workbook proof: `/tmp/tev_ssot_align_smoke.xlsx` latest appended metadata shows `Model Version=mlx:mlx-community/Apertus-8B-Instruct-2509-4bit`, `SSOT Version=0.2`, `Pipeline Version=mvp-0.3.1`
- Known follow-up:
  - regenerate fresh benchmark and acceptance artifacts under the new `0.3.1` baseline
  - produce production rollout and investment plan from the now-aligned architecture baseline

## 2026-03-12 Europe/Budapest - Codex (Production Planning)

- Objective: convert the aligned `0.3.1` / SSOT `0.2` baseline into a client-ready production delivery plan.
- Changes:
  - added a {spot} production plan document grounded in the current Apertus-first architecture
- Files touched:
  - `docs/PRODUCTION_PLAN.md`
  - `docs/HANDOVER.md`
- Validation:
  - document content cross-checked against `ssot/SSOT.md`, `ssot/ssot.json`, `README.md`, and runtime files under `src/`
- Known follow-up:
  - produce dated client quote using confirmed hardware configuration and labor rate assumptions

## 2026-03-12 Europe/Budapest - Codex (Commercial Alignment)

- Objective: align the {spot} production plan with Sentinel Squad's Value Credit commercial model.
- Changes:
  - replaced day-rate style pricing assumptions with Value Credit packaging in the production plan
- Files touched:
  - `docs/PRODUCTION_PLAN.md`
  - `docs/HANDOVER.md`
- Validation:
  - production plan content cross-checked against the provided Sentinel Squad pricing rules and the {spot} production baseline
- Known follow-up:
  - attach final hardware pass-through quote once the client hardware configuration is fixed

## 2026-03-12 Europe/Budapest - Codex (Client Quote)

- Objective: produce a client-sendable commercial quote for {spot} using the Sentinel Squad Value Credit model and a subscription structure.
- Changes:
  - added `quote.md` with a hardware-backed monthly subscription proposal
  - bundled hardware, implementation recovery, and monthly product/management into one monthly price
- Files touched:
  - `quote.md`
  - `docs/HANDOVER.md`
- Validation:
  - quote values cross-checked against the current {spot} production plan and the live hardware pricing basis used in this session
- Known follow-up:
  - confirm final hardware procurement route before signature if the client wants a different machine specification

## 2026-03-12 Europe/Budapest - Codex (Master Brief)

- Objective: create one top-level document that explains {spot} end-to-end from goal through architecture, delivery model, and operating method.
- Changes:
  - added `README_BRIEF.md` as the master project brief
  - linked the brief from the main README documentation map
- Files touched:
  - `README_BRIEF.md`
  - `README.md`
  - `docs/HANDOVER.md`
- Validation:
  - brief content cross-checked against SSOT, runtime docs, production plan, and quote documents
- Known follow-up:
  - keep `README_BRIEF.md` updated whenever the SSOT or commercial model materially changes

## 2026-03-17 Europe/Budapest - Codex (Foundation Hardening Start)

- Objective: start the foundation-hardening pass needed to turn `{spot}` into a delivery-safe local appliance baseline.
- Changes:
  - added a dedicated hardening plan document with workstreams, release gates, and execution phases
  - added the first local appliance runbook for operator-facing local deployment flow
  - clarified in core docs that the standard runtime path is `drafter -> classifier` and that `judge` is only used on disagreement and evaluation paths
  - narrowed quote wording so the client-facing scope matches the implemented antisemitism-classification boundary
- Files touched:
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `README.md`
  - `README_BRIEF.md`
  - `docs/ARCHITECTURE.md`
  - `docs/PRODUCTION_PLAN.md`
  - `quote.md`
  - `docs/HANDOVER.md`
- Validation:
  - documentation changes cross-checked against current runtime behavior in `src/classifier.py`, `src/ensemble/ensemble_runner.py`, `src/pipeline.py`, and current SSOT files
- Known follow-up:
  - add preflight automation and install/bootstrap steps for local Apple Silicon delivery
  - refresh commercial documents further if subscription packaging becomes the sole client model
  - produce fresh smoke evidence package under the current baseline

## 2026-03-17 Europe/Budapest - Codex (Preflight Command)

- Objective: add a supported local-appliance preflight check so machine readiness can be verified before classification or UI startup.
- Changes:
  - added a CLI `preflight` command
  - added local checks for Apple Silicon architecture, virtual environment presence, SSOT validity, runtime dependency availability, loopback-only Ollama configuration, writable runs directory, disk-space headroom, and backend port bindability
  - documented the command in the main README and local appliance runbook
- Files touched:
  - `src/preflight.py`
  - `src/cli.py`
  - `README.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - pending local execution against the current workspace after implementation
- Known follow-up:
  - expand preflight to verify install/bootstrap state and model-weight availability more deeply if delivery requirements tighten

## 2026-03-17 Europe/Budapest - Codex (Bootstrap Command)

- Objective: add a supported local setup path so the appliance has a repeatable bootstrap flow in addition to preflight validation.
- Changes:
  - added a CLI `bootstrap` command
  - added local bootstrap logic for `runs/`, `logs/`, and `.venv/`
  - added optional `requirements.txt` installation and structured JSON output with next steps
  - documented bootstrap usage in the main README and local appliance runbook
- Files touched:
  - `src/bootstrap.py`
  - `src/cli.py`
  - `README.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - pending local execution against the current workspace after implementation
- Known follow-up:
  - add model-weight bootstrap guidance if the delivery process standardises local model storage paths

## 2026-03-17 Europe/Budapest - Codex (SPOT Namespace And Security Hardening)

- Objective: complete the next delivery-hardening step by moving the product-facing runtime namespace to `SPOT_*` and adding stronger production controls and audit outputs.
- Changes:
  - switched the primary runtime environment namespace from `TEV_*` to `SPOT_*`, while keeping temporary compatibility aliases in code
  - added `SPOT_PRODUCTION_MODE` support
  - added production-mode model-route allowlist enforcement for classification and evaluation paths
  - added backend production-mode restrictions to block evaluation start and reject unsupported classify payload keys
  - added `artifact_manifest.json` with per-artifact hashes for completed runs
  - added `disagreement_report.json` for disagreement and judge-path auditability
  - updated product-facing docs and security notes to refer to `{spot}` and `SPOT_*`
- Files touched:
  - `src/defaults.py`
  - `src/classifier.py`
  - `src/pipeline.py`
  - `backend/main.py`
  - `README.md`
  - `FOUNDATION.md`
  - `MONITORING_UI.md`
  - `CHANGELOG.md`
  - `docs/FOUNDATION_HARDENING_PLAN.md`
  - `docs/PRODUCTION_PLAN.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - `python3 -m py_compile src/*.py src/ensemble/*.py src/evaluation/*.py backend/main.py backend/models/*.py backend/routes/*.py` => passed
  - `python3 -m src.cli bootstrap --project-root . --venv-path .venv --requirements requirements.txt --runs-dir runs --logs-dir logs --skip-install` => passed
  - `SPOT_PRODUCTION_MODE=1 .venv/bin/python -m src.cli preflight --ssot ssot/ssot.json --runs-dir runs --port 8765` => passed
- Known follow-up:
  - complete a fresh classification smoke run under the new artifact-manifest baseline once local model execution is available without blocking

## 2026-03-17 Europe/Budapest - Codex (Security Gap Closure)

- Objective: close the previously identified gaps in the SPOT delivery hardening work.
- Changes:
  - removed TEV runtime alias support and made `SPOT_*` the sole product runtime namespace
  - added production-mode SSOT path locking and full lane-route enforcement for classifier, drafter, and judge
  - added structured fallback reporting on classification results and workbook output
  - added workbook size, row-count, text-length, and null-byte guardrails
  - added explanation sanitisation to reduce prompt/control-text leakage into output files
  - tightened bootstrap to set restrictive local permissions on runtime directories and SSOT
  - tightened preflight to check locked SSOT path and local file permissions
  - tightened CLI behavior so production mode blocks evaluation runs and ensemble classification from the operator path
- Files touched:
  - `src/models.py`
  - `src/defaults.py`
  - `src/classifier.py`
  - `src/excel_io.py`
  - `src/pipeline.py`
  - `src/ensemble/ensemble_runner.py`
  - `src/cli.py`
  - `src/bootstrap.py`
  - `src/preflight.py`
  - `README.md`
  - `MONITORING_UI.md`
  - `docs/LOCAL_APPLIANCE_RUNBOOK.md`
  - `docs/HANDOVER.md`
- Validation:
  - pending post-change compile and preflight verification in this session
- Known follow-up:
  - complete a successful non-blocking classification smoke run to prove the new fallback and artifact outputs end-to-end
