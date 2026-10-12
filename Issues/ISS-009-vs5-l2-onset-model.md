---
id: ISS-009
title: VS5 - Onset labels + L2 onset model v1 (one cause group) + backtest
type: vertical-slice
slice: VS5
status: backlog
priority: P1
depends_on: [ISS-007, ISS-008]
runtime: local-prototype
---
# ISS-009 — VS5: Onset labels + L2 onset model v1

## Why
Once L1 has a measured lead time, test whether a learned model beats it. Start narrow: one cause group, one horizon.

## Goal / demo
- Onset labels (`onset_in_1/3/7`) for one cause group.
- A gradient-boosted model (LightGBM) predicting P(onset within H), with SHAP reasons.
- Backtest compared **head-to-head against L1** on lead time / PR-AUC / false alarms.

## In scope
- Label builder from episodes (ISS-003) for one cause group (e.g. equipment/rotating).
- Feature set from `gold.entity_deviation` + lags/slopes/rolling stats.
- Train + chronological backtest; report PR-AUC, recall@budget, lead time.
- Model registered with a version.

## Out of scope
- Survival model (follow-on); multi-cause-group generalisation; alerting.

## Acceptance criteria
- [ ] Labels built and sanity-checked (positive rate plausible).
- [ ] Model trained with no leakage; PR-AUC reported vs base rate.
- [ ] Head-to-head table vs L1 (keep L2 only if it adds lead time at equal false alarms).
- [ ] SHAP top features documented.

## Tasks
- [ ] Build labels + feature matrix.
- [ ] Train LightGBM; tune lightly.
- [ ] Chronological backtest + comparison.
- [ ] Model card.

## Data / dependencies
`gold.entity_deviation`, episode onsets.

## Notes
Prerequisite honesty: with 86% `Mismatch`, "one cause group" may be thin. If so, use severity-onset labels (top-decile loss) instead and document.
