# Candidate evaluation against the accepted reference — 2026-11-11

**Reference:** `docs/evaluation/goldset_2026-11-11.jsonl` — 300 labels, owner-accepted as the provisional
evaluation standard (`docs/GOLD_SET_ACCEPTANCE_2026-11-11.md`). **Not human-adjudicated.**
**Rows:** identical for every candidate — `goldset_input.xlsx`, seed 20261110, 50 rows per workbook category.
**Method:** deterministic decoding, same prompt per row, adjudication pipeline bypassed so the model alone is
measured. Reproduce with `script/score_reference.py`.

---

## 1. Results

| Candidate | n | Six-way agreement | Six-way macro-F1 | Binary P | Binary R | Binary F1 |
|---|---:|---:|---:|---:|---:|---:|
| `qwen2.5:7b` (verifier) | 300 | 54.3 % | **0.351** | 0.679 | 0.900 | 0.774 |
| `gemma2:9b` (primary) | 300 | 43.7 % | 0.328 | 0.600 | **0.975** | 0.743 |
| two-stage (binary gate → forced 5-way) | 300 | **55.0 %** | 0.341 | 0.738 | 0.600 | 0.662 |
| disambiguation rubric (partial) | 115 | 57.4 % | 0.347 | 0.738 | 0.857 | **0.793** |
| `Apertus-8B` MLX (rejected) | 87 | 11.5 % | 0.057 | 0.519 | 0.976 | 0.678 |

Rows marked *(partial)* were stopped early and are **not directly comparable** to the 300-row rows.

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
