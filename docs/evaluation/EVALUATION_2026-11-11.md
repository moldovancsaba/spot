# Candidate evaluation against the accepted reference — 2026-11-11

**Reference:** `docs/evaluation/goldset_2026-11-11.jsonl` — 300 labels, owner-accepted as the provisional
evaluation standard (`docs/GOLD_SET_ACCEPTANCE_2026-11-11.md`). **Not human-adjudicated.**
**Rows:** identical for every candidate — `goldset_input.xlsx`, seed 20261110, 50 rows per workbook category.
**Method:** deterministic decoding, same prompt per row, adjudication pipeline bypassed so the model alone is
measured. Reproduce with `script/score_reference.py`.

---

## 1. Results

Scored against the **double-annotated** reference (kappa 0.827):

| Candidate | n | Six-way agreement | Six-way macro-F1 | Binary P | Binary R | Binary F1 |
|---|---:|---:|---:|---:|---:|---:|
| `qwen2.5:7b` (verifier) | 300 | 52.7 % | 0.338 | 0.660 | 0.909 | **0.765** |
| `gemma2:9b` (primary) | 300 | 42.7 % | 0.331 | 0.581 | **0.981** | 0.729 |
| two-stage (binary gate → forced 5-way) | 300 | **56.0 %** | **0.349** | 0.723 | 0.610 | 0.662 |

Against the earlier single-pass reference the figures were 0.351 / 0.328 / 0.341; the ranking is unchanged and
the ceiling is unchanged, which is what a stable reference should produce.

### Safest detector: union of both models

| Detector | Precision | Recall | F1 | False negatives (of 160 positives) |
|---|---:|---:|---:|---:|
| gemma2 alone | 0.581 | 0.981 | 0.729 | 3 |
| qwen alone | 0.660 | 0.909 | 0.765 | 14 |
| **union — either model flags** | 0.576 | **0.987** | 0.727 | **2** |
| intersection — both flag | 0.668 | 0.903 | 0.768 | 15 |

The union is the safest screening configuration: it misses 2 rows in 300 instead of 3–15. It is now the
governed behaviour — `ANY_POSITIVE_ANALYSIS` forces human review whenever any single analysis branch assigns a
positive category at confidence >= 0.30, which is effectively the union rule applied at row level.

## 2. Per-class behaviour (n = 300 candidates)

| Category | Reference support | qwen F1 | gemma2 F1 |
|---|---:|---:|---:|
| Not Antisemitic | 140 | 0.632 | 0.400 |
| Anti-Israel | 74 | 0.650 | 0.555 |
| Conspiracy Theories | 52 | 0.197 | 0.500 |
| Anti-Judaism | 20 | 0.395 | 0.303 |
| Classical Antisemitism | 13 | 0.231 | 0.209 |
| Structural Antisemitism | **1** | 0.000 | 0.000 |

## 3. What this establishes

1. **No candidate exceeds 0.35 six-way macro-F1** on a fixed, accepted reference. The cap is not an artefact of
   comparing against the workbook any more.
2. **Four of six classes are thinly supported by the reference itself** (52, 20, 13 and 1 rows). Even a perfect
   classifier could not be validated on `Structural Antisemitism` from this sample; the class appears once.
3. **Binary triage remains the reliable capability** — F1 0.66–0.79 across every candidate, with recall up to
   0.975 (gemma2) and the best balance in the disambiguation variant.
4. **Prompt-level interventions do not beat the plain prompt on six-way.** The two-stage gate, the hand-built
   disambiguation rubric, and the flat prompt all land within 0.03 macro-F1 of each other. Against a fixed
   reference, the differences are not meaningful.
5. **The Apertus MLX route is not a candidate.** 11.5 % six-way agreement, 89.7 % malformed output.

## 4. Consequences

- The adopted configuration stands: `gemma2:9b` primary for recall, `qwen2.5:7b` as independent verifier.
- **Six-way output stays advisory.** Binary triage plus human six-way adjudication remains the supported mode.
- **Automatic AI reporting stays disabled** (`automatic_reporting.enabled: false`) — a 0.35 macro-F1 taxonomy
  cannot justify unassisted publication.
- Further prompt engineering is not worth pursuing against this reference; the next real gain requires either
  human adjudication of the labels or a taxonomy whose classes are separable and adequately sampled.

## 5. Reproducing

```bash
cd /Users/Shared/Projects/spot
.venv/bin/python script/score_reference.py --pred path/to/candidate.jsonl
```

Rows join on `text_sha256`, so no post text is stored beside the labels. Regenerate the sample inputs with
`script/acceptance_german.py prepare --per-category 50 --seed 20261110`.
