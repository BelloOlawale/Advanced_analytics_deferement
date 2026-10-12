---
id: ISS-007
title: VS3 - L1 deviation v2 (all signals, EWMA/CUSUM, reasons, change-point)
type: vertical-slice
slice: VS3
status: backlog
priority: P0
depends_on: [ISS-006]
runtime: local-prototype
---
# ISS-007 — VS3: L1 deviation v2 (all signals)

## Why
One signal is not enough, and slow drifts need sensitive detectors. Generalise the engine to all precursors and catch gradual deterioration earlier.

## Goal / demo
- Deviation for `uptimeproduction`, `thp`, `bean`, `water_rf`, oil-vs-target, event frequency.
- Detectors: z-score + **EWMA** + **CUSUM** + change-point.
- A ranked "current risk" view per station with the top reason(s).

## In scope
- Per-entity baselines for all signals (null-tolerant).
- z / EWMA / CUSUM / change-point, combined into a station risk signal.
- Reason list (which signals deviated, direction, magnitude).
- `gold.entity_deviation` extended to all signals.

## Out of scope
- Learned onset model (ISS-009); value ranking (ISS-010).

## Acceptance criteria
- [ ] All signals produce baselines + deviations for all stations/strings.
- [ ] Combined score + top reasons available per entity-day.
- [ ] Documented sensitivity (how much earlier vs raw threshold).
- [ ] Missing-data handled explicitly (no silent zeros).

## Tasks
- [ ] Add EWMA/CUSUM/change-point.
- [ ] Combine signals into a score with reasons.
- [ ] Compare detectors on lead time (feeds ISS-008).
- [ ] Config-as-data for params.

## Data / dependencies
`production_fact`, `deferment_fact`.

## Notes
Handle `thp` (-23% null) and `bean` (-27% null) gracefully.
