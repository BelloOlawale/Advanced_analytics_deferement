# Issues — Deferment Early-Warning System

Work items derived from `docs/prd-deferment-early-warning.md`.
Each issue is a **vertical slice** or an **enabler**, written so it can be run end-to-end.

## Workflow
- `Issues/` — open work (one file per issue: `ISS-XXX-<slug>.md`).
- `Issues/Done/` — completed issues (move the file when acceptance criteria pass).
- Status lives in each file's front matter (`status: backlog | in-progress | blocked | done`).

## Vertical-slice rule
Every slice delivers a **thin end-to-end increment** — data → feature → score → surface —
and is independently demoable. No issue delivers only a layer.

## Order (see PRD §12)
| Issue | Slice | Deliverable | Status |
|---|---|---|---|
| ISS-001 | Enabler | Read-only access + DQ gate | backlog |
| ISS-002 | Enabler | Cause taxonomy normalisation + completeness KPI | backlog |
| ISS-003 | Enabler | Episode & duration reconstruction | backlog |
| ISS-004 | Enabler | Target dedup + versioned potential | backlog |
| ISS-005 | VS1 | Station-day mart + cross-station ranking view | backlog |
| ISS-006 | VS2 | L1 deviation v1 (uptime) | backlog |
| ISS-007 | VS3 | L1 deviation v2 (all signals) | backlog |
| ISS-008 | VS4 | Lead-time measurement harness | backlog |
| ISS-009 | VS5 | Onset labels + L2 model v1 | backlog |
| ISS-010 | VS6 | L3 value ranking + tiering | backlog |
| ISS-011 | VS7 | Data Activator alerts | backlog |
| ISS-012 | VS8 | Feedback loop | backlog |
| ISS-013 | VS9 | Fabric productionisation | backlog |
| ISS-014 | VS10 | Real-time historian | backlog |
| ISS-015 | VS11 | Output tables + semantic model | backlog |
| ISS-016 | VS12 | Power BI report pages | backlog |
| ISS-017 | VS13 | Publish app, RLS, refresh | backlog |

## Issue template
```
---
id: ISS-XXX
title: ...
type: vertical-slice | enabler
slice: VS-X | foundation
status: backlog
priority: P0|P1|P2
depends_on: []
runtime: local-prototype | fabric
---
# ISS-XXX — Title
## Why
## Goal / demo
## In scope
## Out of scope
## Acceptance criteria
## Tasks
## Data / dependencies
## Notes
```
