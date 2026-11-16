# {spot} × TEV Implementation Plan

**Version:** 1.0 — 2026-11-16
**Source:** TEV consultation deck (SPOT.pdf, 13 pages, 2026-11-16) and owner decisions recorded below.
**Status:** Planning only. No code, contract, or runtime change is made by this document. The current system stays untouched for demo until implementation starts.
**Board:** GitHub project `{spot} - From IDEA to LIVE` (project #5). Every issue below is on that board.

---

## 1. Owner decisions (binding for this plan)

| # | Decision | Consequence |
|---|---|---|
| D1 | Languages are managed **separately, never together**; each language has its own gold standard. | Per-language corpora, per-language training sets, per-language acceptance gates. No cross-language mixing in evaluation or training. |
| D2 | The **trinity model** (three independent evaluators, compare, justify, re-vote) is the target: it gives more confidence and less human load. | Replace the current primary+verifier+judge arrangement with three independent evaluators plus a deliberation round. |
| D3 | Adopt the **TEV seven-category taxonomy**, starting with it; more categories can be added later. | Contract change: SSOT, prompts, training data, deterministic fallback, tests, DB columns, UI. |
| D4 | "Even unanimous model proposals can be wrong" is accepted and managed as part of the system. | Keep and extend QA sampling of unanimous and "Not antisemitic" rows; never claim certainty from agreement alone. |
| D5 | No code or process changes until the demo completes; this plan is the preparation artifact. | All work is documented planning + GitHub issues until implementation is started. |
| D6 | **Parallel workers committed.** Go for parallel segment workers; capacity is grown, not argued about. | T16/T17 are the committed approach with an explicit memory budget and capacity model; the SLA volume target follows from the worker count. |
| D7 | **The trinity lane models are never final.** Always search for the best possible, more trustworthy model for each lane and language; promote only on measured gate improvement. | A standing model-advancement program (T24/T25): per-language candidate bakeoffs, gate-gated promotion, recorded rollback to the previous model. |

---

## 2. Measured current state (as of 2026-11-16, read-only snapshot)

**Live run** `full-62024-final-20261114` (German corpus, 62,024 rows):

| Metric | Value |
|---|---|
| Rows processed | 19,071 / 62,024 (30.8%) |
| Review-required | 61.0% of processed rows |
| Throughput | 9.69 s/row → ~9,600 rows per 26 h SLA window, single worker |
| Category mix | Not antisemitic 77.2%, Anti-Israel 18.8%, Anti-Judaism 2.2%, Classical 1.5%, Conspiracy 0.2%, Structural ~0% |

**Review volume drivers** (19,017-row sample — the reason the queue feels "incredibly high"):

| Driver | Share of rows |
|---|---:|
| `ANY_POSITIVE_ANALYSIS` (any lane positive) | 47.3% |
| `SECOND_PASS_DISAGREEMENT` | 33.1% |
| `MISSING_CONTEXT` (judge) | 32.0% |
| `SOFT_SIGNAL_REVIEW` | 19.9% |
| `AUDIT_SAMPLE` | 6.3% |
| `AUTO_RESOLVED_CONSENSUS` | 40.2% |

The dominant cause of volume is **policy**, not noise: the current rule sends every positive finding and every suspicion signal to review. The TEV workflow sends only *disagreement and uncertainty* to a human, with sampled verification of the closed rows. Adopting that rule is the single largest volume change.

**Model measurements** (102-row held-out gate, never trained on):

| Metric | Base Apertus-8B | Fine-tuned adapter |
|---|---:|---:|
| Six-way agreement | 8.51% | 50.00% |
| Macro-F1 | 0.052 | 0.366 |
| Unparsed/unstructured outputs | 55/102 | 0 |
| Binary P / R / F1 (live-prompt adapter) | — | 0.741 / 0.833 / 0.784 |

**Verifier behaviour** (why unanimity will not be cheap until models improve):

- 359 live rows: verifier positive while primary says Not; **354 of 359 at confidence ≥ 0.85** — confident splits, not hedging.
- On the balanced gate the verifier contributes 0 exclusive positives; on the live distribution it touches 8.4% of rows.
- Conclusion already recorded: volume reduction must come from **better models**, not from deleting the disagreement signal.

**Learning pipeline** (already working end-to-end):

- 285 of 300 accepted reference rows reproduce from workbook + seed; double-annotated, kappa 0.827.
- `build_gold_sample → build_training_set → mlx_lm lora → evaluate_adapter` with a held-out gate; adoption is a recorded decision.
- Fine-tuned adapter adopted as primary after the gate; `SPOT_MLX_ADAPTER_PATH` wired; in-process MLX inference (2.2–3.3 s/row per lane).

---

## 3. Strengths to preserve (with evidence)

These are the parts of the system the TEV workflow already assumes and that must survive the refactor:

1. **Deterministic, auditable pipeline** — temperature 0, seed 42, JSON-schema-constrained decoding, taxonomy enforcement with deterministic fallback. Every classification carries a trace with per-lane model identity, judge verdict, and source hash.
2. **Independent assessments** — primary, verifier, judge already disagree on record; the trinity change extends this, it does not invent it.
3. **Disagreement already routes to humans** — `ANY_POSITIVE_ANALYSIS`, `SECOND_PASS_DISAGREEMENT`, `SOFT_SIGNAL_REVIEW` are exactly the "difference shows what deserves expert review" principle from the deck, applied more aggressively than the deck intends.
4. **QA sampling exists** — 10% deterministic audit of cleared rows (`AUDIT_SAMPLE`) implements the deck's "sample of Not antisemitic rows" and "even unanimous can be wrong" checks.
5. **Review triage** — the review queue sorts by likely value (positive findings first, audit samples last).
6. **Machine vs expert decisions tracked separately** — `review_state`, `review_decision`, `reviewer_note` are distinct from the machine flags; the deck's "expert result tracked separately" is already the data model.
7. **Learning loop with gates** — labelled data → weighted training set → LoRA → held-out gate → recorded adoption. This is the machinery for the deck's "new patterns approved, update and verify before/after" loop; it needs a TEV approval step, not a rebuild.
8. **Operational hardening** — ops DB as canonical truth, segment queue with recovery, single-active-run invariant, supervised runtime, purge/re-intake path, contract test suite (**132 tests, CI green**), deployed bundle byte-identical to `main`.

---

## 4. Weaknesses to fix (with evidence)

1. **Taxonomy gap.** TEV defines seven categories with **Holocaust denial separate**; {spot} has six and folds denial into Classical. Everything downstream (SSOT, prompts, training labels, adapter, tests, DB, UI) inherits the wrong scheme.
2. **No third independent evaluator.** The judge validates a proposed category; it does not independently classify. The deck's mechanism — three independent proposals, compare, justify, re-vote — does not exist yet.
3. **No deliberation round.** On disagreement there is one judge call; there is no "justify, read each other's arguments, re-vote" stage, which is the deck's mechanism for converting disagreement into either agreement or a precise expert question.
4. **Review policy reviews too much.** 61% of rows reach review because every positive and every signal routes there; the target policy reviews disagreement + uncertainty + QA samples. This is the volume problem, and it is a policy change, not a fix in isolation (see §6 risk R2).
5. **Model agreement is the binding constraint.** Verifier splits are confident (98.6% ≥ 0.85); the judge hedges (`MISSING_CONTEXT` on 32% of rows, partially improved by prompt v2); Anti-Israel per-class F1 is 0.541. Unanimity routing with today's models would still leave a large queue — improving agreement precedes trusting unanimity.
6. **Confidence is a fixed prior.** The adopted adapter emits 0.9 unconditionally (documented). Thresholds on confidence are therefore impossible; the deck's uncertainty-driven expert routing needs a real calibrated confidence or a per-lane agreement signal.
7. **Language foundation missing for Hungarian.** All validation (reference, gate, adapter) is German. TEV is Hungarian; the deck's model candidates are justified by Hungarian/EU language support. A Hungarian gold standard and gate must exist before any production claim (D1: per-language, never mixed).
8. **No handover artifact.** The deck requires a closed-channel delivery package (summary + review items with source/snapshot, context, proposed category, short rationale, open question). The system produces an Excel output and an internal review queue, not a TEV handover workbook.
9. **No SLA runner.** The deck sets a daily rhythm (10:00 in, next business day 12:00 out). The current model is a single continuous batch; nothing schedules, packs, or delivers per the SLA.
10. **No priority-case escalation.** The deck's "crime suspicion → highlighted review → legal owner decision → police forwarding" flow does not exist.
11. **Throughput ceiling.** 9.69 s/row ⇒ ~9,600 rows per 26 h window on one worker; a trinity + deliberation row will cost more (~15 s). Daily volume must be agreed (≤ ~5–6k rows/day) or parallel workers/GPU are required (§6 risk R3).
12. **Known operational quirks to harden** (learned, documented): the native app rewrites `native-runtime.env` on launch (launcher defaults are the durable place); a SIGSTOPped worker cannot process stop signals (SIGCONT first); `install-bundle.sh` kills the backend by design (run recovery must be part of any deploy procedure).

---

## 5. Target workflow (as-built of the deck)

```
TEV data owner --closed channel, workdays ≤10:00--> SPOT operator
        intake: text + URL/platform + item id (+timestamps/context if available)
        validation → canonical rows (per language, language never mixed)
        ┌──────────────────────────────────────────────────────────┐
        │ three independent evaluators (same post + same context)  │
        │   Gemma-class model · EuroLLM-class model · Apertus-class │
        └──────────────────────────────────────────────────────────┘
                            │ compare three proposals
              all agree ──────────┬────────── any disagreement
                 │                │                │
             closed       justify → read each other's ──→ re-vote
             (recorded)          arguments
                 │                        │
                 │              agree after deliberation? ── yes ──→ closed (recorded)
                 │                        │ no
                 │                     TEV expert review (open question documented)
                 │
          QA sampling of closed rows (esp. "Not antisemitic" + unanimous)
          priority-case escalation for suspected criminal content
        ┌──────────────────────────────────────────────────────────┐
        │ deliver next business day ≤12:00, closed channel:        │
        │ summary + review items (source, context, proposed        │
        │ category, short rationale, open question)                │
        └──────────────────────────────────────────────────────────┘
TEV expert → decision (recorded separately from machine result)
TEV approves new patterns → update → verify before/after on approved sample
```

Design consequences:

- **Routing = disagreement and uncertainty only.** Unanimous rows close with a recorded certificate of agreement; a deterministic sample of closed rows still reaches review (D4).
- **Deliberation is part of classification**, producing either agreement or a precise expert question — the review package is therefore small and high-value.
- **Every lane's proposal, justification, re-vote and final verdict is stored** per row so machine and expert results remain separately trackable (deck p.7, p.10).
- **Per-language everything** (D1): intake language tag → language-specific lanes/prompts/gold standard → language-specific gate. Nothing trained or evaluated across languages.

---

## 6. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Taxonomy migration invalidates the existing German reference, adapter and the in-flight 62k run. | Contract-first migration (§8 M1): migrate SSOT + prompts + tests before touching labels; re-label only the Holocaust-denial split (11 Classical rows in the held-out set, plus a review of all 300); keep the 6-category run as historical evidence until its purpose is served. |
| R2 | Unanimity routing can increase misses (rows both models get wrong silently). | D4 stands: sampled verification of unanimous + "Not antisemitic" rows is mandatory, deterministic, and measured; the miss rate is reported per cycle, never assumed zero. |
| R3 | SLA cannot be met on one worker. | Parallel workers are committed (D6): N workers over disjoint segments with a memory budget; the capacity model translates worker count into agreed daily volume. |
| R4 | Hungarian quality unproven. | Hungarian double-annotated gold set + the same 102-row-style acceptance gate before any production claim; language separation enforced by intake (D1). |
| R5 | Model candidates in the deck are placeholders ("models are not final"). | D7 makes this a feature, not a risk: lanes are model-agnostic, and a standing bakeoff program per language promotes candidates only on measured gate improvement, with the previous model kept for rollback. |
| R6 | Demo continuity. | Nothing in this plan touches code or runtime; the current supervised run and app remain exactly as they are until implementation starts. |

---

## 7. Non-goals (explicit)

- No code, contract, or runtime change now (D5).
- No claim that any planned model set (Gemma 4, EuroLLM-22B, Apertus) is selected or benchmarked yet.
- No TEV data in the repository or in training without TEV approval; no public artifact contains post text.
- No legal decisions by the system: escalation prepares a case; the TEV legal owner decides and forwards.
- No cross-language mixing in any evaluation or training artifact.

---

## 8. Implementation phases and issues

Issues live on the `{spot}` board (#5) with labels `epic` / `feature`. Native GitHub dependencies are authoritative. Phase order is topological; no dates are invented.

### M0 — Contract and taxonomy foundation (before any other code)

| # | Issue | Blocked by |
|---|---|---|
| T01 | [TEV] Taxonomy v2: seven categories and optional secondary category (epic) | — |
| T02 | [TEV] Contract: seven-category taxonomy in SSOT, prompts, deterministic fallback | T01 |
| T03 | [TEV] Data: re-label reference — Holocaust Denial split + secondary category support | T02 |
| T04 | [TEV] Testing: taxonomy migration regression — old six-category rows map deterministically | T02 |

### M1 — Trinity evaluation and deliberation

| # | Issue | Blocked by |
|---|---|---|
| T05 | [TEV] Trinity: three independent evaluators with justification and re-vote (epic) | T02 |
| T06 | [TEV] Pipeline: third independent evaluator lane (language-tagged model set) | T05 |
| T07 | [TEV] Pipeline: deliberation round — justification, argument review, re-vote | T06 |
| T08 | [TEV] Routing: unanimity closes; disagreement and uncertainty route to review | T07 |
| T09 | [TEV] QA: deterministic sampling of unanimous and Not antisemitic rows | T08 |

### M2 — Review policy, confidence, training on v2 taxonomy

| # | Issue | Blocked by |
|---|---|---|
| T10 | [TEV] Review routing: disagreement-driven human review with QA sampling (epic) | T08 |
| T11 | [TEV] Confidence: replace the fixed 0.9 prior with a calibrated per-lane signal | T10 |
| T12 | [TEV] Training: retrain adapters on the v2 taxonomy with the full metadata schema | T03 |
| T13 | [TEV] Evaluation: trinity agreement-rate and miss-rate gate on the 102-row held-out set | T12 |

### M3 — Language foundation and capacity

| # | Issue | Blocked by |
|---|---|---|
| T14 | [TEV] Language foundation: per-language gold standards, Hungarian acceptance gate (epic) | T03 |
| T15 | [TEV] Hungarian: double-annotated gold set with kappa and adjudication records | T14 |
| T16 | [TEV] Throughput: parallel segment workers with memory budget and SLA capacity model (epic, **committed per D6**) | — |
| T17 | [TEV] SLA: 10:00 intake → next-business-day 12:00 batch runner | T16 |
| T24 | [TEV] Model advancement: continuous candidate bakeoff and promotion per lane and language (epic, **per D7**) | T13 |
| T25 | [TEV] Bakeoff harness: per-language candidate evaluation with promotion and rollback | T24 |

### M4 — TEV operations and handover

| # | Issue | Blocked by |
|---|---|---|
| T18 | [TEV] Handover: daily batch SLA and closed-channel delivery package (epic) | T17 |
| T19 | [TEV] Export: handover workbook — summary, source, context, proposed category, rationale, open question | T18 |
| T20 | [TEV] Escalation: priority cases and legal handoff record | T18 |
| T21 | [TEV] Learning: TEV-approved pattern updates with before/after verification (epic) | T13 |
| T22 | [TEV] Operations: access logging, backup/restore drill, closed-channel operation | T18 |
| T23 | [TEV] App: trinity vote display and handover export controls | T19 |

### Acceptance gates (run once, recorded, before go-live)

1. **Taxonomy gate:** every six-category historical row maps deterministically into the seven-category scheme with no loss; all 132+ tests pass.
2. **Trinity gate:** measured agreement rate between the three lanes on the held-out set; review volume projection from the disagreement rate; deliberation converts ≥ X% of disagreements into agreement (X set from the first measurement, not assumed).
3. **Miss-rate gate:** QA sampling reports the cleared-row miss rate per cycle; go-live only with a rate the TEV explicitly accepts.
4. **Hungarian gate:** Hungarian gold set passes the same acceptance standard as the German set (double annotation, kappa, adjudication) before any Hungarian production claim.
5. **SLA gate:** a full dry-run daily batch (intake → delivery package) completes inside the 26-hour window at agreed volume.
6. **Operations gate:** backup + restore drill passes; access log demonstrable; escalation record end-to-end without any legal decision made by the system.

---

### Acceptance gates (recall note for D-decision "a")

The disagreement-driven review policy (T10) is accepted **because** it ships only behind the miss-rate gate
(T09/T13): cleared rows are sampled deterministically, the miss rate is measured and reported every cycle,
and adoption is reversible through `SPOT_REVIEW_POLICY`. The system fails measurably, never silently.

---

## 9. Refactor map (where implementation will touch — not touched now)

| Component | Change |
|---|---|
| `ssot/ssot.json`, `ssot/SSOT.md` | Seven categories; optional secondary category; trinity lane model specs per language; routing policy `disagreement`. |
| `src/classifier.py` | Third evaluator lane; deliberation round (justify → re-vote); unanimity certificate; calibrated confidence source. |
| `src/failure_policy.py` | Routing on disagreement/uncertainty instead of all-suspicion; QA sampling extended to unanimous rows. |
| `src/models.py` | Secondary category field; deliberation trace schema. |
| `script/build_training_set.py`, `script/build_gold_sample.py`, `script/evaluate_adapter.py` | Seven-category labels, Holocaust-denial split, secondary-category targets, trinity evaluation metrics. |
| `backend/services/run_state_service.py`, `ops_db_service.py` | Review-queue semantics (disagreement items + QA samples); priority triage extended; escalation record. |
| `backend/main.py` | SLA batch endpoints; handover export endpoints; escalation endpoints; per-language run metadata. |
| `app/macos/` | Trinity vote + deliberation view; handover export controls; SLA status. |
| `docs/` | Taxonomy v2, TEV workflow, handover contract, runbooks, acceptance-gate records. |

---

## 10. Issue inventory on the board

All issues are on the `{spot} - From IDEA to LIVE` board (#5) with status `Todo (NEXT)`. Epics carry the `epic` label; implementation issues carry `feature`. Dependencies are recorded in the bodies and in the phase tables above.

| Code | Issue | Link |
|---|---|---|
| T01 | Taxonomy v2: seven categories and optional secondary category (epic) | [#85](https://github.com/moldovancsaba/spot/issues/85) |
| T02 | Contract: seven-category taxonomy in SSOT, prompts and deterministic fallback | [#86](https://github.com/moldovancsaba/spot/issues/86) |
| T03 | Data: re-label reference - Holocaust Denial split and secondary category support | [#87](https://github.com/moldovancsaba/spot/issues/87) |
| T04 | Testing: taxonomy migration regression | [#88](https://github.com/moldovancsaba/spot/issues/88) |
| T05 | Trinity: three independent evaluators with justification and re-vote (epic) | [#89](https://github.com/moldovancsaba/spot/issues/89) |
| T06 | Pipeline: third independent evaluator lane (language-tagged model set) | [#90](https://github.com/moldovancsaba/spot/issues/90) |
| T07 | Pipeline: deliberation round - justification, argument review, re-vote | [#91](https://github.com/moldovancsaba/spot/issues/91) |
| T08 | Routing: unanimity closes; disagreement and uncertainty route to review | [#92](https://github.com/moldovancsaba/spot/issues/92) |
| T09 | QA: deterministic sampling of unanimous and Not antisemitic rows | [#93](https://github.com/moldovancsaba/spot/issues/93) |
| T10 | Review routing: disagreement-driven human review with QA sampling (epic) | [#94](https://github.com/moldovancsaba/spot/issues/94) |
| T11 | Confidence: replace the fixed 0.9 prior with a calibrated per-lane signal | [#95](https://github.com/moldovancsaba/spot/issues/95) |
| T12 | Training: retrain adapters on the v2 taxonomy with the full metadata schema | [#96](https://github.com/moldovancsaba/spot/issues/96) |
| T13 | Evaluation: trinity agreement-rate and miss-rate gate on the held-out set | [#97](https://github.com/moldovancsaba/spot/issues/97) |
| T14 | Language foundation: per-language gold standards, Hungarian acceptance gate (epic) | [#98](https://github.com/moldovancsaba/spot/issues/98) |
| T15 | Hungarian: double-annotated gold set with kappa and adjudication records | [#99](https://github.com/moldovancsaba/spot/issues/99) |
| T16 | Throughput: parallel segment workers with memory budget and SLA capacity model (epic) | [#100](https://github.com/moldovancsaba/spot/issues/100) |
| T17 | SLA: 10:00 intake to next-business-day 12:00 batch runner | [#101](https://github.com/moldovancsaba/spot/issues/101) |
| T18 | Handover: daily batch SLA and closed-channel delivery package (epic) | [#102](https://github.com/moldovancsaba/spot/issues/102) |
| T19 | Export: handover workbook - summary, source, context, proposed category, rationale, open question | [#103](https://github.com/moldovancsaba/spot/issues/103) |
| T20 | Escalation: priority cases and legal handoff record | [#104](https://github.com/moldovancsaba/spot/issues/104) |
| T21 | Learning: TEV-approved pattern updates with before/after verification (epic) | [#105](https://github.com/moldovancsaba/spot/issues/105) |
| T22 | Operations: access logging, backup/restore drill, closed-channel operation | [#106](https://github.com/moldovancsaba/spot/issues/106) |
| T23 | App: trinity vote display and handover export controls | [#107](https://github.com/moldovancsaba/spot/issues/107) |
| T24 | Model advancement: continuous candidate bakeoff and promotion per lane and language (epic, D7) | [#108](https://github.com/moldovancsaba/spot/issues/108) |
| T25 | Bakeoff harness: per-language candidate evaluation with promotion and rollback | [#109](https://github.com/moldovancsaba/spot/issues/109) |

Board URL: https://github.com/users/moldovancsaba/projects/5
