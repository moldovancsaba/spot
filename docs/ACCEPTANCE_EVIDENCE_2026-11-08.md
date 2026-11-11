# {spot} German Acceptance Evidence — 2026-11-08

## Acceptance position

**Engineering recommendation: hold production acceptance.** The installed workflow operates and audit artifacts verify, but classification agreement with the approved workbook's existing labels remains poor. The designated reviewer is the project owner (the user), who approved the German workbook in this session. The owner's final decision is pending. No review decisions were saved on the owner's sample rows.

## Machine and execution

- Machine: Mac18,5, Apple Silicon, 32 GiB unified memory; macOS 27.2; Python 3.12.16.
- Workspace and installed app: `/Users/Shared/Projects/spot`, `/Applications/spot.app`; baseline 0.5.2 with local uncommitted corrections.
- Models: governed Apertus MLX primary, Qwen 2.5 7B fallback, Granite drafter and governed judge lanes. No training or route substitution was performed.
- Both measured runs used the actual native-supervised production backend, one worker, German language and full review. The cockpit displayed progress throughout.
- Initial watched-inbox intake uncovered a missing production start default; it was fixed and tested against the actual start builder. Pause/resume/stop were exercised on the initial control run, which was excluded from scoring.
- A completed-progress/stale-startup precedence bug and incomplete-canonical-coverage sign-off gap were fixed. Completed states now display correctly, and sign-off requires canonical row coverage.

## Dataset and method

The approved input is `samples/sample_germany.xlsx`. Its 62,024 nonblank source rows include mixed spelling/case variants and unlabelled rows. Selection normalized existing category labels using the runtime mapping (including Holocaust Denial → Classical Antisemitism), excluded unlabelled/empty posts and duplicate text, and sampled five posts per canonical category using seed 20261108. The resulting 30-row sample's reference labels were stored separately and hidden from inference. The uploaded workbook hash matches the prepared sample.

This is **reference-label agreement**, not an independently adjudicated accuracy estimate. The sample is small and balanced, does not represent natural category prevalence, and the second run reuses the same sample after a generic preprocessing correction. Fresh held-out evaluation and reviewer adjudication remain required.

## Results

| Measure | Baseline | Source-preserving comparison |
|---|---:|---:|
| Scored rows | 30 | 30 |
| Exact reference-label matches | 5 | 8 |
| Reference-label agreement | 16.67% | 26.67% |
| Macro F1 against reference labels | 0.1067 | 0.1755 |
| Missing outputs | 0 | 0 |
| Analysis-failure placeholders | 0 | 0 |
| Runtime | 459.57 seconds | 507.92 seconds |
| Throughput | 3.92 rows/minute | 3.54 rows/minute |
| Review-required rows | 30 | 30 |

Full review was intentional; these review rates do not estimate normal partial-review burden. Timing is a single sequential warm-machine observation, not a capacity/SLA benchmark.

| Category | Reference rows | Baseline correct | Comparison correct |
|---|---:|---:|---:|
| Anti-Israel | 5 | 1 | 4 |
| Anti-Judaism | 5 | 1 | 1 |
| Classical Antisemitism | 5 | 0 | 0 |
| Conspiracy Theories | 5 | 0 | 0 |
| Not Antisemitic | 5 | 3 | 3 |
| Structural Antisemitism | 5 | 0 | 0 |

Three categories had no exact matches in either run: Classical Antisemitism, Conspiracy Theories and Structural Antisemitism. Baseline confidence exceeded 0.95 on every row despite only five exact matches; confidence must not be treated as calibrated proof of correctness.

## Source-preservation correction

The baseline drafter changed more than whitespace in 23/30 posts, shortening 11 posts by over 30%. The installed guard accepts only whitespace-equivalent drafts. Other rewrites are rejected, the original post is classified, and a review flag records the rejection. The comparison preserved source text on **30/30** rows and recorded 23 drafter rejections. Twelve comparison rows carried metadata-shape warnings; malformed flag strings are now flagged rather than split into single-character flags. The comparison contained 19 judge-lane rows and no classifier-route fallback.

This fixes evidence preservation and metadata handling, but the remaining reference disagreements still require review and classifier-quality work.

## Acceptance checks completed

- 71 regression tests passed, including production start, terminal-state precedence, canonical coverage, source preservation, malformed metadata and score handling of failed negatives.
- Native build, bundle installation, syntax and Git whitespace checks passed.
- Native watched intake accepted the sample and archived its source; malformed-schema control intake was rejected.
- Anonymous run access was rejected; an operator's attempt to mutate review was denied.
- Real completed runs exposed 30 review rows and a working row inspector.
- Output downloads matched stored workbook hashes. Governed output, policy, integrity and log hashes verified against the runtime manifests.
- Both baseline and comparison native smoke checks passed after the lifecycle correction; no artificial completed-run fixtures were used.
- A separate synthetic empty-text run in `none` mode emitted `EMPTY_TEXT_FALLBACK`, `ANALYSIS_FAILED` and `REVIEW_REQUIRED`. Its deliberate synthetic escalation remained unresolved, and sign-off returned HTTP 409 as expected. No client post was used in that control.
- A cockpit selection correction preserves an explicitly selected completed run during automatic refresh, while active runs retain priority.

## Audit evidence locations

Protected local evidence is under `runs/acceptance-20261108-german-30/`:

- `sample_manifest.json`: seed, normalized reference labels, source-row lineage and hashes.
- `accuracy_report.json` and `accuracy_preserved_report.json`: per-row comparisons, confusion matrices and per-category metrics.
- `baseline_code_hashes.json` and `preserved_code_hashes.json`: installed runtime file fingerprints for each phase.
- `preprocessing_diagnostics.json` and `preserved_diagnostics.json`: source-preservation findings.
- `native_smoke_baseline.json`, `native_smoke_preserved.json`, `native_smoke_pending.json`: live runtime checks.
- `cockpit_baseline_run.json`: initial pause/resume/stop check statuses; `cockpit_preserved_run.json`: comparison start record.
- `fallback_control_report.json`: synthetic fallback and blocked-sign-off evidence.
- `baseline_targeted_disagreement.json`: six targeted second-pass disagreements projected read-only from canonical votes and judge evidence. This is a separately derived acceptance report; the runtime's ensemble disagreement artifact is not rewritten.

Actual governed run directories are `runs/acceptance-german-30-20261108/` and `runs/acceptance-german-preserved-30-20261108/`. The synthetic control is `runs/acceptance-empty-control-20261108/`. Original source and governed outputs remain intact.

## Reviewer action and remaining gates

Review the comparison run in the cockpit and adjudicate the 22 reference disagreements using original post context. The existing workbook labels may themselves require correction; do not relabel the evaluation set to match model predictions without independent adjudication. Then refine the governed classification rubric or model candidate against an independent held-out set and rerun acceptance. Full-volume throughput, interrupted-run recovery on representative workloads and independent operator usability sign-off are not established by this bounded session.

The owner has not yet issued a formal acceptance decision. Until then, the engineering recommendation is to **hold acceptance**, preserve mandatory human review, and avoid consequential automated use.
