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
