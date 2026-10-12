---
id: ISS-005
title: VS1 - Station-day deferment mart + cross-station ranking view
type: vertical-slice
slice: VS1
status: backlog
priority: P0
depends_on: [ISS-004]
runtime: local-prototype
---
# ISS-005 — VS1: Station-day deferment mart + cross-station ranking view

## Why
First end-to-end (tracer-bullet) slice. Gives a fair, per-station view of loss over time — the baseline every later slice builds on. Demonstrates the full path data -> feature -> view.

## Goal / demo
- One command produces `gold.station_day` (per station x day: actual, target, deferred, deferment %, events).
- A view/report ranks stations by deferment % and gap-to-target with a 24-month trend.

## In scope
- Build `gold.station_day` from `silver` outputs.
- Cross-station normalisation: deferment % of potential, events per 1,000 bbl.
- A simple chart/table output (chart first; Power BI later).

## Out of scope
- Any modelling or alerting.

## Acceptance criteria
- [ ] `gold.station_day` materialised for 2024-10-01 -> 2026-10-07.
- [ ] Per-station ranking reproduces: EFE 26.2% > OML147 14.0% > Ekulama2 11.1% > Awoba 7.5% > Ekulama1 6.0%.
- [ ] Trend view renders for the 24-month window.
- [ ] Row-count and date-coverage checks pass.

## Tasks
- [ ] Build station_day mart.
- [ ] Add ranking + trend output.
- [ ] Smoke tests on known totals.

## Data / dependencies
`deferment_fact`, `production_fact`, `flowstations_dim`.

## Notes
This slice is largely already prototyped ad hoc - formalise it into a repeatable artefact.
