# {spot} German Acceptance Evidence — 2026-11-11

## Acceptance position

**Engineering recommendation: hold formal acceptance.** The classifier route was changed from
`qwen2.5:7b` primary to `gemma2:9b` primary on measured evidence, and the bounded 30-row acceptance
improved from 26.67% to 40.0% reference agreement. That is a real, reproducible gain, not a sufficiency
proof. The remaining blocker is the reference labels themselves, not the model: the workbook's six
categories are applied with heavy overlap (see "Material limitation"). The designated reviewer is the
project owner. **No formal client acceptance decision has been issued.**

## Machine and execution

- Machine: Apple Silicon, 32 GiB unified memory; macOS 27.2; Python 3.12.16.
- Workspace: `/Users/Shared/Projects/spot`, branch `codex/spot-79-operator-safeguards`, workspace
  baseline `0.5.2`, pipeline `mvp-0.5.2`, SSOT `0.4`.
- The entire working tree was committed before this run (commits `039600c`..`46c2413`, plus the route
  swap as `54645f5`). `/Applications/spot.app` was rebuilt from that committed tree and reinstalled;
  the bundled `src/classifier.py` SHA-256 matches the repository byte-for-byte
  (`f81058c3…a84987887`). This is the first evidence record where the deployed artifact is traceable to
  a commit.
- Route under test: classifier `ollama://gemma2:9b`; independent verifier / fallback
  `ollama://qwen2.5:7b`; judge `ollama://llama3.1:8b`; `prompt-v0.3-independent-checks`;
  deterministic decoding (`temperature=0`, `top_p=1`, seed 42), structured JSON schema.
- Validation before the run: `bash script/verify-contracts.sh` → **106 tests, OK**;
  `preflight --inference-smoke` → 50 checks, 0 errors, `inference_primary: passed`,
  `inference_fallback: passed`.
- One worker, German, `partial` review mode, CLI (`src.cli classify`), run id
  `acceptance-gemma-30-20261111`.

## Why the route changed

Both models were measured on the same 300 stratified rows (seed 20261109), same prompt, same decoding,
with the adjudication pipeline bypassed so the model alone was measured:

| Model | Binary precision | Binary recall | Binary F1 | Six-way macro-F1 |
|---|---:|---:|---:|---:|
| `qwen2.5:7b` (previous primary) | 0.934 | 0.788 | 0.855 | 0.270 |
| `gemma2:9b` (previous fallback, now primary) | 0.886 | **0.936** | **0.911** | **0.323** |

The configured fallback outperformed the configured primary on every metric except precision, and the
decisive difference for this product is recall — missed antisemitic posts (53 → 16 false negatives) are
the failure mode that matters. Cost: 4.61 s → 6.65 s per row (+44%).
Supporting alternatives were tested and rejected: `qwen3.8:27b` produced no parseable output on 86% of
rows at 76 s/row; a hierarchical two-stage classifier scored worse (macro-F1 0.186); a hand-built
disambiguation rubric scored worse (0.243). Details in the run's `policy.json` and the workspace bake-off
artifacts.

## Dataset and method

The approved input is `samples/sample_germany.xlsx` (62,024 nonblank rows). Selection normalized existing
labels to the closed taxonomy (including Holocaust Denial → Classical Antisemitism), excluded unlabelled
and duplicate posts, and sampled five posts per canonical category with seed 20261108 — the same 30-row
sample used on 2026-11-08, so the comparison is like-for-like. Reference labels were stored in
`sample_manifest.json` and hidden from inference.

This is **reference-label agreement**, not an independently adjudicated accuracy estimate. The sample is
small and balanced and does not represent natural category prevalence.

## Results

| Measure | 2026-11-08 baseline (MLX/Apertus) | 2026-11-08 source-preserving (Qwen) | 2026-11-11 route swap (Gemma primary) |
|---|---:|---:|---:|
| Scored rows | 30 | 30 | 30 |
| Exact reference-label matches | 5 | 8 | **12** |
| Reference-label agreement | 16.67% | 26.67% | **40.00%** |
| Macro F1 against reference labels | 0.1067 | 0.1755 | **0.3201** |
| Missing outputs | 0 | 0 | 0 |
| Analysis-failure placeholders | 0 | 0 | 0 |
| Runtime | 459.57 s | 507.92 s | 660.48 s |
| Throughput | 3.92 rows/min | 3.54 rows/min | 2.72 rows/min |
| Review-required rows | 30 | 30 | 30 |

Timing is a single sequential warm-machine observation, not a capacity or SLA benchmark. The 44% per-row
cost increase is the measured price of the recall gain.

| Category | Reference rows | Baseline correct | Source-preserving correct | Route-swap correct |
|---|---:|---:|---:|---:|
| Anti-Israel | 5 | 1 | 4 | **5** |
| Anti-Judaism | 5 | 1 | 1 | 0 |
| Classical Antisemitism | 5 | 0 | 0 | **3** |
| Conspiracy Theories | 5 | 0 | 0 | **1** |
| Not Antisemitic | 5 | 3 | 3 | 3 |
| Structural Antisemitism | 5 | 0 | 0 | 0 |

