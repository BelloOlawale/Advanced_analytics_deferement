---
id: ISS-006
title: VS2 - L1 deviation engine v1 (uptime), per station
type: vertical-slice
slice: VS2
status: backlog
priority: P0
depends_on: [ISS-004]
runtime: local-prototype
---
# ISS-006 — VS2: L1 deviation engine v1 (uptime)

## Why
The core hypothesis: an entity's own signal deviating from its own normal precedes loss. Start with the single most complete, most predictive signal: `uptimeproduction`.

## Goal / demo
- Per station, a learned baseline for `uptimeproduction` (median + MAD, seasonal).
- Daily deviation (`z`, and a simple threshold) -> a `gold.entity_deviation` row with a flag + reason.
- A view shows flagged days next to known event days for one station.

## In scope
- Baseline: robust location/scale per station (optionally day-of-week).
- z-score deviation + threshold; reason code "uptime vs own baseline".
- Persist `gold.entity_deviation` (station-day).

## Out of scope
- Other signals (ISS-007); modelling (ISS-009).

## Acceptance criteria
- [ ] Baseline computed per station from a clean window; no leakage of the scored day.
- [ ] Daily deviation + flag stored for all 5 stations.
- [ ] Flag rate is sane (not ~100%): a target false-positive rate is reported.
- [ ] Visual overlay of flags vs event days for >= 1 station.

## Tasks
- [ ] Implement robust baseline + z-score.
- [ ] Emit deviation table + reason.
- [ ] Produce overlay chart.
- [ ] Record baseline/flag parameters as config.

## Data / dependencies
`production_fact`; `silver` from ISS-004.

## Notes
Keep the method explainable; this is the shape all later slices reuse.
