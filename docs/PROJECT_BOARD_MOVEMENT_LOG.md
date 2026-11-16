# Project board review and manual movement / Scrum journal

Reviewed: 2026-11-15 UTC. Repository: moldovancsaba/spot.

Canonical board: [project board](https://github.com/users/moldovancsaba/projects/5). **The board is the owner's source of truth and is read-only. Never add, remove, reorder or move cards or edit project fields.** This file records observations and conditional proposals for manual owner decisions only.

## Verified coverage and limitations

- Repository collection: 84 entries, including 83 issues and 1 pull requests; 74 issues are open.
- Board: all 45 returned items were read; totalCount matches the captured item count.
- Linked issue-state / Done-status discrepancies: 0. Open issues absent from this board snapshot: 35. Absence here does not prove absence from every board and does not authorize creating a card.
- Exact title-and-body duplicate groups among open issues: 0. Similar titles alone were not treated as duplicates.
- Issue and board reads succeeded. No access failure was observed for these captured collections. No board write was attempted.
- This is a documentation-only review. The required model-free contract suite passed (132 tests), and Python syntax compilation passed. No production flow, user data mutation, external message, dependency upgrade or deployment action was performed. Source presence and previous Done status are not fresh acceptance evidence.

## Source observations and work clusters

### Existing native and execution foundations

The current workspace is 0.5.2; shipped release notes remain 0.3.1. The native-only macOS operator surface supersedes the older browser-shell implementation framing in #1–#16; retain actual workflow, permissions, recovery, row inspection and artifact acceptance rather than rebuilding a second browser product by default. #19's observational read-model work is closed and documented; canonical rows, attempts and queue implementation already exist, so #17/#20–#24 require remaining migration/transactional/recovery evidence, not assumed greenfield persistence. Model-free backend tests cannot establish native client or inference acceptance.

### Model modernization must preserve the governed contract

Newer local models are benchmark candidates, not automatic replacements for the SSOT-selected classifier/fallback/judge routes. Preserve one language per run, one validated closed-taxonomy category per row, local-first processing, source-preserving drafts, explicit failure review and reproducible audit artifacts. READMEDEV and HANDOVER record that client acceptance remains pending; startup readiness is distinct from inference readiness. No workbook, personal records, local model service or client machine was accessed.

### Idea clusters and distinct safeguards

#25/#27/#28 separate policy versioning, severity and automation thresholds from taxonomy labels; do not silently expand taxonomy or mark low-confidence results verified. #32/#34/#35/#36/#39 concern narrative clustering, metadata and drift: embeddings or local summaries require labeled evaluation and traceable source evidence, without automatically changing canonical classification. #37/#38/#42 concern QA sampling, correction export and appeals; preserve human adjudication and prevent failed/escalated outputs entering learning data. #30/#31/#44 concern reports, cases and compliance bundles: reuse canonical run/row manifests and verify hashes/access boundaries. Watchlists and repeat-source/actor proposals require explicit product and privacy scope, not inferred identity claims. Similar goals were not treated as exact duplicates. None of these items was closed or moved here. Absolute macOS paths in older documentation are environment-specific and do not prove those resources exist in this Linux checkout.

Inspected sources: [README.md](../README.md), [READMEDEV.md](../READMEDEV.md), [docs/HANDOVER.md](../docs/HANDOVER.md), [backend/services/run_state_service.py](../backend/services/run_state_service.py), [script/verify-contracts.sh](../script/verify-contracts.sh). Documentation paths and register coverage were checked before publication. No new technology is selected or installed by this assessment.

## Per-card review register

A destination is a proposal, never an executed move. Historical closed cards stay historical; migrated or not-planned closures do not prove feature delivery. Open work remains subject to its issue's acceptance criteria and owner decision.

| Issue / card | Title | Issue state / reason | Observed current column | Proposed destination / next evidence | Owner decision / manual execution |
| --- | --- | --- | --- | --- | --- |
| [#3](https://github.com/moldovancsaba/spot/issues/3) | {spot}: Refactor onto one canonical execution and review state model | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#14](https://github.com/moldovancsaba/spot/issues/14) | {spot}: Prepare browser acceptance evidence and release-candidate package | closed / not_planned | Done | Remain; preserve historical evidence, no fresh completion claim. | Pending / not executed |
| [#16](https://github.com/moldovancsaba/spot/issues/16) | {spot}: Complete browser release cutover and post-release handover | closed / not_planned | Done | Remain; preserve historical evidence, no fresh completion claim. | Pending / not executed |
| [#17](https://github.com/moldovancsaba/spot/issues/17) | {spot}: Persist canonical run-row results and migration paths | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#18](https://github.com/moldovancsaba/spot/issues/18) | {spot}: Make segment execution transactional at row commit boundaries | open / unspecified | Todo (NEXT) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#19](https://github.com/moldovancsaba/spot/issues/19) | {spot}: Make read models side-effect free and centralize state resolution | closed / completed | Done | Remain; preserve historical evidence, no fresh completion claim. | Pending / not executed |
| [#20](https://github.com/moldovancsaba/spot/issues/20) | {spot}: Unify review state and reviewer persistence | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#21](https://github.com/moldovancsaba/spot/issues/21) | {spot}: Standardize progress, ETA, and metrics semantics | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#22](https://github.com/moldovancsaba/spot/issues/22) | {spot}: Introduce explicit run-attempt lifecycle and recovery semantics | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#23](https://github.com/moldovancsaba/spot/issues/23) | {spot}: Consolidate native app and backend state models | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#24](https://github.com/moldovancsaba/spot/issues/24) | {spot}: Harden artifact manifests and audit contract coverage | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#50](https://github.com/moldovancsaba/spot/issues/50) | {spot}: Deliver DB-first ingest and bounded self-learning architecture | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#51](https://github.com/moldovancsaba/spot/issues/51) | {spot}: Define the canonical intake row schema and provenance contract | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#52](https://github.com/moldovancsaba/spot/issues/52) | {spot}: Introduce importer adapters, staging, and normalization diagnostics | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#53](https://github.com/moldovancsaba/spot/issues/53) | {spot}: Add CSV, JSON, TXT, API, and CLI intake on the canonical importer framework | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#54](https://github.com/moldovancsaba/spot/issues/54) | {spot}: Make canonical DB rows the only live classification input contract | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#55](https://github.com/moldovancsaba/spot/issues/55) | {spot}: Add governed export adapters from canonical rows | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#56](https://github.com/moldovancsaba/spot/issues/56) | {spot}: Persist operator feedback as governed learning candidates | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#57](https://github.com/moldovancsaba/spot/issues/57) | {spot}: Add offline evaluation and candidate promotion gates | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#58](https://github.com/moldovancsaba/spot/issues/58) | {spot}: Add Apple-Silicon local fine-tuning with MLX LoRA and QLoRA | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#59](https://github.com/moldovancsaba/spot/issues/59) | {spot}: Add a candidate model registry with promotion and rollback controls | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#60](https://github.com/moldovancsaba/spot/issues/60) | {spot}: Add an active-learning review queue | open / unspecified | Roadmap (LATER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#61](https://github.com/moldovancsaba/spot/issues/61) | {spot}: Enforce immutable row lineage between upload_rows and run_rows | closed / completed | Done | Remain; preserve historical evidence, no fresh completion claim. | Pending / not executed |
| [#62](https://github.com/moldovancsaba/spot/issues/62) | {spot}: Make segment claims atomic and concurrency-safe | closed / completed | Done | Remain; preserve historical evidence, no fresh completion claim. | Pending / not executed |
| [#63](https://github.com/moldovancsaba/spot/issues/63) | {spot}: Fail fast on managed upload and recovery relation drift | closed / completed | Done | Remain; preserve historical evidence, no fresh completion claim. | Pending / not executed |
| [#64](https://github.com/moldovancsaba/spot/issues/64) | Documentation: Browser history archive - Preserve historical links | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#65](https://github.com/moldovancsaba/spot/issues/65) | Documentation: Runtime terminology - Align active descriptions with behavior | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#66](https://github.com/moldovancsaba/spot/issues/66) | API: Contract inventory - Preserve native and artifact interfaces | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#67](https://github.com/moldovancsaba/spot/issues/67) | Native: API compatibility - Verify supervisor and operator contracts | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#68](https://github.com/moldovancsaba/spot/issues/68) | Testing: Runtime API smoke - Isolated contract verification | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#69](https://github.com/moldovancsaba/spot/issues/69) | Architecture: State inventory - Define authority and recovery inputs | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#70](https://github.com/moldovancsaba/spot/issues/70) | Persistence: Legacy migration - Explicit resumable import | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#71](https://github.com/moldovancsaba/spot/issues/71) | Artifacts: Evidence publication - Crash-safe versioned snapshots | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#72](https://github.com/moldovancsaba/spot/issues/72) | Testing: Recovery fault injection - Preserve inputs and evidence | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#73](https://github.com/moldovancsaba/spot/issues/73) | Runtime: Provenance - Capture per-attempt execution identity | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#74](https://github.com/moldovancsaba/spot/issues/74) | Research: Candidate isolation - Define bounded offline evaluation contract | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#75](https://github.com/moldovancsaba/spot/issues/75) | Governance: Candidate promotion - Specify approval and rollback | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#76](https://github.com/moldovancsaba/spot/issues/76) | Documentation: Audit claims - Bound reproducibility and learning | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#77](https://github.com/moldovancsaba/spot/issues/77) | Evaluation: Targeted adjudication - Compare category authority policies | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#78](https://github.com/moldovancsaba/spot/issues/78) | Design system: SwiftUI integration - Verify native GDS mapping | open / unspecified | IDEABANK (SOMEDAY) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#79](https://github.com/moldovancsaba/spot/issues/79) | Operations: Classification safeguards - Review failure and invalid-output flags | open / unspecified | Review (ALMOST) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#80](https://github.com/moldovancsaba/spot/issues/80) | Classification: Failure outcomes - Prevent unreviewed fallback negatives | open / unspecified | In Progress (NOW) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#81](https://github.com/moldovancsaba/spot/issues/81) | Classification: Model provenance - Prevent false second-pass confirmation | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#82](https://github.com/moldovancsaba/spot/issues/82) | Taxonomy: Annotation contract - Define antisemitism category boundaries | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#83](https://github.com/moldovancsaba/spot/issues/83) | Evaluation: Pairing integrity - Verify frozen inputs and complete coverage | open / unspecified | Backlog (SOONER) | Remain; satisfy original issue acceptance before proposing Review or Done. | Pending / not executed |
| [#49](https://github.com/moldovancsaba/spot/issues/49) | {spot}: Add a cluster-level trend dashboard across workbooks | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#48](https://github.com/moldovancsaba/spot/issues/48) | {spot}: Add plain-language search and Q&A over prior runs | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#47](https://github.com/moldovancsaba/spot/issues/47) | {spot}: Add a downstream webhook or case-export bridge | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#46](https://github.com/moldovancsaba/spot/issues/46) | {spot}: Add an OCR-ready upstream text ingest contract | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#45](https://github.com/moldovancsaba/spot/issues/45) | {spot}: Add AI-generated text suspicion flagging | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#44](https://github.com/moldovancsaba/spot/issues/44) | {spot}: Add compliance evidence bundles per run | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#43](https://github.com/moldovancsaba/spot/issues/43) | {spot}: Add a rule simulator and dry-run mode | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#42](https://github.com/moldovancsaba/spot/issues/42) | {spot}: Add an appeals and second-review workflow | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#41](https://github.com/moldovancsaba/spot/issues/41) | {spot}: Add analyst watchlists for phrases, entities, and narratives | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#40](https://github.com/moldovancsaba/spot/issues/40) | {spot}: Add repeat-source and repeat-actor fingerprinting | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#39](https://github.com/moldovancsaba/spot/issues/39) | {spot}: Add cross-run benchmark and drift scoring | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#38](https://github.com/moldovancsaba/spot/issues/38) | {spot}: Add active-learning exports from reviewer corrections | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#37](https://github.com/moldovancsaba/spot/issues/37) | {spot}: Add a reviewer QA sampling queue | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#36](https://github.com/moldovancsaba/spot/issues/36) | {spot}: Add context-aware classification from adjacent metadata | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#35](https://github.com/moldovancsaba/spot/issues/35) | {spot}: Add a custom narrative and trope tagging layer | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#34](https://github.com/moldovancsaba/spot/issues/34) | {spot}: Add weekly AI summaries of key shifts and clusters | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#33](https://github.com/moldovancsaba/spot/issues/33) | {spot}: Add narrative spike and anomaly alerts | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#32](https://github.com/moldovancsaba/spot/issues/32) | {spot}: Add duplicate and near-duplicate clustering | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#31](https://github.com/moldovancsaba/spot/issues/31) | {spot}: Add an analyst case view with lifecycle history | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#30](https://github.com/moldovancsaba/spot/issues/30) | {spot}: Add transparency-report exports | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#29](https://github.com/moldovancsaba/spot/issues/29) | {spot}: Add a trusted-flagger intake lane | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#28](https://github.com/moldovancsaba/spot/issues/28) | {spot}: Add confidence-based automation profiles | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#27](https://github.com/moldovancsaba/spot/issues/27) | {spot}: Separate severity scoring from taxonomy labels | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#26](https://github.com/moldovancsaba/spot/issues/26) | {spot}: Add rapid incident packs for emerging antisemitic narratives | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#25](https://github.com/moldovancsaba/spot/issues/25) | {spot}: Add policy profile versioning and threshold sets | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#11](https://github.com/moldovancsaba/spot/issues/11) | {spot}: Establish the browser design system and responsive UX baseline | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#10](https://github.com/moldovancsaba/spot/issues/10) | {spot}: Add operator-safe error handling, retry, cancel, and recovery flows | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#9](https://github.com/moldovancsaba/spot/issues/9) | {spot}: Establish local browser auth and operator permissions | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#8](https://github.com/moldovancsaba/spot/issues/8) | {spot}: Build the output and audit artifact download center | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#7](https://github.com/moldovancsaba/spot/issues/7) | {spot}: Add a row inspector with explanations, evidence, and annotations | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#6](https://github.com/moldovancsaba/spot/issues/6) | {spot}: Build the review queue for flagged rows and reviewer triage | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#5](https://github.com/moldovancsaba/spot/issues/5) | {spot}: Add a run detail surface with live status and operator actions | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#4](https://github.com/moldovancsaba/spot/issues/4) | {spot}: Build the browser app shell and operations dashboard baseline | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#2](https://github.com/moldovancsaba/spot/issues/2) | {spot}: Build workbook upload intake and browser submission flow | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |
| [#1](https://github.com/moldovancsaba/spot/issues/1) | {spot}: Define the browser operator workflow and UX acceptance contract | open | Not on this board | No card change; inspect associated tracking and acceptance evidence. | Pending / not executed |

## Append-only Scrum / manual movement journal

| Date / Scrum reference | Board and issue | Verified current column | Proposed destination | Evidence / rationale | Dependency / blocker | Owner decision | Manual execution / person | Verified new column | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-15 review | Board and issues above | Snapshot above | No automatic move | Recorded source/issue/board review | See unresolved requirements | Pending | Not executed | Snapshot only | Preserve history |
| YYYY-MM-DD / meeting link | Board URL + issue URL | Exact observed value | Exact proposed value or remain | Acceptance link | Specific condition | Pending | Not executed | Not verified | — |

Read the issue and actual board before each future proposal. Retain previous observations when a decision changes. Record execution only after the owner performs it and the result is read back. Documentation rollback requires no product or board rollback.

Verification limitation: the environment emitted a Starlette httpx deprecation warning; target-machine native/inference/client acceptance was not run. No app source changed.

## 2026-11-16 — Owner-authorized board update (TEV implementation plan)

The standing rule above ("board is read-only, never add cards") is superseded for this one action by the
owner's direct instruction of 2026-11-16: "all issues updated on the gh repository project board" as part of
the TEV implementation planning.

Automated, scripted addition (not manual movement of existing cards):

- 23 new issues created in `moldovancsaba/spot`: #85–#107 (T01–T23), titles prefixed `[TEV]`.
- Labels: `epic` for T01/T05/T10/T14/T16/T18/T21; `feature` for the rest.
- All 23 added to board #5 and set to `Todo (NEXT)`. No existing card was moved, reordered, edited or closed.
- Source of truth for the plan: `docs/IMPLEMENTATION_PLAN_TEV_2026-11-16.md` (committed same day; contains the
  full measured current state, the decision log D1–D5, phases M0–M4, risks, non-goals and the issue map).

Review of existing cards performed in this pass: none moved. This section is the audit record of the
addition; the per-card register above is unchanged.
