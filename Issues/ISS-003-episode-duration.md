---
id: ISS-003
title: Episode & duration reconstruction
type: enabler
slice: foundation
status: backlog
priority: P1
depends_on: [ISS-001]
runtime: local-prototype
---
# ISS-003 — Episode & duration reconstruction

## Why
`deferment_fact` has one row per event-day and no start/end, so frequency × duration decomposition and MTBF are impossible. Reconstructed episodes unlock them.

## Goal / demo
- For each station/string/cause, collapse consecutive event-days into **episodes** with `start_date`, `end_date`, `duration_days`, `events`.
- A report shows episode count vs event count and duration distribution.

## In scope
- Islands-and-gaps reconstruction per (flowstation, productionstring, cause).
- Flag reconstruction as **approximate** where data is sparse/gappy.
- Feed episode duration into features and recurrence.

## Out of scope
- Adding real `start_ts`/`end_ts` to source (client change — recommend, do not perform).

## Acceptance criteria
- [ ] `silver.deferment_episode` produced with start/end/duration.
- [ ] Reconciliation: Σ event-days = Σ episode duration days.
- [ ] Duration distribution per cause group.
- [ ] Limitation documented.

## Tasks
- [ ] Implement islands-and-gaps in duckdb/Spark.
- [ ] Validate against known multi-day causes.
- [ ] Publish episode table + distribution view.

## Data / dependencies
`deferment_fact` (daily).

## Notes
Quality bounded by daily granularity; higher frequency later (ISS-014).
