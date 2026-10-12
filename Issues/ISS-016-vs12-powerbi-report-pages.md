---
id: ISS-016
title: VS12 - Power BI report pages (ranking, drill-down, well vs baseline, heatmap, alert log, executive)
type: vertical-slice
slice: VS12
status: backlog
priority: P0
depends_on: [ISS-015]
runtime: fabric
---
# ISS-016 — VS12: Power BI report pages

## Why
People act on what they can see. This slice turns the model into the views each persona needs — ranked by money, drillable to a well, with the reason visible on every flag.

## Goal / demo
A Power BI report with:
- **Ranked stations** by value at risk (and by deferment %).
- **Station drill-down** to well/string.
- **Well detail** — trend versus its own baseline, with deviation overlay.
- **Cause heatmap** — stations × cause groups.
- **Alert log & precision** — alerts raised, acknowledged, hit/miss.
- **Executive summary** — headline lead time, value at risk, trend.

## In scope
- Build the report pages on the semantic model (ISS-015).
- Ensure every flag shows its **reason(s)** and **value at risk**.
- Baseline-vs-actual visual for the leading signals.
- Drill-through from station to well.

## Out of scope
- Publishing, RLS, refresh and distribution (ISS-017).

## Acceptance criteria
- [ ] All six pages exist and are driven only by the semantic model.
- [ ] Station → well drill-through works.
- [ ] Every risk visual carries the reason and $ value.
- [ ] Trend-vs-own-baseline visual renders for at least one signal.
- [ ] Report reviewed with at least one operator and one manager.

## Tasks
- [ ] Design page layout per persona.
- [ ] Build visuals; wire drill-through and tooltips.
- [ ] Add reason and value context to every flag.
- [ ] Review with users; iterate.

## Data / dependencies
Semantic model (ISS-015).

## Notes
Keep it explainable — a flag without a reason will not be trusted.
