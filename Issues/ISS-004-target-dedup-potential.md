---
id: ISS-004
title: Target dedup + versioned potential
type: enabler
slice: foundation
status: backlog
priority: P0
depends_on: [ISS-001]
runtime: local-prototype
---
# ISS-004 — Target dedup + versioned potential

## Why
`target_oil` is a **station-level value repeated on every string row**; naive summation inflates it ~15×. `potential` and gap-to-target must be computed correctly and versioned.

## Goal / demo
- `silver.production_day` with `target_oil` deduplicated per station-day and `potential = actual + deferred`.
- A comparison shows naive vs dedup vs (if available) well-model potential.

## In scope
- Deduplicate `target_oil`/`target_gross` to station-day (`max`).
- `potential_oil` versioned (method column) — proxy = actual + deferred until a true allowed/potential exists.
- Gap-to-target and deferment % per station-day.

## Out of scope
- Sourcing a true well-model potential (client dependency).

## Acceptance criteria
- [ ] Station-day target deduped and documented.
- [ ] `potential_oil` + `potential_method` columns present.
- [ ] Naive-vs-correct target comparison produced.
- [ ] deferment % per station matches the cross-station ranking already observed.

## Tasks
- [ ] Implement dedup + potential in `silver`.
- [ ] Add tests (target constant per station-day; potential >= actual).
- [ ] Document method + version.

## Data / dependencies
`production_fact`; optional true potential from client.

## Notes
Observed correct targets: EFE ~950k, Ekulama1 ~11.69M over 24 mo.
