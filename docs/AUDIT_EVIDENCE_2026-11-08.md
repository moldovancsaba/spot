# {spot} Local Audit Hardening Evidence

Date: 2026-11-08 (Europe/Budapest)
Workspace: `/Users/Shared/Projects/spot`, baseline 0.5.2 with local uncommitted hardening changes.
Installed app: `/Applications/spot.app`, rebuilt and installed from this checkout.

## Verified behavior

- Missing, invalid and null model categories produce a governed fallback placeholder with `ANALYSIS_FAILED`, zero confidence and mandatory review across full/partial/none modes.
- Shared persistence/output safety gates keep canonical rows and workbook review indicators consistent.
- Escalated rows do not count as completed review for sign-off. Learning export excludes escalated rows and failure/fallback evidence.
- MLX requests use response-only stdout and an assistant JSON prefill; model request deadlines default to 120 seconds, with bounded output. Timeout reports do not disclose prompt text.
- Health explicitly distinguishes startup readiness from inference verification. Preflight can check both classifiers with `--inference-smoke` and verifies the actual Ollama listening address.
- Native authentication is enabled with generated per-install access codes and actor/role controls in Settings. Sign-off uses the selected session rather than silently elevating to an administrator identity.

## Validation

- Regression entrypoint: `bash script/verify-contracts.sh`; all 65 tests passed.
- Native Swift package/build, bundle build and installation: passed. The compiler emits two non-fatal CommandLineTools linker search-path warnings.
- Shell script syntax, Info.plist and Git whitespace checks: passed.
- Production preflight with real primary/fallback inference: passed; 52 checks, zero errors, one occupied-backend-port warning because the app was already running.
- Both synthetic classifier probes returned structured `Not Antisemitic` responses.
- Complete synthetic German workbook classification: passed; primary Apertus route, no failure flags, no fallback events, expected assigned/raw category, and an integrity report with canonical-set validation passed.
- Synthetic workbook/artifacts remain in the temporary directory `spot-acceptance-20261108-ztbezf9q` under the machine's temporary root; no client workbook was used or altered.
- Installed classifier, failure policy, preflight, backend and canonical persistence files were checked against the checkout with SHA-256 equality.
- Installed health reports `auth_enabled=true`; anonymous `GET /runs` returns HTTP 401. Native Settings visibly confirms an authenticated operator session.
- Ollama and Spot actual listening sockets verified as `127.0.0.1:11434` and `127.0.0.1:8765`.
- Ollama desktop's network-exposure preference is saved off. No additional Ollama server or login helper is enabled.
- A model-free GitHub workflow was added locally; it has not been pushed or executed on GitHub.

## Remaining acceptance boundary

This is local engineering verification, not full client acceptance or an accuracy benchmark. Historical workbooks are unchanged and still require the interim manual safeguard. Shared-code authentication does not independently verify organizational identities. A 32 GB machine can run out of GPU memory when Apertus competes with another resident large model; release that model in its owning app before classification. One audit diagnostic confirmed Metal insufficient-memory failure under that condition. Production cutover still requires representative benchmark/UAT and owner sign-off.

## Acceptance evaluation follow-up

The project owner approved the German repository sample and identified themselves as reviewer. A reproducible balanced 30-row reference-label comparison completed through the native cockpit, with reference labels hidden from inference. The first run completed with 5/30 exact label matches (16.67%), no request-failure placeholders, and verified output/artifact hashes. It is not acceptable evidence of classification quality. Its drafter changed more than whitespace on 23/30 posts, shortening 11 posts by more than 30%.

The follow-up preserves original text modulo whitespace and rejects drafter rewrites explicitly. The installed production start handler's missing progress default, completed-state precedence, and legacy canonical-coverage sign-off gate were also corrected. The 71-test suite passed. The same-sample source-preserving comparison completed with 8/30 matches (26.67%), zero source-preservation violations, verified artifact hashes and a passing synthetic empty-text/sign-off control. It is separate from fresh held-out validation; the owner must adjudicate disagreements and decide acceptance. Detailed results are in `docs/ACCEPTANCE_EVIDENCE_2026-11-08.md`. No review decision has been saved on the owner's real sample rows.
