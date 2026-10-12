---
id: ISS-002
title: Cause taxonomy normalisation + completeness KPI
type: enabler
slice: foundation
status: backlog
priority: P0
depends_on: [ISS-001]
runtime: local-prototype
---
# ISS-002 — Cause taxonomy normalisation + completeness KPI

## Why
86.2% of deferment events carry no usable cause code (`Mismatch`). Cause-specific analysis and modelling are impossible until raw drivers map to a canonical hierarchy.

## Goal / demo
- A mapping table maps raw drivers / codes → canonical **L1 group** and **L2 cause**.
- A report shows **before/after % classified**, per station and overall.

## In scope
- Define canonical cause hierarchy (L1 groups: equipment/rotating, facility/utilities, well/subsurface, flowline/export, planned, third-party).
- Map the ~60 raw drivers to the hierarchy (explicit mapping table).
- Detect the upstream mapping failure that sends everything to `Mismatch`; document the fix owner.
- Completeness KPI per station/month.

## Out of scope
- Fixing the upstream ETL (owned by NewCross) — we specify and measure.

## Acceptance criteria
- [ ] Mapping table (raw → L1 → L2) exists and is versioned.
- [ ] Pipeline computes % classified before and after mapping.
- [ ] Per-station completeness report.
- [ ] Root cause of `Mismatch` documented with a named owner and fix path.

## Tasks
- [ ] Extract distinct raw driver values + current dim names.
- [ ] Build mapping table (reviewed with client).
- [ ] Add completeness metric to DQ suite.
- [ ] Write short "taxonomy gap" note for the client.

## Data / dependencies
`deferment_fact`, `deferment_category_dim`, `deferment_subcategory_dim`; Discovery input on raw drivers.

## Notes
Target ≥ 95% classified. **Not a blocker for L1** (precursor-based) early warning.
