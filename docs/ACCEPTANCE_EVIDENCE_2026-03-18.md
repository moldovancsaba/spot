# {spot} Acceptance Evidence Record

Document date: `2026-03-18`
Acceptance session baseline: `0.3.2`
SSOT: `0.2`

## Session Details

- Date: `2026-03-18`
- Machine model: `MacBookPro18,3` (`MacBook Pro`, Apple M1 Pro, 10 cores)
- Unified memory: `16 GB`
- SSD size: `994.7 GB`
- macOS version: `macOS 26.4 (25E5233c)`
- Python version: `3.14.3`
- `{spot}` commit hash: `efbbce887405b6fde888e4f34e6601630f010b50`
- Release tag: `v0.3.1`
- SSOT path: `/Users/moldovancsaba/Projects/spot/ssot/ssot.json`
- Production mode: `SPOT_PRODUCTION_MODE=1` used for bootstrap/preflight/classify runs
- Operator: `Codex`
- Reviewer: `Pending client review`

## Benchmark Record

- Benchmark workbook: `/tmp/spot_acceptance_primary_input.xlsx`
- Row count: `1` executed for the accepted primary-path benchmark record
- Language: `de`
- Primary-route run ID: `acceptance-primary-limit1-20260318`
- Duration: `55s` (`2026-03-18T10:30:46Z` to `2026-03-18T10:31:41Z`)
- Rows per minute: `1.09`
- Output workbook: `/tmp/spot_acceptance_primary_limit1.xlsx`
- Artefact directory: `/Users/moldovancsaba/Projects/spot/runs/acceptance-primary-limit1-20260318`
- Result summary: run completed and artefacts were written; policy shows the expected Apertus MLX primary route, but the workbook row recorded `CLASSIFIER_FALLBACK_FAILED`, so the primary route did not produce a clean accepted classification result on the tested row. Additional benchmark finding: `samples/sample_germany.xlsx` was rejected before inference because row `257` exceeded the `10000`-character `Post text` guardrail.

## Fallback Record

- Fallback demonstrated: `yes`
- Run ID: `acceptance-fallback-20260318`
- Trigger reason: controlled empty-text row
- Fallback event type: `EMPTY_TEXT_FALLBACK`
- Affected rows: `1`
- Evidence files: `/Users/moldovancsaba/Projects/spot/runs/acceptance-fallback-20260318/integrity_report.json`, `/Users/moldovancsaba/Projects/spot/runs/acceptance-fallback-20260318/artifact_manifest.json`, `/tmp/spot_acceptance_fallback.xlsx`
- Operator visibility confirmed: `yes`

## Disagreement Record

- Disagreement demonstrated: `no`
- Run ID: `acceptance-eval-limit1-20260318`
- Disagreement row count: `0`
- `disagreement_report.json` present: `no`
- Judge participation confirmed: `no`
- Evidence files: `/Users/moldovancsaba/Projects/spot/runs/acceptance-eval-limit1-20260318/evaluation_report.json`, `/Users/moldovancsaba/Projects/spot/runs/acceptance-eval-limit1-20260318-ensemble/integrity_report.json`, `/Users/moldovancsaba/Projects/spot/runs/acceptance-eval-limit1-20260318-ensemble/artifact_manifest.json`

## Workbook Output Review

- Metadata columns present: `yes`
- `Assigned Category` correct: `conditional`
- `Fallback Events` present when expected: `yes`
- `Review Required` populated correctly: `yes`
- Explanation quality acceptable: `conditional`
- Notes: the fallback workbook output is correct and operator-visible. The benchmark and ensemble workbook outputs both append the expected metadata columns, but the tested benchmark row resolved to `Not Antisemitic` with `CLASSIFIER_FALLBACK_FAILED`, so semantic correctness cannot be accepted from this session alone.

## Artefact Review

- `policy.json` present: `yes`
- `integrity_report.json` present: `yes`
- `artifact_manifest.json` present: `yes`
- `logs.txt` present: `yes`
- Artefact access path confirmed: `yes`
- Notes: verified on `acceptance-primary-limit1-20260318`, `acceptance-fallback-20260318`, and both evaluation sub-runs. The ensemble evaluation also produced `/Users/moldovancsaba/Projects/spot/runs/acceptance-eval-limit1-20260318/evaluation_report.json`.

## Operational Review

- preflight completed: `yes`
- operator started run successfully: `yes`
- operator retrieved outputs successfully: `yes`
- operator understood review workflow: `yes`
- Notes: `py_compile`, bootstrap, and production preflight all passed. Direct runtime probes also passed on this machine: `gemma3:1b` via Ollama returned in about `10.27s`, and direct MLX/Apertus generation returned in about `18.77s`. The full standard classification path remains slower and produced classifier-fallback evidence on the benchmark row.

## Final Acceptance Position

- Decision: `accepted with conditions`
- Critical issues: clean primary-route semantic success was not demonstrated on the benchmark row because the completed benchmark workbook recorded `CLASSIFIER_FALLBACK_FAILED`; disagreement/judge-path evidence was executed but did not produce an actual disagreement case, so `disagreement_report.json` was not generated in this session.
- Non-critical follow-up actions: run benchmark and UAT again on an approved client workbook that satisfies the runtime input guardrails; capture at least one clean primary-route row without classifier fallback; capture one genuine disagreement case that writes `disagreement_report.json`; obtain client-side operator and reviewer sign-off.
- Sign-off date: `2026-03-18`
- Client representative: `Pending`
- Sentinel Squad representative: `Codex`
