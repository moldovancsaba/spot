# TEV go-live task list — mapping to {spot} delivery

**Source:** `SPOT_TEV_feladatlista.docx` (2026-11-17, client feedback round).
**Purpose:** each TEV task below gets a named owner, deadline and status when the joint launch starts. This file maps every task to the {spot} capability that serves it, marks what is TEV-side vs SPOT-side, and records the client's distribution warning.

## Client feedback that changes our assumptions

1. **TEV sends only rows they already found suspicious** — the production prior is *positive-heavy*
   ("large amounts of threats"). Our measured calibration table and gates were built on a balanced sample and
   a 14–23% positive live corpus. **Consequence:** no production claim, threshold or volume projection is
   valid until re-measured on the real data. The per-language check samples (task 07) are that measurement.
2. **Gold standards per language AND country, cross-referenced.** The gold-set protocol therefore keys on
   *locale* (language + country), and pattern proposals carry language and platform, so a pattern found in
   one locale can be proposed and verified in another.
3. **TEV will supply the threat definitions and categorisation rules** — the taxonomy (seven categories) is
   TEV's; our job is to enforce it deterministically and to re-measure whenever their rules change (tasks
   05, 06, 11, 12).

## Task mapping

| # | TEV task | Side | {spot} capability | State |
|---|---|---|---|---|
| 01 | Data owner and deputy named | TEV | operational record; tracked in run/action log | open |
| 02 | Sources and coverage recorded | TEV | intake accepts per-platform rows; coverage gaps noted in run metadata | open |
| 03 | Sample export + field description | TEV | intake validation (text + URL/platform + item id mandatory) | open |
| 04 | Handover schedule approved | TEV+SPOT | SLA deadlines + `pending/on_time/missed/delivered` status | **ready** |
| 05 | Seven categories confirmed with definitions and an approved example each | TEV | taxonomy v0.2 (seven categories); canonical naming updated from TEV's confirmed list | **ready for TEV input** |
| 06 | Edge cases and priority rules (quote, condemnation, satire, missing context; Holocaust-denial priority) | TEV | rubric already implements denial priority and quote/condemnation distinctions; TEV examples become regression fixtures | **ready for TEV input** |
| 07 | Multilingual expert check samples (10 items per language to start; Hebrew/Arabic marked) | TEV+SPOT | per-locale gates: `build_gold_sample` → `build_training_set` → `evaluate_adapter` / `measure_calibration` | **tooling ready, data pending** |
| 08 | False flags / misses review; acceptance criteria recorded before launch | TEV+SPOT | audit strata (`AUDIT_STRATUM_UNANIMOUS`/`CLEARED`) + review queue + handover workbook | **ready** |
| 09 | Expert owner, deputy, response times (1 business day normal / 2 hours priority) | TEV | escalation records carry urgency + expected response | **ready** |
| 10 | Review package + reply template; one trial case round-trip | TEV+SPOT | handover workbook + review_decision/reviewer_note (expert reply fields) | **ready** |
| 11 | New pattern flagging (pattern, language+platform, examples, counter-example, proposed handling, TEV decision); weekly review | both | `propose_pattern` records + approvals.jsonl + verify before/after | **ready** |
| 12 | Rule update approval + before/after measurement on the same approved sample | TEV+SPOT | `approve_cycle` + `verify_cycle` | **ready** |
| 13 | Closed channel + recipients + trial with revoke | TEV+SPOT | access log, backup/restore, handover endpoints | **ready** |
| 14 | Retention and deletion schedule per data type; email is notification only | TEV+SPOT | retention policy template below; deletion automation not built (documented gap) | **template ready** |
| 15 | Priority case notification trial (fictional case, real order/channels, no submission) | TEV+SPOT | escalation record + drill script | **ready** |
| 16 | Forwarding decision and closure (police submission: who, channel, confirmation) | TEV | escalation record fields for decision/channel/confirmation | **ready** |
| 17 | Result package acceptance: retrievable row numbers, summary of processed/error/review, machine vs expert separate | TEV | handover workbook (case id, row numbers, summary counts, separate expert fields) | **ready** |
| 18 | Defect log + phone escalation rules + missed-handover drill | both | action log + SLA missed status; runbook section | **ready** |
| 19 | Go-live decision preparation | TEV+SPOT | acceptance gates in IMPLEMENTATION_PLAN_TEV_2026-11-16.md §8 | **ready** |
| 20 | Fifth-workday review metrics | TEV+SPOT | learning report cadence + metrics template below | **ready** |

## Recording templates (to be filled by the named owners at launch)

### Task 02 — sources
`Platform | watched source or search | language | country | period | known coverage gaps`

### Task 05 — categories
`Category | when it applies | when it does not | one approved example` (one row per category; TEV order)

### Task 06 — edge cases
`Item id | context | expected primary category | reason | human review required?`

### Task 07 — check samples
`Language | country | item id | expected label | reason | labeller` — start with 10 items per locale; Hebrew and Arabic samples marked explicitly.

### Task 08 — acceptance criteria (record before launch)
`False-flag rate (flagged but not antisemitic) | miss rate (antisemitic but closed) | sample sizes | acceptance threshold | decision`

### Task 11 — pattern proposal
`Pattern | language + platform | two interpretable examples | known counter-example | proposed handling | TEV decision`

### Task 14 — retention schedule
`Data type | who can access | approved retention period | deletion owner | exception approver`
(email carries notification only; no source data in email.)

### Task 15/16 — priority case
`Case id | original source | snapshot + timestamp | factual description | urgency | primary recipient | deputy | receipt time`
Decision record: `Decision + reason | approver | sender | recipient | channel | timestamp | confirmation` — drill uses a fictional case, no real submission.

### Task 20 — fifth-workday metrics
`Indicator | expected value | measured value | deviation | action | owner | deadline` plus the next review date.

## Explicit gaps (not built; not claimed)

- Automated retention/deletion enforcement (task 14): the schedule template exists; deletion automation is a
  deliberate future item and must be approved by TEV before implementation.
- Actual closed-channel transport (task 13): artifacts are generated with integrity manifests; the transport
  itself is the agreed external channel, not part of the local system.
