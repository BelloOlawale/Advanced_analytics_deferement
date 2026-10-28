---
id: ISS-009
title: VS5 - Onset labels + L2 onset model v1 (one cause group) + backtest
type: vertical-slice
slice: VS5
status: done
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
- [x] Labels built and sanity-checked (positive rate plausible).
- [x] Model trained with no leakage; PR-AUC reported vs base rate.
- [x] Head-to-head table vs L1 (keep L2 only if it adds lead time at equal false alarms).
- [x] Top features documented. SHAP was not used because the selected model is
      linear; standardised logistic coefficients provide the directional
      explanation.

## Tasks
- [x] Build labels + feature matrix.
- [x] Train and compare models; logistic regression selected for stability.
      LightGBM and histogram gradient boosting were also tested.
- [x] Chronological backtest + comparison.
- [x] Model card — `docs/slice9-onset-model-report.md`.

## Result (2026-10-22)

**Decision: keep rules v1.** Layer 2 v1 was not promoted.

- Primary target `material`: model PR-AUC 0.706 vs rules 0.603, but at the
  same 13-alert budget the model got 9 confirmed / 4 false / 2.0 days vs
  rules 10 / 3 / 3.0 days. It is worse on both false alarms and lead time.
- `large_loss`: model 4 / 9 / 3.5 days vs rules 4 / 9 / 4.5 days — same false
  alarms, one day slower.
- `coded_material`: model 10 / 3 / 3.5 days vs rules 8 / 5 / 3.5 days — better
  precision at the same lead, but no lead gain.

The gate (“adds lead time at equal false alarms”) fails on every target.
See `docs/slice9-onset-model-report.md` and `tools/onset_model.py`.

## Data / dependencies
`gold.entity_deviation`, episode onsets.

## Notes
Prerequisite honesty: with 86% `Mismatch`, "one cause group" may be thin. If so, use severity-onset labels (top-decile loss) instead and document.
