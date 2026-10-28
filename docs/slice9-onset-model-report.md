# Slice 9 — Layer 2 onset model v1

**Date:** 2026-10-22
**Environment:** `maf` sandbox
**Data window:** 2026-07-10 → 2026-10-07 (90 days, 5 stations)
**Verdict:** **Do not promote Layer 2. Keep rules v1.**

---

## 1. Question

Does a learned onset model beat rules v1 on **lead time at the same alert budget**?

The acceptance gate from `docs/fabric-semantic-model-and-report-plan.md` is:

> Keep Layer 2 only if it adds lead time at equal false alarms.

This slice builds the labels, trains a challenger, runs a chronological backtest and applies that gate.

---

## 2. Data and labels

The experiment uses the Fabric gold snapshot:

- `gold_entity_day_features` — 450 station-days, 171 columns
- `gold_risk_daily` — rules-v1 scores and tiers
- `gold_entity_baseline` — station p90 for large-loss labels
- `gold_alert` — rules-v1 alerts
- `silver_deferment_episode` — coded episode starts

Only **scored, observed** rows are eligible:

- 273 scored station-days
- 240 with a complete 7-day forward label window (2026-08-07 → 2026-09-30)
- 164 out-of-sample rows across three chronological folds

### Target definitions

| Target | Definition | Distinct events |
|---|---|---:|
| `large_loss` | Deferred oil reaches the station p90 after 3 quiet observed days below p90 | 18 |
| `coded_material` | A coded episode starts with deferred oil ≥ the station p90 | 34 |
| `material` (primary) | Union of the two | 34 |

Positive rows in the evaluation window:

| Target | Positive rows | Base rate |
|---|---:|---:|
| `large_loss` | 32 / 164 | 19.5% |
| `coded_material` | 48 / 164 | 29.3% |
| `material` | 62 / 164 | 37.8% |

A model that predicts every row positive would score 37.8% precision on the primary target. That is the bar the alert policy must clear.

---

## 3. Model and backtest

### Features

61 features, deliberately excluding rules-v1 outputs so the model is a genuine challenger:

- Robust z-scores and deviations for 8 metrics
- Composite deviation score and count of deviated signals
- Current process levels: oil, deferred oil, deferment %, target gap %, uptime, THP, bean, water cut
- Lags 1/7, deltas 1/7, rolling means/std 7/28, EWMA, slope, CUSUM for oil, uptime and deferment
- Event counts and 7-day event sums
- Weekday and weekend flags

### Model

Regularised logistic regression:

```text
median imputation → standard scaling → LogisticRegression(
    C=0.1, class_weight="balanced", max_iter=3000
)
```

Logistic regression was chosen over gradient boosting because:

- Only 164 out-of-sample rows and ~34 events
- The coefficients are directly interpretable
- LightGBM and histogram gradient boosting were also tested; they had higher variance across folds
- A simple linear model is easier to defend at this sample size

### Backtest

Three chronological folds, no random split:

| Fold | Train | Test | Train rows / pos | Test rows / pos |
|---|---|---|---|---|
| 1 | 2026-08-07 → 2026-08-22 | 2026-08-23 → 2026-09-04 | 76 / 25 | 54 / 10 |
| 2 | 2026-08-07 → 2026-09-04 | 2026-09-05 → 2026-09-17 | 130 / 35 | 53 / 9 |
| 3 | 2026-08-07 → 2026-09-17 | 2026-09-18 → 2026-09-30 | 183 / 44 | 57 / 13 |

Positive counts above are for `large_loss`; the primary `material` target has more positives.

### Alert comparison

Rules v1 fired **13 alerts** in the common test window (2026-08-23 → 2026-09-30).

The model was evaluated at the **same budget of 13 alerts**:

- A single score threshold was chosen from the score distribution only
- 3-day per-station cooldown, matching the rules-v1 cooldown
- The threshold is a **budget-matching device**, not a production threshold
- No labels were used to choose the threshold

---

## 4. Ranking results

### Primary target — `material`

| Metric | Model | Rules v1 |
|---|---:|---:|
| PR-AUC | **0.706** | 0.603 |
| ROC-AUC | **0.807** | 0.706 |
| Precision @ top 10% | 0.706 | **0.765** |
| Recall @ top 10% | 0.194 | **0.210** |
| Precision @ top 20% | 0.667 | **0.697** |
| Recall @ top 20% | 0.355 | **0.371** |

The model ranks better overall (higher PR-AUC and ROC-AUC), but its **top-of-list precision is slightly worse** than rules v1. The improvement is in the middle of the ranking, not where the alert budget is spent.

### Secondary target — `large_loss`

| Metric | Model | Rules v1 |
|---|---:|---:|
| PR-AUC | **0.401** | 0.178 |
| ROC-AUC | **0.790** | 0.485 |
| Precision @ top 10% | **0.412** | 0.059 |
| Recall @ top 10% | **0.219** | 0.031 |
| Precision @ top 20% | **0.364** | 0.091 |
| Recall @ top 20% | **0.375** | 0.094 |

The model is clearly better at ranking rare large-loss events than the rules score. This is the strongest positive result in the slice.

### Secondary target — `coded_material`

| Metric | Model | Rules v1 |
|---|---:|---:|
| PR-AUC | **0.680** | 0.564 |
| ROC-AUC | **0.778** | 0.720 |
| Precision @ top 10% | **0.824** | 0.706 |
| Recall @ top 10% | **0.292** | 0.250 |
| Precision @ top 20% | **0.697** | 0.636 |
| Recall @ top 20% | **0.479** | 0.438 |

