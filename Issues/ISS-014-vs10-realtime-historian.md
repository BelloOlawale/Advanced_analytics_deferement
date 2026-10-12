---
id: ISS-014
title: VS10 - Real-time historian ingestion -> hourly risk (future)
type: vertical-slice
slice: VS10
status: backlog
priority: P2
depends_on: [ISS-013]
runtime: fabric
---
# ISS-014 — VS10: Real-time historian ingestion

## Why
Daily process data has **no precursor for abrupt causes** (Power Trip, Facility Shutdown). Hourly historian signals are the path to warning on those and to shorter lead times overall.

## Goal / demo
- Hourly THP / WHP / FLP / bean / power signals flow via Eventstream into an Eventhouse.
- The deviation engine runs on a sliding window; hourly risk appears for at least one station.
- Demonstrated lead vs the daily-only baseline for an abrupt cause.

## In scope
- Eventstream + Eventhouse ingestion of historian (hourly or better).
- Hourly feature/deviation computation reusing the same contracts.
- Sliding-window scoring + alert path.
- Comparison: daily vs hourly lead time.

## Out of scope
- Full asset coverage; sub-minute control-room integration.

## Acceptance criteria
- [ ] Historian stream lands and is queryable at hourly grain.
- [ ] Hourly deviation + risk produced for >= 1 station.
- [ ] Measured lead-time improvement (or a documented null result) vs daily.
- [ ] Capacity/latency within agreed limits.

## Tasks
- [ ] Confirm historian interface + frequency.
- [ ] Build Eventstream -> Eventhouse path.
- [ ] Reuse deviation/score logic at hourly grain.
- [ ] Compare to daily baseline.

## Data / dependencies
Historian feed (client); Eventstream/Eventhouse; ISS-013 platform.

## Notes
Blocked on historian availability/frequency (PRD open question 3).
