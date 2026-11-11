# Gold-set acceptance record — 2026-11-11

**Decision:** the project owner accepts the AI-produced annotation (`goldset_2026-11-11.jsonl`) as the
**provisional evaluation reference** for {spot}. Human adjudication is deferred; when it lands, it supersedes
this reference.

This document records the decision, its authority, its limits, and the conditions under which it expires —
so the artifact can be used now without ever being mistaken for human-adjudicated ground truth.

---

## 1. What was accepted

| Property | Value |
|---|---|
| Reference | `docs/evaluation/goldset_2026-11-11.jsonl` |
| Rows | 300 (50 per workbook category, seed 20261110) |
| Producer | AI assistant (deepseek-flash), blind single pass, `RULES.md` v1 |
| Human adjudicated | **No** |
| Label distribution | Not Antisemitic 140 · Anti-Israel 74 · Conspiracy Theories 52 · Anti-Judaism 20 · Classical Antisemitism 13 · Structural Antisemitism 1 |
| Contents | `sample_id`, `text_sha256`, accepted `label`, original `workbook_label`. **No post text is committed** — regenerate the sample from the seed to reproduce the texts. |
| Authority | Project owner, 2026-11-11 |

## 2. Why it is usable

Before this record the project had no fixed reference: the workbook labels contradict their own definitions
(`Structural Antisemitism` is 83.5 % Israel/Zionism-framed), and every comparison against them was arguable.
Accepting one frozen reference makes measurements **reproducible and comparable** — the same 300 labels apply
to every future candidate.

It is usable for *engineering decisions*: is candidate A better than B, did a prompt change help, does a
threshold move the operating point. It is not usable for *claims about reality* — see §3.

## 3. Limits that do not go away by being accepted

1. **It is not human adjudication.** It is one LLM's reading of the taxonomy.
2. **The self-reference effect is measured, not assumed.** On these same 300 rows, scoring qwen against this
   reference raises macro-F1 by **+0.050** versus the workbook (0.351 vs 0.300), because the annotator agrees
   with the model (54.3 %) more than with the workbook (42.7 %). Any figure computed against this reference is
   therefore an **upper bound relative to a human standard**.
3. **Shared blind spots are invisible.** The models, the annotator, and the rule text share a training
   distribution. Where all three are wrong together, this reference cannot detect it.
4. **`Structural Antisemitism` is effectively unused** — assigned once in 300 rows. That is a property of the
   reference, and it should not be read as proof the category is meaningless in the source corpus.

**Therefore this reference may not be cited as evidence of classification accuracy in any client-facing or
regulatory context.** It may be cited as the agreed internal baseline.

## 4. What it unlocks

- A fixed, versioned target for all candidate comparisons (`docs/evaluation/goldset_2026-11-11.jsonl`).
- The six-way feasibility question becomes decidable on a stable reference instead of a moving one.
- A pre-annotation draft for the future human pass: correcting 300 pre-filled rows is far cheaper than
  labelling from scratch, and the corrections become the real gold set.

## 5. What it does not change

- **Automatic AI reporting stays disabled.** A provisional reference does not authorize unassisted
  publication; `automatic_reporting.enabled` remains `false` in the governed SSOT.
- **Six-way output remains advisory.** Accepting a reference does not make the classifier better.
- **Binary triage remains the supported operating mode** (F1 0.887–0.918 across candidates).
- **Formal acceptance remains held** (`docs/ACCEPTANCE_EVIDENCE_2026-11-11.md`).

## 6. Expiry

This reference is superseded automatically when either of the following lands:

1. A human-adjudicated gold set at kappa ≥ 0.60 with all conflicts resolved, or
2. A redefined taxonomy whose categories are separable under independent reading.

At that point this file becomes historical evidence and the decision record must be re-run against the
successor reference.

## 7. Reproducing a measurement

```bash
# regenerate the sample inputs (texts are not committed)
cd /Users/Shared/Projects/spot
.venv/bin/python script/acceptance_german.py prepare \
  --source samples/sample_germany.xlsx --destination /tmp/gold-20261111 \
  --per-category 50 --seed 20261110
# score any candidate JSONL against the frozen reference
.venv/bin/python script/score_reference.py --pred <candidate.jsonl>
```

The scoring helper resolves rows by `text_sha256`, so the post text never needs to be stored beside the labels.
