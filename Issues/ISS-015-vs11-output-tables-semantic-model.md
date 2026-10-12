---
id: ISS-015
title: VS11 - Gold output tables + semantic model (DirectLake) + measures
type: vertical-slice
slice: VS11
status: backlog
priority: P0
depends_on: [ISS-010]
runtime: fabric
---
# ISS-015 — VS11: Gold output tables + semantic model + measures

## Why
The findings only matter if they land somewhere the business can consume. This slice turns the daily risk output into a governed set of Delta tables and a semantic model that Power BI reads directly.

## Goal / demo
- The gold output tables exist as Delta: `risk_daily`, `deviation_daily`, `alert`, `station_day`, and dimensions.
- A **DirectLake semantic model** sits over them with a defined star schema.
- Core measures return correct numbers in a blank report:
  - count and value of risks, median lead time, alert precision, false alarms per station per week, coverage.

## In scope
- Materialise the gold output tables with the agreed schema (PRD §12.5).
- Build the star schema: facts vs dimensions, relationships, hierarchies (asset → station → well).
- Create the semantic model with DirectLake; Import fallback if required.
- Define measures (DAX) and mark the date dimension.

## Out of scope
- Report page design (ISS-016); publishing/RLS (ISS-017).

## Acceptance criteria
- [ ] All output tables materialised and refreshable.
- [ ] DirectLake model connects and renders; relationships validated (no ambiguous joins).
- [ ] Every measure reconciles with a hand-checked query for one station-day.
- [ ] Model documented (tables, relationships, measures).

## Tasks
- [ ] Finalise output schemas.
- [ ] Build the model + relationships + date table.
- [ ] Write and test measures.
- [ ] Document the model.

## Data / dependencies
`risk_daily` and related gold tables (ISS-010); Fabric workspace.

## Notes
DirectLake keeps refresh near-instant and avoids data copies.