The model also ranks coded material onsets better.

---

## 5. Alert-level results

This is the decision-relevant table. All rows use 13 alerts in the same test window.

| Target | Model confirmed / false | Model precision | Model median lead | Rules confirmed / false | Rules precision | Rules median lead |
|---|---:|---:|---:|---:|---:|---:|
| `material` (primary) | 9 / 4 | 69.2% | 2.0 d | **10 / 3** | **76.9%** | **3.0 d** |
| `large_loss` | 4 / 9 | 30.8% | 3.5 d | 4 / 9 | 30.8% | **4.5 d** |
| `coded_material` | **10 / 3** | **76.9%** | 3.5 d | 8 / 5 | 61.5% | 3.5 d |

### Gate result

| Target | Lead gain vs rules | False-alarm delta | Gate |
|---|---:|---:|---|
| `material` (primary) | **−1.0 day** | **+1 false alarm** | **FAIL** |
| `large_loss` | **−1.0 day** | 0 | **FAIL** |
| `coded_material` | 0.0 day | −2 false alarms | **FAIL** (no lead gain) |

The model does **not** add lead time at equal false alarms on any target.

- On the primary `material` target it is worse on both lead time and false alarms.
- On `large_loss` it ties false alarms but is one day slower.
- On `coded_material` it has better precision but the same median lead, so it fails the literal gate.

---

## 6. What the model learned

Logistic coefficients on the last training fold (standardised features). Positive coefficients increase the 7-day material-onset odds.

| Feature | Coefficient | Odds ratio |
|---|---:|---:|
| `uptime_cusum_neg` | +0.579 | 1.78 |
| `oil_lag_7` | +0.332 | 1.39 |
| `deferment_pct_cusum_neg` | +0.261 | 1.30 |
| `deviation_score` | +0.246 | 1.28 |
| `oil_cusum_neg` | +0.242 | 1.27 |
| `oil_roll_mean_28` | +0.231 | 1.26 |
| `oil_ewma_7_prev` | +0.228 | 1.26 |
| `actual_oil` | +0.224 | 1.25 |

| Feature | Coefficient | Odds ratio |
|---|---:|---:|
| `coded_event_count_roll_sum_7` | −0.218 | 0.80 |
| `coded_event_count` | −0.192 | 0.83 |
| `event_count_roll_sum_7` | −0.188 | 0.83 |
| `deferment_pct_roll_mean_28` | −0.151 | 0.86 |
| `deferment_pct_roll_mean_7` | −0.136 | 0.87 |
| `event_count` | −0.110 | 0.90 |
| `oil_delta_1` | −0.101 | 0.90 |
| `z_uptime` | −0.098 | 0.91 |

Interpretation:

- Sustained uptime deterioration and persistent oil underperformance increase risk.
- Recent coded-event activity is associated with **lower** forward risk in this seed, which may reflect recovery after an event. That is a data artefact/behaviour to validate on real history.
- The model is picking up oil and uptime trajectories, not just station identity.

SHAP was not used because the final model is linear; standardised coefficients provide an equivalent directional explanation. A tree-based model can be revisited if the dataset grows enough to support it.

---

## 7. Decision

**Keep rules v1.**

Reasons:

1. The primary target fails the gate: model 9 confirmed / 4 false / 2.0 days vs rules 10 / 3 / 3.0 days.
2. The large-loss target ties false alarms but loses one day of lead.
3. The coded-material target improves precision at the same lead, but that is not the primary operational target and does not satisfy “adds lead time”.
4. The sample is too small to justify replacing a transparent, explainable champion with a model that is less stable across folds.

The model is a useful **ranking challenger**, not a replacement alert engine. Possible future use:

- Use the model as a secondary prioritization score inside the existing rules alert workflow.
- Use it to rank station-days for analyst review, not to fire alerts directly.
- Re-test when a longer history is available.

---

## 8. Caveats

- **Small sample:** 5 stations, 90 days, 34 material events, 164 out-of-sample rows.
- **Synthetic seed:** the data is anonymised; the model may learn seed artefacts.
- **Target definition:** `material` is one defensible definition, not the only one. Different definitions change the result.
- **Budget-matched threshold:** the threshold is chosen from score quantiles to hit 13 alerts; a production threshold must be calibrated on training/validation data and monitored.
- **Alert policy:** 3-day cooldown matches rules v1, but a different policy (5-day or 7-day) changes the alert-level result.
- **Fold instability:** PR-AUC varies substantially across folds, especially for `coded_material` (0.12 → 0.95 → 0.40).
- **No model card:** this report is the model card for the rejected v1 experiment.

---

## 9. Reproduce

```bash
python tools/onset_model.py \
  --fabric-dir test_data/parity/fabric \
  --output-dir test_data/slice9
```

Outputs:

- `test_data/slice9/backtest_metrics.json`
- `test_data/slice9/scores_material.csv`
- `test_data/slice9/scores_large_loss.csv`
- `test_data/slice9/scores_coded_material.csv`
- `test_data/slice9/alerts_model_*.csv`
- `test_data/slice9/alerts_rules_window.csv`

The Fabric snapshot is read-only; the script does not write to `lh_gold`.

---

## 10. Next

1. Do **not** promote Layer 2 v1.
2. Keep rules v1 as the production alert engine.
3. Revisit Layer 2 when a longer real history is available.
4. In the meantime, the model ranking could be used for analyst prioritization, behind rules alerts.
5. Fix ISS-018 (duplicate `episode_id`) before using episode keys in any model feature or join.
