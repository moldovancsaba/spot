# Changelog

## Unreleased

### 2026-11-11 — operator safeguards, case/report cockpit, classifier route swap

- Committed the previously uncommitted operator-safeguards work as ten reviewable commits: SSOT 0.4, failure policy and review routing, human case decisions and threat reports, automatic any-positive reporting, native reports surface, contract regressions, CI, and documentation reconciliation.
- Swapped the governed classifier route to `ollama://gemma2:9b` with `ollama://qwen2.5:7b` as the independent verifier, on 300-row same-sample evidence: binary recall 0.788 -> 0.936, six-way macro-F1 0.270 -> 0.323, +44% per-row latency.
- Re-ran the 30-row German acceptance under the new route: reference agreement 26.67% -> 40.00%, macro-F1 0.1755 -> 0.3201, zero analysis failures. Formal acceptance remains held; see `docs/ACCEPTANCE_EVIDENCE_2026-11-11.md`.
- Recorded the reference-label audit as a material limitation: `Structural Antisemitism` is 83.5% Israel/Zionism-framed in the approved workbook, so reference agreement is not an accuracy estimate.
- Rebuilt and reinstalled `/Applications/spot.app` from the committed tree; the bundled `classifier.py` is verified byte-identical to the repository.
- Split test-only dependencies into `requirements-dev.txt` (`httpx2`, `pypdf`) and made CI resolve the same set instead of patching requirements at install time.
- Refreshed `ssot/ssot.example.json` to the current contract, aligned `FOUNDATION.md` and `DESIGN.md` to the 0.5.2 / SSOT 0.4 baseline, moved the automatic-reporting clause out of "Explicit Non-Goals", and normalized machine-specific absolute paths across all documentation.
- Disabled automatic AI reporting for the active interrupted run and kept it frozen pending a restart under the new route.

### 2026-11-08 — cockpit reports, human threat decisions, acceptance evaluation

- Added native Reports with case totals, paginated cases, and generated threat report history; attached the German baseline and comparison summaries to their run records.
- Added explicit human confirmed-threat / false-alarm / unresolved decisions with closed-taxonomy categories, evidence-bound write tokens, immutable decision history, and evidence-change invalidation.
- Added gated `{spot}` PDF generation with original post, saved human finding, model evidence, identities, timestamps and hashes; added the pinned `reportlab` dependency and PDF regressions.
- Added mandatory failure review, zero-confidence failure placeholders, and shared safety enforcement at canonical persistence and workbook boundaries.
- Added SSOT 0.4 automatic any-positive AI reporting and its governed preference rules.
- Consolidated `{spot}` into a native-only macOS delivery baseline; removed the server-rendered browser operator UI and browser appliance startup path.
- Added native acceptance smoke coverage at `app/macos/native_acceptance_smoke.py`.
- Rebuilt active operator, acceptance, benchmark, and production docs around the native macOS surface.

## 0.5.2 - 2026-05-11

- Added the bounded `{trinity}` / `{train}` export seam so reviewed run rows feed the review-policy loop (`src/trinity_spot_bundle.py`, `export-trinity-spot-bundles`).
- Limited export eligibility to reviewed rows with saved `confirm` or `adjust` decisions.
- Promoted the workspace baseline to `0.5.2` and the pipeline marker to `mvp-0.5.2` across version surfaces, native bundle metadata, and maintainer docs.

## 0.5.1 - 2026-05-10

- Promoted the active workspace baseline to `0.5.1` and the pipeline marker to `mvp-0.5.1`.
- Rewrote active README sections so the repository no longer reads as a public open-source distribution; documented the source-checkout install, update, removal, and maintenance path.
- Aligned the client package, developer handover, runbook, and baseline docs to the same maintainer/support posture.

## 0.5.0 - 2026-05-07

- Renamed the native macOS app source root from `app/spot-app` to `app/macos`.
- Aligned active workspace version markers to `0.5.0` and pipeline markers to `mvp-0.5.0`.
- Documented the native supervisor baseline, repo layout, generated native build folders, and maintainer-facing source-of-truth paths.
- Clarified that `app/macos/.build/` and `app/macos/dist/` are generated outputs and not source-controlled project structure.

## 0.4.0 - 2026-03-18

- Implemented the local browser operator workflow for upload intake, run status, review, row inspection, artifact retrieval, and sign-off.
- Added local auth/session gating, run recovery operations, and a supported browser appliance startup path.
- Added deterministic browser integration smoke coverage and productionization contracts/docs.
- Normalized the workspace baseline to `0.4.0` and separated historical `0.3.2` acceptance evidence from the live template.

## 0.3.2 - 2026-03-18

- Added the local-hardware benchmark checklist.
- Added the structured UAT checklist.
- Added the acceptance evidence template for benchmark and client sign-off capture.
- Added a developer-facing repo handover readme aligned to the current `{spot}` baseline.
- Promoted the workspace baseline to `0.3.2` while keeping `v0.3.1` as the latest shipped release.

## 0.3.1 - 2026-03-12

- Promoted SSOT to `0.2` and made runtime routing/security defaults explicit in `ssot/ssot.json`.
- Switched {spot} architectural baseline to Apertus-first classification on MLX.
- Made lane defaults derive from SSOT instead of duplicated hard-coded literals.
- Added explicit `backend://model` model-spec support for evaluation and mixed-backend runs.
- Fixed audit reporting so MLX/Apertus runs record the resolved classifier route instead of being mislabeled as Qwen.
- Updated output workbook metadata so `Model Version` reflects the resolved runtime route used for each row.
- Added loopback-only Ollama security guard with explicit opt-out via `SPOT_ALLOW_REMOTE_OLLAMA=1`.
- Rewrote architecture/foundation/runtime docs to match the real implementation baseline.

## 0.3.0 - 2026-02-28

- Added full classify monitoring workflow UI at `/classify-monitor`.
- Added classify process control endpoints:
  - `POST /classify/start/{run_id}`
  - `POST /classify/pause/{run_id}`
  - `POST /classify/resume/{run_id}`
  - `POST /classify/stop/{run_id}`
  - `GET /classify/status/{run_id}`
- Added PID auto-discovery so monitor/control also works for classify runs started outside UI.
- Hardened MLX output handling for unstructured model responses:
  - deterministic category extraction guardrails
  - controlled explanation fallback
  - `UNSTRUCTURED_MODEL_OUTPUT` flag
- Installed and pinned MLX runtime dependencies in project requirements.
- Upgraded project documentation to production handover quality.

## 0.2.0 - 2026-02-27

- Replaced `HATORI_*` routing keys with `{spot}` runtime routing keys, with legacy compatibility aliases retained during migration.
- Removed writer lane from {spot} architecture.
- Added explicit {spot} lane model: `classifier`, `drafter`, `judge`.
- Added optional MLX backend support for classifier and judge lanes.
- Added backend fallback behavior for classifier/judge/drafter routing failures.
- Kept closed-set taxonomy enforcement and fallback category controls intact.
- Preserved deterministic ensemble logic and minority-report evidence.
- Updated documentation for workflow, guarantees, and versioning boundaries.

## 0.1.0

- Initial SSOT-aligned MVP pipeline.
- Deterministic single-label classification.
- Deterministic evaluation framework (single vs ensemble).
- Agent Eval UI with near-real-time progress tracking.
