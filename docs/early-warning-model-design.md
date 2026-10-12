# Early-Warning Model Design — what we are actually building

> Focus: **"How to detect the risk earlier?"** — flag deferment *before* it occurs.
> Depends on: `early-warning-patterns.md` (real precursor findings), `data-quality-findings.md` (data limits).
> Status: design proposal to confirm in Discovery.

---

## 1. Why not a single model

| Constraint (from real data) | Modelling consequence |
|---|---|
| Deferment on ~95% of station-days | "Predict occurrence" is meaningless — a constant `yes` scores 95%. |
| Loss lag-1 autocorr 0.45–0.82 | A model using yesterday's loss is accurate but **late**; it must key on **change**. |
| 86% of causes are `Mismatch` | Cause-specific supervised learning is starved for the rare coded causes. |
| No event duration | No time-to-failure / RUL labels yet. |
| Precursors partial (`thp` −23%, `bean` −27% null) | Model must tolerate missing signals. |

So the system is **three layers**: an always-on deterministic detector, a supervised onset model on top, and a value-ranking layer.

## 2. What exactly is predicted (the labels)

| Label | Definition | Used for |
|---|---|---|
| **Onset-in-H (primary)** | For entity = station **or** string, cause *c*: `y=1` if the **first day of a coded-cause episode** falls within the next H days (H ∈ {1, 3, 7}); else 0. Episode = run of consecutive days carrying *c* (islands). | Supervised onset model |
| **Severity-onset (fallback)** | Station-day deferred oil ≥ its **own 90th percentile**, following ≥K quiet days. | When cause codes are unusable |
| **Next-day loss (magnitude)** | Continuous deferred-oil volume per station-day. | Value/priority ranking |

Cause grouping (to beat sparsity): **equipment/rotating**, **facility/utilities**, **well/subsurface**, **flowline/export**, **planned**. Model each group, then drill in.

## 3. The three layers

### Layer 1 — Per-entity deviation engine (baseline, always on)
- Learn **each station's and each string's own normal** for: `uptimeproduction`, `thp`, `bean`, `water_rf`, oil-vs-deduped-target, event frequency.
- Robust, seasonal baseline (median + MAD, day-of-week / month-of-year).
- Deviation detectors: **z-score**, **EWMA**, **CUSUM** (CUSUM/EWMA catch slow drifts days earlier than raw thresholds).
- Change-point detection for *station regime shift*.
- Output: an anomaly score + **which signal** moved — explainable by construction.
- This layer alone can fire warnings (rule-based tiers) and is the honest MVP.

### Layer 2 — Supervised onset model (learned)
- **Algorithm: gradient-boosted trees (LightGBM / XGBoost)** — tabular, handles missingness, small data, fast, explainable via SHAP. This is the primary "prediction model".
- **Features:** Layer-1 deviations + lags (1–14 d), rolling deltas/velocity, rolling volatility, uptime/THP/bean/water-cut levels and slopes, recent event history & gaps, oil-vs-target gap, station/string/asset identifiers.
- **Target:** Onset-in-H (§2).
- **Companion: survival model** (`Cox PH` or discrete-time hazard) for **time-to-onset**, which yields the *lead-time distribution* directly.
- **Start rule-first, learn second:** ship Layer 1, then train Layer 2 and keep it only if it beats Layer 1 on lead time / false alarms.

### Layer 3 — Value ranking (priority)
- `Risk = P(onset within H) × expected bbl at risk × oil price`.
- Expected bbl from the magnitude model or recent loss run-rate.
- Output → **Red / Amber / Green**, ranked by money, routed to the owner (Data Activator).
- Requires `oil_prices` (tiny, not yet pulled) for the money term.

## 4. Why not deep/sequence models yet
5 stations, 71 strings, ~5,400 coded events, daily granularity, and a cause-code gap. Deep nets (LSTM/Transformer) need far more data and higher frequency, and operators need *reasons*. Revisit when we have **hourly historian feeds** and clean cause codes. GBM + survival is the right ceiling for now.

## 5. How we judge it (this is the "earlier" proof)
Evaluation must be **chronological backtest**, never random split. Metrics:
- **Median lead time (days)** — how early before onset the flag fires. *The headline KPI.*
- **Recall at a fixed alert budget** (alerts/day an operator can absorb) — precision/recall on a rare positive class; use **PR-AUC**, not accuracy.
- **False-alarm rate** per station per week.
- **Stability** across stations (one model, per-station behaviour).

KPI sentence we're aiming to earn: *"For cause group G at station S, the model flags N days before onset with F false alarms/week."*

## 6. Build order
1. **Per-entity baseline + deviation engine** (Layer 1) — and the **measured lead-time table** vs coded onsets.
2. Value ranking (Layer 3) — cheap, makes warnings actionable immediately.
3. Onset model (Layer 2) once Layer 1 establishes the lead time and features.
4. Feedback loop: log whether the event happened and whether the team acted → retrain.

## 7. Fabric placement
- Features: `lh_gold` feature table (entity-day). 
- Scoring: daily notebook/pipeline → risk table.
- Alerting: Data Activator → Red/Amber only → owner.
- Governance: model card, backtest report, drift monitoring.

---

*Proposal, 2026-10-08. Algorithm choice and horizons (H) to be confirmed against measured lead time.*
