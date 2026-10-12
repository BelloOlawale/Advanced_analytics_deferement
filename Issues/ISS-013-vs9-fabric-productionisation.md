---
id: ISS-013
title: VS9 - Fabric productionisation (pipelines + notebooks replace local prototype)
type: vertical-slice
slice: VS9
status: backlog
priority: P1
depends_on: [ISS-005, ISS-006, ISS-007, ISS-008, ISS-010]
runtime: fabric
---
# ISS-013 — VS9: Fabric productionisation

## Why
The Phase-0 slices run locally on `duckdb` + CSVs. To be operated and governed by NewCross, they must run in Fabric on a schedule.

## Goal / demo
- A Fabric Data Factory pipeline + Spark notebooks run the same slices: bronze -> silver -> gold -> risk_daily.
- The daily run is scheduled, monitored, and reproducible; the local prototype is retired.

## In scope
- OneLake shortcuts / copy into `lh_bronze`.
- Spark notebooks: conform, episodes, features, deviations, scoring -> `lh_gold`.
- Orchestration + schedule + retry + alerting on failure.
- Secrets via Key Vault / Fabric connections; RBAC; sensitivity labels.
- Parity check: Fabric output == local prototype output for the same window.

## Out of scope
- Real-time (ISS-014); alert delivery already in ISS-011.

## Acceptance criteria
- [ ] End-to-end run completes on schedule with no manual steps.
- [ ] Outputs reconcile with the local prototype (row counts / key metrics).
- [ ] Failure alerting and rerun documented.
- [ ] No secrets in code; least-privilege connections.

## Tasks
- [ ] Create lakehouses + shortcuts.
- [ ] Port notebooks from prototype.
- [ ] Build orchestration + monitoring.
- [ ] Parity test.

## Data / dependencies
Fabric workspace/capacity; read-only identity (ISS-001).

## Notes
Keep config-as-data so tuning does not require redeploy.
