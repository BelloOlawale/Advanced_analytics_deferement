# Flow Station Early Risk Detection — Process & Historical Data Requirements

> Project: **Part 1, Project 1 — Deferment Root-Cause & Production Loss Prediction**
> Asset: **OML 24** (Awoba, Awoba North West, Ekulama) · western Niger Delta
> Platform: **Microsoft Fabric** (`lh_silver` → `lh_gold`) + Power BI + Data Activator
> Purpose: detect deferment risk at **flow-station level, earlier than the deferment log shows it**, and compare risk fairly **across flow stations**.
> Status: working design — field/table names are proposals to confirm in discovery.
> Related: `deferment-root-cause-deep-dive.md`, `deferment-fabric-build-spec.md`, `deferment-ml-engineering-blueprint.md`

---

## 1. The question this answers

> "How do we see trouble brewing at a flow station **before** the deferment shows up — and which station is at risk first?"

The key insight: **deferment is the result, not the signal.** By the time an event is booked in `deferment_fact`, barrels are already lost. Early detection therefore means watching **precursors (leading signs)**, not lost volumes (lagging results).

---

## 2. Core principles

- Each flow station is its own little world — its own wells, equipment, age, and "normal."
- Detect risk by watching each station **against its own normal**, then comparing stations to each other.
- Score **daily** (or hourly with live data) rather than waiting for monthly reporting.
- Everything is ranked by **money at stake**, not by raw probability.
- Flags must be **explainable** and **owned**, or they will not be trusted or acted on.

---

## 3. The process

### Step 1 — Define what "risk" means at a flow station
A station's risk is the sum of two parts:
- **Its own facility risk** — power, separator, pump, compressor, export line, capacity limits.
- **The risk of everything inside it** — the wells and production strings hanging off that station.

So a station flag means: *"this station is starting to misbehave"*, built from its wells + equipment + station-level facilities.

### Step 2 — Give every station its own baseline (critical step)
- Do **not** use one global threshold — Awoba, Awoba North West and Ekulama are not the same.
- For each station, learn **its own normal**: normal deferment %, normal uptime, normal event rate, normal THP/bean behaviour.
- Flag when a station drifts from **its own** normal.
- Rationale: a station that always runs at 95% uptime dropping to 90% is a bigger warning than one that always sits at 90%.

### Step 3 — Watch leading signs, not just lost barrels
Detect the **precursor**, grouped by signal type:

| Signal type | What to watch per flow station | Drivers it warns about |
|---|---|---|
| Production drift | actual vs `target_oil` gap widening; `uptimeproduction` slipping | any impending loss |
| Process behaviour | `thp`, `bean` size, water cut (`water_rf`), GOR changing | dewaxing, sand, water encroachment, well no-flow |
| Equipment / runtime | run-hours, power trip counts, spares status | pump, compressor, engine, power, SSV/SCSSSV |
| Maintenance load | open work orders, overdue PMs, backlog | most equipment failures |
| Event history | repeat events, shrinking gaps (MTBF falling) | bean erosion, flowline leaks, pump failures |
| External factors | rainy season, community/security incidents, drilling plan | community interruption, vandalism, drilling deferment |
| Rate of change | speed of deterioration, not just the level | all of the above |

These move **before** the deferment is booked.

### Step 4 — Use simple statistics to catch the shift early
- **Control charts (per station):** plot daily deferment % and key signals; set limits from that station's own history. A run above the limit = a real shift, not noise.
- **EWMA / CUSUM:** sensitive to small, slow drifts — catches things days earlier than a raw chart.
- **Change-point detection:** auto-dates "something changed here."
- **Trend / seasonality split:** separates a genuine worsening trend from the normal rainy-season pattern.

### Step 5 — Compare stations fairly (cross-station view)
Raw numbers mislead (bigger stations always look worse). So **normalise**:
- Deferment as a **% of potential**, not barrels.
- Events **per well** and **per 1,000 bbl** of potential.
- Duration and frequency per station.

Then:
- **Rank / z-score** each station against its peers.
- Build a **heatmap: flow stations × causes** — red cells show where risk is concentrating.
- Watch **station-to-station gaps** — if one station's uptime drops while peers hold, that station is the early warning.

### Step 6 — Score each station daily and roll it up
- `Station Risk = combine( own facility risk , risk of its wells/strings )`
- `Score = chance of loss × expected barrels × oil price` → flags ranked by money at stake.
- **Tier:** Red / Amber / Green.
- Recompute daily (or hourly with live data) — this is what makes it *earlier* than monthly reporting.

### Step 7 — Turn scores into flags people act on
Each flag states: **which station, likely cause, how soon, barrels at risk, what to do, who owns it.**
- Standing **dashboard** (all stations, ranked) + **push alerts** only for Red/Amber.
- Example station flags:
  - "Ekulama FS: power trips 2σ above its own baseline → pump failure risk in 48h."
  - "Awoba FS: gap to target widening + THP falling → dewaxing likely within 5 days."
  - "FS-X: 3rd flowline leak this quarter, gaps shrinking → integrity risk."

### Step 8 — Close the loop
- Record whether the event happened and whether the team acted.
- Measure **how early** and **how accurate** the flag was, per station.
- Retrain and re-tune thresholds monthly so warnings get earlier without crying wolf.

---

## 4. How this maps onto the Fabric data model

