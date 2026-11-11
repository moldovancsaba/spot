# Model selection decision record — 2026-11-11

**Status:** DECIDED — model exploration closed for the current hardware and label set.
**Supersedes:** the implicit assumption in SSOT 0.4 that a suitable local model could be found by
swapping candidates.

---

## 1. Question

Can the closed six-category taxonomy be produced autonomously by a locally runnable model on this
appliance (Apple Silicon, 32 GB unified memory, local Ollama/MLX only)?

## 2. What was measured

All candidates were scored on the identical 300 rows (`goldset/goldset_input.xlsx`, seed 20261110,
50 rows per workbook category), same prompt, same deterministic decoding, with the adjudication
pipeline bypassed so the model alone was measured.

Two references were used, because neither is authoritative:

- **Workbook labels** — the approved input's existing categories. Not independently adjudicated, and
  shown below to contradict their own definitions.
- **AI annotation** (`llm_annotation/`) — a blind independent LLM pass. Useful as a contrast, **not**
  usable as ground truth: it agrees with the models more than with the workbook, so scoring against it
  inflates results.

| Candidate | Six-way macro-F1 vs workbook | vs AI annotation | Binary P / R / F1 vs workbook | Latency | Outcome |
|---|---:|---:|---|---:|---|
| `qwen2.5:7b` (previously primary) | 0.300 | 0.351 | 0.967 / 0.820 / 0.887 | 4.6 s | kept as verifier |
| `gemma2:9b` (**current primary**) | **0.354** | 0.328 | 0.900 / 0.936 / **0.918** | 7.0 s | adopted |
| `qwen3.8:27b` | — | — | — | 76 s | **rejected**: 86 % unparseable output, 8.5× slower |
| `Apertus-8B-Instruct-2509-4bit` (MLX) | in progress | — | — | 14.9 s | structured output clean on the rows run so far; 0 malformed |
| two-stage hierarchical (binary gate → forced 5-way) | 0.186 | — | 0.977 / 0.500 / 0.661 | 1.8 s | rejected |
| flat + hand-built disambiguation rubric | 0.243 | — | — | 4.2 s | rejected |

## 3. What the numbers establish

1. **Six-way autonomy is not supported by any tested candidate.** The best result, 0.354 macro-F1,
   means three of six categories are effectively unusable. `Structural Antisemitism` scores **0.000**
   for every model; an independent annotator reproduced it **1 time in 50**.
2. **The ranking of models is reference-dependent.** gemma2 leads against workbook labels (0.354 vs
   0.300); qwen leads against the independent annotation (0.351 vs 0.328). A result that flips with the
   choice of reference is a measurement of label noise, not of model quality. **Model comparisons on
   six-way output are not decidable with these labels.**
3. **Binary triage is reliable.** Both models separate "antisemitic at all" from "not antisemitic"
   strongly (F1 0.887–0.918). The capability exists at the bedrock and fails at the taxonomy layer.
4. **Scale does not fix it and cannot be afforded.** A 27B model on this machine produced mostly
   unparseable output and ran 8.5× slower, driving macOS swap from 2.7 GB to 9.0 GB. The next Apertus
   size up is 70B, whose INT4 footprint is ~40 GB — larger than this machine's 32 GB total.

## 4. The binding constraint is the label definition, not the model

Vocabulary audit over all 31,755 labelled rows: `Structural Antisemitism` — defined as systemic
exclusion of Jews with no Israel component — is **83.5 % Israel/Zionism-framed**, higher than
`Anti-Israel` itself (66.3 %). Independent annotation agrees with the workbook on **42.7 %** of rows.
Two models agree with each other on 58.3 % and disagree with the workbook on most of those.

No model, prompt, threshold, or parameter count can be validated against targets that contradict their
own definitions. **This decision record therefore closes model selection, not classification work.**

## 5. Decision

- **Adopt `gemma2:9b` as primary** with `qwen2.5:7b` as independent verifier. It has the best measured
  binary recall (0.936) and best workbook-reference six-way score, at a cost of +44 % latency.
- **Stop searching for a better classifier.** No further candidate, prompt variant, or size increase
  will be adopted until the label problem is resolved.
- **Treat six-way output as advisory, never authoritative.** Binary triage plus human six-way
  adjudication is the supported operating mode.
- **Keep automatic any-positive reporting disabled.** It publishes branded reports off the same
  unreliable six-way output.

## 6. Apertus, specifically

Apertus ships in exactly two sizes, 8B and 70B (70.6B dense, Apache-2.0;
[apertus-ai.org](https://www.apertus-ai.org/pages/about/)). The 70B at INT4 requires roughly 40 GB
([VRAM reference](https://www.aquanode.io/models/apertus)) against 32 GB of unified memory here.

- **70B: not evaluated, not feasible on this appliance.** Measured proxy: an 18 GB model already drove
  swap to 9 GB and an 8.5× slowdown. A ~40 GB model would exceed physical memory and run unusable
  slowly, not merely slower.
- **8B (MLX): measurement in progress.** The previously documented "frequent malformed responses" has
  not reproduced so far — the MLX route is returning structured output cleanly with 0 malformed rows to
  date, at ~14.9 s/row. Full 300-row figure to be appended to §7 on completion. This does not change the
  decision: an 8B candidate cannot resolve a taxonomy-boundary problem, and the close-out holds either way.

**If someone wants a larger Apertus, it needs ≥64 GB unified memory (96 GB comfortable),** and even then
the label problem remains the ceiling. A fine-tune on a human-confirmed gold set is the only path that
attacks the actual constraint; raw scale ranks below it.

## 7. Evidence locations

| Artifact | Path |
|---|---|
| Candidate runs (identical rows) | `bakeoff/gold-qwen2-5-7b.jsonl`, `bakeoff/gold-gemma2-9b.jsonl`, `bakeoff/gold-apertus-8b.jsonl` |
| AI annotation + diagnostics | `llm_annotation/` (workspace) |
| Sample + manifest | `goldset/` (workspace) |
| Prior 300-row comparison | `bakeoff/model-qwen2.5-7b.jsonl`, `model-gemma2-9b.jsonl` |
| Acceptance evidence | `docs/ACCEPTANCE_EVIDENCE_2026-11-11.md` |

## 8. What would reopen this decision

1. A human-confirmed, adjudicated gold set (kappa ≥ 0.60) that resolves the category boundaries.
2. A narrowed or redefined taxonomy whose categories are actually separable.
3. Hardware with ≥64 GB unified memory **and** a reason to believe scale addresses the boundary
   problem — which the Apertus-70B question would then legitimately answer.
4. A governed fine-tuning pipeline on adjudicated labels (epic #50 path).
