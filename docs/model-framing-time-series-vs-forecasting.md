# Model Framing — Time Series vs Forecasting

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Audience: anyone asking "is this a time-series model, and should we forecast?"
> Status: reference · Version 0.1 · 2026-10-08

---

## 1. The question

*"Is this a time-series solution? Should we use a typical time-series model — ARIMA, Prophet, or a sequence model — to forecast deferment?"*

## 2. Short answer

- The **data** is genuinely time series (daily observations per station and well over about two years).
- The **solution is not a classic time-series forecasting model**. It is an **early-warning system**, delivered mainly as **event prediction** plus **anomaly and survival analysis**, with a small **forecasting** element (the value at risk).
- In one line: **a leading-indicator solution built on time-series data — event prediction, not value forecasting.**

---

## 3. What the model actually does

| Layer | Task | Output |
|---|---|---|
| **L1 — Deviation engine** | Detect when each signal departs from its own normal (anomaly / change-point) | deviation score + reason |
| **L2 — Onset model** | Predict the probability that a specific event **starts within the next 1 / 3 / 7 days**, from lagged clues | risk probability 0–1 |
| **Survival model** | Estimate **time until onset** | expected days to onset |
| **L3 — Value ranking** | Combine probability with barrels and price | expected bbl, expected $, tier |

The target is an **event** ("will a loss episode start soon?"), not the next value of a series.

---

## 4. Why the data is genuinely time series

| Aspect | Why it is time series |
|---|---|
| Data | Daily observations per station and well over about two years |
| Features | Lags, slopes, rolling means, smoothed drift (EWMA/CUSUM) — the time is engineered into the clues |
| Splitting | Chronological only (train on past, test on future) — never random |
| Detection | Finding drift and change points in a signal |
| Evaluation | Lead time — how many days ahead the warning fires |
| Maintenance | Retraining as behaviour drifts over time |

---

## 5. Why it is *not* a typical time-series forecasting model

**What a typical time-series forecasting model does:** given a series of values `y(t)`, predict the next values `y(t+1) … y(t+h)`. The target is a **number**, the thing forecast *is* the thing of interest, and it is judged by **forecast error**.

**How our problem differs:**

| Dimension | Typical forecasting model | This solution |
|---|---|---|
| Target | The next value of a series (a number) | Whether an **event starts** (a class) |
| Question answered | "How much, next period?" | "Will trouble start soon — and how soon?" |
| Data shape | One (or few) series | Many entities (station × well), aggregated to entity-day |
| Headline metric | Forecast error (MAE / RMSE / MAPE) | **Lead time** (days of warning), precision/recall |
| Why it works | The series varies enough to forecast | The value is in the **change**, before the loss is logged |
| Base-rate problem | Not usually an issue | Loss occurs on ~95% of station-days, so forecasting "will there be loss" is accurate but useless |

**The decisive point:** forecasting the loss series would be *accurate but late*. The loss is already happening; the model must react to **change**, not predict the level.

---

## 6. Component-by-component classification

| Component | Task | Flavour |
|---|---|---|
| Deviation engine | Anomaly / change-point detection per signal | Time series |
| Onset model | "Event within the next 1 / 3 / 7 days?" from lagged clues | Time series turned into **classification** |
| Survival model | Time to onset | Time series / **survival analysis** |
| Expected loss | Barrels and value at risk | **Forecasting** (the only forecasting piece) |

---

## 7. What a *real* time-series forecasting model would look like here

For completeness, a genuine forecasting artefact in this domain would be:

- **Deferred-volume forecast:** predict daily/weekly deferred barrels per station (ARIMA / ETS / Prophet / regression), judged by MAE/MAPE.
- **Production-volume forecast:** predict future oil output — a *separate* project in the programme.

These are **complementary**, not the same thing. In fact they compose:

> `expected loss = P(onset within H) × forecast volume at risk × price`

Our solution supplies the probability; a forecasting model could supply the volume. The current build uses a simple proxy (recent loss rate) for the volume term and can be upgraded later.

---

## 8. Why not ARIMA / Prophet / deep sequence models

- **ARIMA / Prophet** forecast a series' next values. Here the series is almost always "loss happening" (about 95% of days), so forecasting it is accurate but uninformative — and it fires *after* the loss starts.
- **Deep sequence models (LSTM / Transformer)** need far more data and a higher frequency than 5 stations × ~2 years of daily history, and they cannot explain *why* a flag fired.
- **Tabular models on engineered temporal clues** win at this scale. The three clocks — lags, rolling windows, and deviations — already carry the time information the model needs.

*(Source: real-data findings — see `early-warning-patterns.md` and `data-quality-findings.md`.)*

---

## 9. What the model outputs

Not a single number, and not a binary label — a rich, explainable record: **risk probability, tier, reason(s), expected barrels and value** (a binary "alert fired" flag is derived from the tier). See `prd-deferment-early-warning.md` §12.3.

---

## 10. Implications for how we build and judge it

- **Respect time order** everywhere: lags, rolling windows, chronological splits, no shuffling.
- **Temporal feature engineering** is where the time lives.
- **Time-aware cross-validation** (rolling windows), not random k-fold.
- **Judge by lead time**, not forecast error.
- **Monitor drift** and retrain periodically.
- If the client wants a volume **forecast dashboard**, treat it as a **separate, complementary deliverable** — do not conflate it with the early-warning model.

---

## 11. One-sentence summary

> We are not forecasting deferment — we are **predicting when it will start, and saying so early enough to act** — on time-series data.

---

*Reference note, 2026-10-08. Related: `how-the-model-works.md` §6, `early-warning-model-design.md`, `decisions-log.md` D-05.*