Two categories that had zero exact matches in both 2026-11-08 runs (Classical Antisemitism, Conspiracy
Theories) now match. Structural Antisemitism remains 0/5 — consistent with both models never emitting
that category under any prompt tested.

## Coverage observation

The run emitted only four of the six categories (predicted distribution: Anti-Israel 18, Not Antisemitic
5, Classical Antisemitism 5, Conspiracy Theories 2, Anti-Judaism 0, Structural Antisemitism 0). The
taxonomy is therefore not being exercised across its full range even where the route correctly recalls
Anti-Israel. `canonical_set_validation_passed` was true and `taxonomy_violation_count` was 0, so this is
model behaviour, not a contract failure. 30/30 rows were judged, 30/30 second passes ran, 5 second-pass
overrides occurred, and 32 fallback events were recorded.

## Material limitation: reference label consistency

A vocabulary audit over all 31,755 labelled rows shows the workbook's categories are not applied as
mutually exclusive:

| Category | n | Israel/Zionism vocabulary | Religion vocabulary | Conspiracy vocabulary |
|---|---:|---:|---:|---:|
| Anti-Israel | 12,499 | 66.3% | 7.8% | 0.7% |
| Anti-Judaism | 294 | 34.0% | 53.7% | 2.7% |
| Classical Antisemitism | 966 | 53.7% | 9.6% | 1.7% |
| **Structural Antisemitism** | 909 | **83.5%** | 8.9% | 12.4% |
| Conspiracy Theories | 629 | 63.6% | 8.9% | 35.9% |
| Not Antisemitic | 17,279 | 7.5% | 3.1% | 1.2% |

`Structural Antisemitism` is defined as systemic exclusion of Jews with no Israel/Zionism component, yet
83.5% of its labelled rows are Israel/Zionism-framed — a higher rate than Anti-Israel itself. Hand
inspection confirms it (e.g. "Israelische Zionisten haben Tiktok übernommen" is labelled Structural and is
Anti-Israel under the contract definition). Two independent models also agree with each other and disagree
with the reference label on 63.4% of rows where they agree.

**Consequence:** the reference-agreement figures above are depressed by label inconsistency as well as by
model error. They cannot be read as accuracy. A 300-row double-annotated, adjudicated gold set with
mutually exclusive boundary rules is the prerequisite for any accuracy claim; tooling and rules are
prepared, human annotation is not yet done.

## Acceptance checks completed

- 106 model-free contract tests pass on the committed tree.
- Preflight inference smoke passes for both the new primary and the verifier.
- Swift build, bundle build, install, `plutil -lint`, and all three `bash -n` syntax gates pass.
- Installed bundle verified to embed the swapped SSOT and a byte-identical `classifier.py`.
- Acceptance run completed with `canonical_set_validation_passed: true`, 0 taxonomy violations, 0 missing
  outputs, 0 analysis failures.

## Audit evidence locations

- Governed run: `runs/acceptance-gemma-30-20261111/` (`policy.json`, `integrity_report.json`,
  `processing_stats.json`, `artifact_manifest.json`, `output.xlsx`, `logs.txt`).
- Prepared sample and scoring: `runs/acceptance-gemma-30-20261111-evidence/` (`sample_manifest.json`,
  `accuracy_report.json`, the prepared workbook and the CLI log). Earlier copies under `/tmp` were temporary.
- `policy.json` records `ssot_version 0.4`, `prompt-v0.3-independent-checks`,
  `model_version ollama:gemma2:9b`.

## Reviewer action and remaining gates

1. Annotate the prepared gold set (two independent annotators), adjudicate conflicts, and confirm kappa
   ≥ 0.60. Re-score all model candidates against it before any further route or threshold decision.
2. Decide whether six-way autonomy is in scope at all. Measured behaviour supports binary triage plus
   human six-way adjudication; the review cockpit already implements the human side.
3. Re-run this same 30-row acceptance after the gold set lands, so the number is measured against coherent
   targets.
4. Full-volume throughput, interrupted-run recovery at representative scale, and operator usability
   sign-off remain unestablished. The 62,024-row run was **archived and purged** on 2026-11-11: its
   audit evidence (419 automatic AI reports plus policy, recheck, review-history and run logs) is preserved
   under `runs/_archive/2026-11-11-german-full-system-autoreports/`, the managed source upload and its
   62,024 canonical rows are retained, and the run itself was removed so it cannot be auto-recovered under
   a different model route. Any successor run must be started fresh under the current route.

The owner has not issued a formal acceptance decision. Until then: keep open any-positive automatic
reporting disabled, keep mandatory human review, and avoid consequential automated use.
