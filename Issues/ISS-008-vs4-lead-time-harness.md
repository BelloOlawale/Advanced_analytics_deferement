---
id: ISS-008
title: VS4 - Lead-time measurement harness (the proof slice)
type: vertical-slice
slice: VS4
status: backlog
priority: P0
depends_on: [ISS-003, ISS-007]
runtime: local-prototype
---
# ISS-008 — VS4: Lead-time measurement harness

## Why
This is the slice that **proves "earlier"**. It converts the deviation engine into a measured number: how many days before a coded onset does a flag fire, and at what false-alarm cost.

## Goal / demo
- For each coded cause group, a table: **median lead time (days)**, hit rate, false alarms per station per week.
- A backtest report, chronological, with the alert budget made explicit.

## In scope
- Align deviation flags with coded **onsets** (episode starts, ISS-003).
- Compute lead time distribution per cause group and per station.
- Report recall at fixed alert budget; report false alarms.
- Sensitivity table across thresholds/horizons.

## Out of scope
- Learned model (ISS-009); alert delivery (ISS-011).

## Acceptance criteria
- [ ] Lead-time table produced for >= 3 cause groups (e.g. Well No-Flow, Engine Failure, Flowline leak).
- [ ] False-alarm rate stated per station per week.
- [ ] Chronological backtest (no random split / leakage).
- [ ] One-line headline per cause: "N days early at F false alarms/week".

## Tasks
- [ ] Build onset set from ISS-003, filter to coded causes.
- [ ] Match flags to onsets; compute lead time.
- [ ] Sweep thresholds/horizons -> sensitivity table.
- [ ] Write backtest report.

## Data / dependencies
`gold.entity_deviation` (ISS-007), episode onsets (ISS-003).

## Notes
Expected (from precursor study): Well No-Flow and Flowline leak should show multi-day lead; Power Trip likely none until historian data exists.
