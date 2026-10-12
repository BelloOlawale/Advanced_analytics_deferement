---
id: ISS-001
title: Read-only access hardening + DQ monitoring gate
type: enabler
slice: foundation
status: backlog
priority: P0
depends_on: []
runtime: local-prototype
---
# ISS-001 — Read-only access hardening + DQ monitoring gate

## Why
Access currently uses an admin account (`sharepoint.admin@Newcross.com`). We need a **read-only identity** and an automated **data-quality gate** so the pipeline runs safely and fails loudly on bad data.

## Goal / demo
- The pipeline connects with a **read-only** identity; a write is rejected by the database itself.
- A one-command DQ report prints volume, date coverage, FK integrity, null rates and cause-code completeness.

## In scope
- Obtain/create a read-only service principal or user; grant workspace `Viewer` + `db_datareader` (+ `db_denydatawriter`).
- Point `tools/fabric_query.py` at it.
- Reusable DQ suite (duckdb/Python) covering: rows, min/max date, null rates, FK orphans, duplicates, negative volumes, % cause classified.

## Out of scope
- Fabric productionisation (ISS-013).

## Acceptance criteria
- [ ] Connection succeeds with a read-only identity (admin not required).
- [ ] A write statement is refused by the **database**, not only the client guard.
- [ ] DQ report outputs all checks and exits non-zero on a hard failure.
- [ ] Access documented in `docs/`.

## Tasks
- [ ] Request read-only identity from NewCross admin.
- [ ] Grant roles; verify with a write-attempt test.
- [ ] Add DQ suite to `tools/`.
- [ ] Document access + roles.

## Data / dependencies
`wh_gold`; NewCross Fabric admin.

## Notes
Cause completeness will fail initially (~13.5%) — the gate must **WARN, not block**.