| Need | `lh_silver` source |
|---|---|
| Station dimension / peer grouping | `flowstations_dim` (flowstation, asset) |
| Event-level loss + cause | `deferment_fact` (flowstation_id, category_id, subcategory_id, date, oil/gross, status) |
| Cause taxonomy | `deferment_category_dim`, `deferment_subcategory_dim` |
| Actual vs target / leading process signals | `production_fact` (`oil`, `target_oil`, `uptimeproduction`, `thp`, `bean`, `water_rf`) |
| Value at risk | `oil_prices` |
| Well / reservoir context | `reservoirs_dim`, production strings |

**Gap to close:** `deferment_fact` currently has a `date` and volumes but **no start/end or duration** → add `start_ts` / `end_ts` (or `duration_hrs`) to enable true frequency × duration decomposition at station level.

---

## 5. Historical data required to detect risk earlier

The rule: **you need enough history to learn each station's normal, its repeat patterns, and the precursors that precede failures — and enough to prove the model works.** Depth matters more than width here.

### 5.1 Minimum history depth

| Purpose | Minimum | Preferred |
|---|---|---|
| Learn each station's own baseline | 12 months | 24–36 months |
| Capture seasonality (rainy/dry, turnarounds) | 24 months | 36+ months |
| Learn recurrence intervals / MTBF per cause | ≥ 3–5 occurrences per cause per station | 10+ occurrences |
| Train & backtest ML classifiers | ≥ 12 months of labelled events | 24–36 months |
| Survival / RUL for critical equipment | ≥ 1 full failure cycle per asset | 2+ cycles |

**Rule of thumb:** 24–36 months is the practical target for a Niger Delta onshore asset; below 12 months you can only do descriptive Pareto, not reliable early warning.

### 5.2 Data you need (by domain)

**A. Event / loss history (the label)**
- `deferment_fact` events with: date, **start & end time**, flowstation, production string, category + subcategory (clean codes), status (planned/unplanned, open/closed), oil/gross/water/gas lost.
- History of the **cause taxonomy changes** (codes were re-mapped over time) so old labels can be normalised.

**B. Production & potential (the outcome + drift)**
- Daily actual oil/gas/water per well and per station.
- **Potential / allowable / target** per well and station — and the **method used over time** (well models change).
- `uptimeproduction`, runtime hours, downtime flags.

**C. Process / sensor time series (the precursors)**
- `thp`, choke/`bean` size, flowline/wellhead pressures, temperatures, water cut (`water_rf`), GOR.
- Ideally **hourly or higher** from the historian; daily is the minimum.
- Vibration/temperature for critical rotating equipment where instrumented.

**D. Equipment & maintenance (the mechanics)**
- Equipment master: install date, type, criticality, capacity, run-hours.
- Work orders: failure codes, repair hours, dates, equipment references.
- PM/planned maintenance history — including **overdue / deferred** maintenance.
- Spares availability and procurement lead times (links to the Supply Chain project).

**E. Utilities & external factors**
- Power supply/trip logs per station.
- Weather / rainfall (rainy-season effects on access, power, community).
- Community / security incident logs.
- Drilling, intervention, and shutdown schedules (planned deferment context).

**F. Commercial**
- Daily realised oil price (`oil_prices`) for value-at-risk scoring.

### 5.3 Data-quality requirements (non-negotiable for early warning)

- **Cause-code completeness** — `% unclassified` (`NULL`, `Mismatch`) must be low; otherwise the model learns noise. Target ≥ 95% valid codes.
- **Event timing** — exact start/end (or best reconstructed), not date-only.
- **Referential integrity** — every event ties to a valid station, well, and string.
- **Consistent potential methodology** — a fixed formula, versioned; stale well models distort every trend.
- **Units, time zones, gross vs net** — standardised and documented.
- **Late-arriving / restated data** — handled via slowly-changing dimensions.
- **History of re-classifications** — so trends aren't broken by taxonomy changes.

### 5.4 What "enough" looks like per station

For a reliable per-station early-warning model you want, per flow station:
- ~24+ months of clean daily production vs target.
- ~24+ months of clean deferment events with duration.
- At least a handful of repeat occurrences of each **high-priority** cause (the chronic ones), so recurrence logic and thresholds are meaningful.
- Enough **non-event days** (controls) — normally the vast majority — so the model can learn what "normal" looks like.

If a cause is too rare (e.g. Wellhead Fire), level it up to a station/asset-level rule and contingency plan rather than a statistical model.

### 5.5 Minimum-viable vs ideal datasets

| Priority | Dataset | Why |
|---|---|---|
| Must-have | Deferment events + clean cause codes + start/end | the label & the pattern |
| Must-have | Daily actual vs potential/target per station & well | the drift signal |
| Must-have | Flowstation + well + equipment master | entity context |
| Must-have | Oil price | ranking by money |
| High-value | THP / bean / water cut / uptime time series | the precursors |
| High-value | Work orders + PM history + spares | mechanical drivers |
| High-value | Power trip logs | top station-level driver |
| Nice-to-have | Weather, community/security logs | seasonality & third-party |
| Nice-to-have | Vibration / equipment condition data | RUL for critical assets |

---

## 6. Summary

- **Don't** wait for the deferment log — watch the precursors.
- **Give each station its own baseline**, then flag drift from it.
- **Normalise before comparing** stations, so the comparison is fair.
- **Score daily, rank by money, tier Red/Amber/Green**, route to owners.
- **Track outcomes** so the next warning comes earlier and cleaner.
- **History rule of thumb:** 24–36 months of clean, event-level, per-station data with duration and codes — with valid cause codes above ~95%.

---

*Prepared as a working design. All KPIs, thresholds and field names are proposals to confirm during Discovery and Value Definition.*
