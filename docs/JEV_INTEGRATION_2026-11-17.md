# JEV integration — investigation and implementation proposal

**Date:** 2026-11-17
**JEV repo:** https://github.com/moldovancsaba/jev (cloned and read at commit `3a3f645`)
**Status:** investigation only; no SPOT or JEV code changed by this document.

## 1. What JEV is (as read, not as assumed)

JEV is a **scaffold-stage local decision model** for an Apple M4 (16 GB) Mac mini. No trained model, no
inference implementation, no benchmark exists yet; the repository contains the contract, data plan,
architecture and a dependency-ordered backlog (#1–#15, M0–M4).

The v0.1 contract (docs/ARCHITECTURE.md) is precise:

- `POST /v1/decide` on 127.0.0.1: `{context, question, options[{id, description}]}`
- Response: `{selected_id, probabilities by id, max_probability, abstained, model_version, calibration_version, latency_ms}`
- 2–8 caller-defined options; reject duplicates, invalid counts, oversized context; never silently truncate
- Base model + optional LoRA adapter; **temperature calibration on a dedicated split**; abstention is an
  evaluated policy, not a by-product of normalization
- Offline after weights download; MLX; candidate Qwen3-0.6B then maybe 1–2B; no Jev API dependency
- Governance: one independently executable outcome per issue, GDS-only UI, no private data or weights in git,
  no inferred quality claims

## 2. Why it fits {spot} — the decision-problem shape

JEV's primitive (bounded question, fixed options, calibrated probability, abstention) is exactly the shape of
{spot}'s hardest remaining problems. Each of these is a `/v1/decide` call:

| {spot} problem | question | options | abstention → |
|---|---|---|---|
| **Judge lane** (llama3.1 today, uncalibrated score) | "Is the proposed category supported?" | PASS / REVIEW / FAIL | REVIEW_REQUIRED |
| **Deliberation re-vote** | "Which category fits the author's position?" | the seven categories | TRINITY_DISAGREEMENT |
| **Calibrated confidence (T11, currently a static per-category table)** | "How certain is the final category?" | per-category probability distribution | LOW_CONFIDENCE → review |
| **Review triage** | "Which expert action fits this row?" | confirm / correct / information-request | expert question |
| **Pattern triage (task 11)** | "Is this a new pattern for the weekly TEV review?" | yes-pattern / no / more-examples | postpone decision |
| **Escalation pre-screen (task 15)** | "Does this row need priority handling?" | priority / normal | — (legal decision stays human) |

The first three are the highest value: they close the two gaps measured this month — **uncalibrated judge
confidence** and **models that cannot confirm negatives** — with a small scorer whose probabilities are
temperature-calibrated by construction, on hardware that adds only ~1–2 GB to the current footprint.

## 3. What {spot} gives JEV — real training corpora in JEV's exact format

JEV's DATA.md format (`id, source_family, synthetic, context, question, options, correct_id, rationale,
provenance`) is exactly what {spot}'s operations already produce:

| Source | Records | correct_id from |
|---|---|---|
| Gold set v2 (285 reproducible rows, seven categories) | context = post + rubric, question = category, options = 7 categories | accepted double-annotated label |
| Trinity verdicts on the 62k run | context = post + proposals, question = re-vote, options = 7 categories | majority/adjudicated verdict |
| Review queue decisions | context = row + machine verdict, question = expert action, options = confirm/correct/info-request | the human review decision |
| Pattern proposals (task 11) | context = pattern + examples, question = is it a pattern, options = yes/no/more | TEV decision |
| Escalation pre-screens | context = row + flags, question = priority handling, options = priority/normal | TEV legal decision |

Privacy aligns by construction: {spot} commits hashes and manifests, never post text; JEV forbids private
data in git. The export tooling (`build_gold_sample`, `build_training_set`) already regenerates texts from
approved workbooks and seeds, so a JEV-format export can be deterministic and hash-verifiable.

## 4. Phased implementation (maps to JEV backlog order #1–#15)

### Phase 1 — JEV v0.1 baseline in the JEV repo (its own board governs it)

Execute JEV's backlog in order: #1 MLX environment (Qwen3-0.6B pinned, tokenizer/logit access verified,
cold/warm latency and memory measured) → #7 contracts → #3 first 100-example pilot **drawn from the {spot}
gold set v2 as the pilot rubric** → #2 direct answer scoring → #10 scorecard → #4 LoRA → #5 temperature
calibration + abstention policy → #6 local service.

**First application selected: the judge lane** — smallest decision problem {spot} has, three fixed options,
and the current llama3.1 judge is the weakest calibrated component.

### Phase 2 — {spot} consumption (one new lane, no workflow change)

- `src/classifier.py`: `backend="jev"` route calling `POST /v1/decide` for the judge task; response
  probabilities become the judge score; `abstained=true` ⇒ REVIEW_REQUIRED (replaces uncalibrated
  `run_judge` score only when the JEV service answers).
- Calibrated confidence: the category-scoring decide call (option 3 above) replaces the static
  `calibration-v1.json` lookup as the primary confidence source; the table remains the fallback.
- Everything else (trinity routing, audit strata, review policy) is unchanged — the routing contract stays
  identical, only the confidence/judge signal improves.

### Phase 3 — Train "our JEV" on {spot} processes

- Export the §3 corpora in JEV format (deterministic, hash-verifiable, source text regenerated from approved
  workbooks); train/validation/calibration/test splits grouped by `source_family` per DATA.md.
- Train the LoRA adapter on the judge rubric first, then the category rubric, then triage rubrics.
- Promote through JEV's registry; {spot} consumes the promoted adapter via a versioned config, with rollback
  to the previous judge (the existing model registry + bakeoff discipline already provides the promotion
  record format — reuse it rather than invent a second one).

## 5. Risks and constraints (measured against this machine)

| Risk | Assessment |
|---|---|
| Memory | Qwen3-0.6B ~1 GB, 1–2B ~3 GB on MLX; coexists with the trinity lanes on this 32 GB M4. The JEV target is 16 GB, so staying small keeps JEV portable and {spot} safe. |
| Latency | One extra local call per judged row (~tens of ms on 0.6B); negligible against the current ~10 s/row. |
| Calibration validity | JEV's own plan: fit temperature on a calibration split, evaluate ECE/abstention coverage on untouched test; no claims before that. |
| Distribution shift | SPOT corpora are German today; TEV real data is Hungarian. Train per locale exactly like the gold standards; never mix (D1). |
| "No Jev API dependency" | Respected: the dependency is our own local service, not an external Jev API. |
| Governance | JEV's board is the execution authority for Phase 1; {spot}'s board for Phase 2/3. No cross-repo claims without both boards' evidence. |

## 5a. Owner decisions (2026-11-17)

1. **Local JEV on this machine** — the working copy lives at `/Users/Shared/Projects/jev`, branch
   `spot-judge`, tracking upstream `moldovancsaba/jev` main. Upstream is checked periodically: general
   improvements come in, spot-specific knowledge stays local, and worthwhile general work goes back later
   as PRs.
2. **First application: the judge lane** (PASS/REVIEW/FAIL).
3. **Hardware: this machine** — measured as Apple M6 / 32 GB (stronger than JEV's 16 GB target, so the
   small-model budget keeps JEV portable).

## 5b. Progress so far (first implementation session, local JEV)

- Environment recorded; venv with mlx-lm 0.31.3 pinned (requirements-lock.txt).
- Qwen3-0.6B downloaded, revision pinned, loads directly from HF safetensors (no conversion).
- `src/local_decision`: strict schemas (2–8 unique options; oversized context rejected, never truncated),
  direct likelihood scoring with **sequence log-likelihood for multi-token labels** (REVIEW is 2 tokens),
  CLI. 7 tests.
- Measured: load 1.07 s, warm decide ~140–260 ms, peak RSS ~1.5 GB.
- Judge pilot: 100 adjudicated PASS/FAIL records (50/50) compiled from the accepted spot reference;
  raw records git-ignored, manifest committed with sha256. REVIEW-class records deferred to the TEV
  borderline samples.
- **Zero-shot baseline: 0.50 accuracy, PASS 30/30, FAIL 0/30** — the base model answers PASS to
  everything. That is the measured starting point the rubric pilot and LoRA (upstream issues #3/#4) must
  beat; the scorecard is recorded in the JEV reports.

## 5c. Second session progress (2026-11-17, evening)

- Scorecard harness (upstream #10) live: judge 0.774 / category 0.571 on the held-out split; Brier 0.187;
  ECE 0.106. **Found a real defect: option-order reversal flips 10 of 20 decisions** - spot pins a fixed
  option order, and the fix track is permutation-averaging or order-augmented training.
- Calibration (upstream #5): fit attempted, and the honest decision is T=1.0 with no abstention - the
  fitted T=2.1 flattened the distribution (median max-prob 0.14) and hurt discrimination. Per-rubric
  calibration waits for the TEV samples.
- Service (upstream #6): local /v1/decide on 127.0.0.1:8770, single-threaded by MLX stream affinity,
  bounded body, no raw context logging, health endpoint, 3 contract tests.
- spot lane: SPOT_JEV_URL routes the judge task to JEV (PASS/REVIEW/FAIL + max_probability score);
  abstention maps to REVIEW with JUDGE_ABSTAINED; JEV_JUDGE/JEV_CALIBRATED provenance flags; any failure
  falls back to the Ollama judge. 150 tests. Verified end-to-end against the live service.
- Known v0.1 limits: PASS bias persists (FAIL recall 0.548), thin category classes are 0, REVIEW class
  untrained (pilot had none) - all need the TEV borderline samples.

## 5d. Enabled in production + aggressive retraining loop (2026-11-17, evening)

- Deployed with the disagreement guard: JEV decides, llama3.1 corroborates; an opposite PASS/FAIL split
  routes to REVIEW (JEV_JUDGE_DISAGREEMENT). Verified live: new rows carry JEV_JUDGE / JEV_CALIBRATED /
  JEV_LLAMA_CORROBORATED provenance in their traces, and the guard has already fired.
- Aggressive training loop (JEV repo): cursor-bounded trinity-confirmed feedback -> judge-only retraining
  -> gate on the fixed human test -> promote with atomic jev-active swap + service restart (SPOT falls back
  during the seconds). First promotion: jev-v1, judge 0.774 -> 0.881 on the held-out human split; category
  drift recorded and tolerated (not consumed in production). Cadence: scripts/train_and_swap.sh, every 500
  new confirmed rows or every 6h.
- Known bias: JEV still PASS-biases wrong proposals alone (control 0.637); production safety therefore
  depends on the corroboration guard, not on JEV alone.

## 6. Open questions for the owner

1. **Repo boundary (recommended A):** implement the scorer in the JEV repo and have {spot} consume it as a
   local service — keeps JEV general-purpose and its board authoritative. Alternative B: port the scoring
   design into {spot}'s `src/` directly (faster, but couples the repos and duplicates JEV's future work).
2. **First application:** judge scoring (recommended) vs category re-vote vs review triage?
3. **Hardware:** implement and measure on this M4/32 GB (the machine {spot} runs on), keeping the 16 GB
   budget as a constraint so JEV stays portable?

## 7. Tracking

SPOT board issue: [JEV] Integration — local decision service for calibrated judge/scoring lanes.
JEV-side issues remain on the JEV board (#1–#15); none are created or moved by this document.
