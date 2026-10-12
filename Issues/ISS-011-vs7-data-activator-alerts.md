---
id: ISS-011
title: VS7 - Data Activator alerts (Red/Amber) with reasons + owner routing
type: vertical-slice
slice: VS7
status: backlog
priority: P0
depends_on: [ISS-010]
runtime: fabric
---
# ISS-011 — VS7: Data Activator alerts with reasons + routing

## Why
A risk score nobody sees changes nothing. The warning must reach the owner with enough context to act, without spamming them.

## Goal / demo
- When a station/string crosses Red/Amber, a Data Activator rule fires a message to the owner (Teams/email) containing: entity, likely cause group, expected lead time, bbl/USD at risk, top reasons, suggested check.
- Alerts are rate-limited to an agreed budget.

## In scope
- Data Activator rule on `gold.deferment_risk_daily`.
- Message template with reason + value + link to dashboard.
- Owner mapping (station -> engineer) as data.
- Rate limiting / de-duplication of repeat alerts.

## Out of scope
- Feedback capture (ISS-012); model retraining.

## Acceptance criteria
- [ ] A Red and an Amber test alert both deliver to the intended owner.
- [ ] Message includes reasons, bbl/USD, and a dashboard link.
- [ ] Duplicate suppression works (no repeat spam while state persists).
- [ ] Alert volume respects the configured budget.

## Tasks
- [ ] Build owner mapping table.
- [ ] Configure Data Activator rule + template.
- [ ] Test Red/Amber paths and suppression.
- [ ] Document routing.

## Data / dependencies
`gold.deferment_risk_daily` (ISS-010); Power BI workspace; Teams/email.

## Notes
Runtime = Fabric. Confirm alert budget with ops (see PRD open questions).
