# Ops runbook — defect handling, missed handovers, escalation (go-live task 18)

## Defect log

One joint defect location, one entry per defect. Entry template:

`Run or file id | timestamp | symptom | impact | responsible | next status time`

Classification:
- **No rows processed** (intake broken): check upload validation; phone the deputy immediately.
- **Segment failure**: isolated per segment now (one failure no longer fails the queue); the run finalises
  FAILED with the precise segment list; heal (`POST /runs/{id}/heal`) requeues only the failed segments.
- **Missed handover**: see below.

## Phone escalation rules

| Situation | Phone call |
|---|---|
| Intake did not arrive by 10:00 (workday) | yes — data owner deputy |
| Backend/worker down > 30 min during a batch window | yes — SPOT operator |
| Priority case (suspected crime) | yes — TEV legal owner first, then deputy, per the approved task 15 order |
| Any single segment failure | no — heal path; report in the defect log |

## Missed-handover drill

1. Simulate by setting a delivery deadline in the past: `POST /runs/{id}/sla`.
2. `GET /runs/{id}/sla` must report `missed`.
3. Run `script/weekly_metrics.py --run-id <id>` — the SLA row shows `missed` with the deviation column to fill.
4. Record the drill in the defect log with the resolution (reschedule or manual delivery).

## Backup/restore drill (deck p.11)

1. `script/backup_runs.py backup --runs-dir runs --backup-dir backups`
2. Verify the manifest exists; restore into a scratch directory and check integrity.
3. Record the drill result in the go-live checklist before launch.
