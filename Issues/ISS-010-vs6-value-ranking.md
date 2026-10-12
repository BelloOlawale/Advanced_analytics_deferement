---
id: ISS-010
title: VS6 - L3 value ranking + tiering -> risk_daily + Power BI view
type: vertical-slice
slice: VS6
status: backlog
priority: P0
depends_on: [ISS-005, ISS-006]
runtime: local-prototype
---
# ISS-010 — VS6: L3 value ranking + tiering

## Why
Alerts must be ranked by **money at stake**, not just probability, and surfaced where people work.

## Goal / demo
- `gold.deferment_risk_daily` per station-day: risk, tier (Red/Amber/Green), top reasons, expected bbl, expected USD.
- A Power BI (or report) view: stations ranked by expected value, drill to string, cause heatmap.

## In scope
- Value = risk signal x expected bbl x oil price.
- Expected bbl from recent loss run-rate (later from a severity model).
- Tiering rules (config) + reason list.
- Power BI station view (or interim report) reading the gold table.

## Out of scope
- Push alerts (ISS-011); learned risk (uses L1 until ISS-009).

## Acceptance criteria
- [ ] `gold.deferment_risk_daily` populated with risk, tier, reasons, bbl, USD.
- [ ] `oil_prices` joined for the money term.
- [ ] Ranked station view + drill-to-string works.
- [ ] Tier thresholds live in config, not code.

## Tasks
- [ ] Pull `oil_prices` (tiny) into the mart.
- [ ] Implement value + tiering.
- [ ] Build the ranked view.
- [ ] Config table for thresholds.

## Data / dependencies
`gold.station_day`, `gold.entity_deviation`, `oil_prices`, `flowstations_dim`.

## Notes
First slicing of money-at-risk; refine once L2 exists.
