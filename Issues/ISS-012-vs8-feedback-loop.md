---
id: ISS-012
title: VS8 - Feedback loop: outcome capture + realised lead time + tuning
type: vertical-slice
slice: VS8
status: backlog
priority: P1
depends_on: [ISS-011]
runtime: fabric
---
# ISS-012 — VS8: Feedback loop

## Why
The system must learn whether alerts were right and acted on, and use that to get earlier and cleaner. Without this, thresholds never improve.

## Goal / demo
- Each alert gets an outcome record (event occurred? acted? realised lead time).
- A dashboard shows alert precision, realised lead time, override rate over time.
- Thresholds/horizons are re-tuned from this evidence.

## In scope
- `feedback.outcomes` table keyed to alert id.
- Capture mechanism (form / link in the alert / Power App / notebook).
- Realised lead time + hit/miss computed when the event lands.
- Monthly re-tune job (config-as-data) + report.

## Out of scope
- Automated retraining of L2 (manual initially).

## Acceptance criteria
- [ ] Outcomes captured for a sample of alerts end-to-end.
- [ ] Realised lead time and precision computed automatically.
- [ ] Tuning report shows before/after false-alarm rate.
- [ ] No alert is silently dropped (every alert has an outcome slot).

## Tasks
- [ ] Create outcomes table + capture path.
- [ ] Compute realised lead time / precision.
- [ ] Build monitoring view.
- [ ] Define the monthly re-tune run.

## Data / dependencies
Alerts (ISS-011), event history, `deferment_fact`.

## Notes
Closes the loop that makes warnings "earlier without crying wolf".
