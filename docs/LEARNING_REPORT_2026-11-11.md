# Learning report — first adapter, 2026-11-11

## Why learning is required

Routing cannot fix discrimination. Measured against the double-annotated reference, flagging every row either
model calls positive gives recall 0.987 at a **88% review volume**. Thresholding cannot help:

| Flag rule (either model positive) | Recall | Review volume | Missed |
|---|---:|---:|---:|
| conf >= 0.30 / 0.50 / 0.70 | 0.987 | 88% | 2 |
| conf >= 0.85 | 0.929 | 76% | 11 |
| conf >= 0.95 | 0.344 | 28% | 101 |

A workload of 62,024 rows cannot be handed to humans, so the classifier itself has to improve.

## Pipeline

`script/build_gold_sample.py` -> `script/build_training_set.py` -> `mlx_lm lora` -> `script/evaluate_adapter.py`.
285 of the 300 accepted rows reproduce from the approved workbook and seed (183 train / 57 valid / 45 test).
No post text is committed.

## First adapter result (Apertus-8B-Instruct-2509-4bit 4-bit, LoRA r=8, 600 iters, lr 1e-5)

Validation loss fell 3.79 -> 0.62. On the 45 held-out rows:

| Metric | Base | Adapter | Delta |
|---|---:|---:|---:|
| Six-way agreement | 27.27% | **60.00%** | **+32.73 pp** |
| Six-way macro-F1 | 0.150 | **0.294** | **+0.144** |
| Binary precision | 0.700 | **0.833** | +0.133 |
| Binary recall | **0.875** | 0.417 | **-0.458** |
| Binary F1 | **0.778** | 0.556 | -0.222 |

Per class, the adapter learned boundaries the base never had: `Not Antisemitic` F1 0.000 -> **0.704**,
`Conspiracy Theories` 0.000 -> **0.615**. It also lost `Anti-Israel` recall (0.750 -> 0.444).

**Interpretation:** with 183 training rows the adapter learned the reference's strict boundary and became
conservative — it now distinguishes political criticism from antisemitism, which is real learning, but it
under-calls antisemitic rows. Directionally correct, not yet fit for a recall-first product.

## Hybrid policies on the same 45 rows

| Policy | Precision | Recall | F1 | Review volume | Missed |
|---|---:|---:|---:|---:|---:|
| qwen positive >= 0.30 | 0.714 | 0.833 | 0.769 | 62% | 4 |
| gemma positive >= 0.30 | 0.605 | 0.958 | 0.742 | 84% | 1 |
| union | 0.605 | 0.958 | 0.742 | 84% | 1 |
| adapter alone | 0.833 | 0.417 | 0.556 | 27% | 21 |

No combination delivers high recall at a maintainable volume with these models. The adapter shows the
achievable trade (27% volume) and what it costs (21 misses of 36 positives).

## Next iteration

1. **More labels.** 183 training rows cannot teach a boundary this subtle. The learning cycle already
   collects reviewed rows; each review session grows the set. Target several hundred agreed positive rows
   before judging the approach.
2. **Recall-aware objective.** Class-balanced sampling and/or positive-class weighting, then re-measure —
   the current run optimises agreement, not recall.
3. **Compare against a stronger base** once one is available locally; the LoRA path is base-agnostic.
4. **Adopt only on a measured gate**, and record the adapter path in the governed runtime configuration.

## State

The 62,024-row run is **paused** rather than consuming ~9 days of compute to produce a review queue that is
not maintainable. It resumes from committed state with one call once the model is good enough that its flags
are worth a human's time.


---

# Iteration 2 — 2026-11-12

## Recall-aware weighting

Iteration 1 optimised agreement and became conservative (recall 0.875 -> 0.417). The builder now repeats
antisemitic rows and lifts thin classes (`--positive-repeat 3 --min-per-class 40`), giving a training set
that is 78.8% positive while keeping the identical held-out split.

## Results on the same 45 held-out rows

| Model | Six-way agreement | Macro-F1 | Binary P | Binary R | Binary F1 |
|---|---:|---:|---:|---:|---:|
| Base `Apertus-8B` | 27.27% | 0.150 | 0.700 | 0.875 | 0.778 |
| Adapter 1 — chat prompt, agreement-optimised | 60.00% | 0.294 | 0.833 | 0.417 | 0.556 |
| Adapter 2 — chat prompt, recall-weighted | **64.44%** | **0.445** | 0.750 | **0.875** | **0.808** |
| Adapter 3 — **live pipeline prompt**, recall-weighted | **64.44%** | 0.401 | 0.741 | 0.833 | 0.784 |

Adapter 3 is the deployable one: it trains on exactly the string `src.classifier` sends, so there is no
prompt-shift at serving time. Its checkpoint-200 was chosen because validation loss rose afterwards
(0.382 -> 0.618), i.e. it overfits past that point.

## What changed in the model

- `Not Antisemitic` F1 0.000 -> 0.718; `Conspiracy Theories` 0.000 -> 0.333; `Anti-Israel` 0.750 -> 0.686;
  `Anti-Judaism` 0.000 -> 0.667.
- JSON reliability: 0 unparsed of 45, versus 89.7% malformed for the untuned Apertus route earlier.
- Positive-prediction volume on this balanced split: 60% (27 of 45), versus 84% for the model ensemble and
  100% under the no-auto-clear posture. On the real corpus (~17% positive) that projects to roughly 35-45%
  review volume — better, still not yet a maintainable queue.

## Deployment status

`SPOT_MLX_ADAPTER_PATH` is wired into the classifier route and covered by tests, so the adapter can serve
through the normal pipeline. Two blockers remain before adopting it for a full run:

1. **Per-row process spawn.** The MLX route shells out to `mlx_lm generate` per row and reloads the model
   each time; 62,024 rows would take days just in loading. Adoption wants a persistent inference worker.
2. **Decision gate.** The gain is measured on 45 rows. It is a real improvement, but adopting it as the
   primary classifier should be a recorded decision with a larger held-out set.

## Honest state

The learning loop works end to end: labels -> weighted dataset -> LoRA -> held-out measurement -> deployable
adapter path. What it lacks is **labels** — 183 training rows cannot define this boundary. Each review the
queue collects feeds the next iteration, which is the mechanism the service was built for.
