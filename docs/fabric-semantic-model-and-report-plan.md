# Fabric semantic model and report — build plan (`maf`)

**Date:** 2026-10-21
**Workspace:** `maf`
**Status:** Slice 9 complete — Layer 2 v1 tested and rejected; rules v1 retained

This document records the decisions, findings and vertical slices for the
serving layer over `lh_gold`. It complements the build log in
`docs/fabric-build-log-maf-sandbox.md` §14.

---

## 1. Naming convention — `df` = deferment

All **new** serving-layer artifacts carry `df` so they are recognisable as part
of the deferment early-warning solution.

| Artifact | Name |
|---|---|
| Dimension notebook | `nb_05_df_gold_dimensions` |
| Date dimension table | `gold_df_dim_date` |
| Station dimension table | `gold_df_dim_station` |
| Semantic model | `sm_df_early_warning` |
| Power BI report | `rpt_df_early_warning` |

Existing items keep their names. Renaming `nb_01`–`nb_04` or the existing
`gold_*` tables would break the build log, notebook references and the planned
pipeline, so the convention starts with the serving layer and the new
dimensions.

**Direct Lake constraint.** The semantic-model table name must match the
physical Delta table name exactly. Friendly report labels therefore come from
visual titles and measure names, not from renamed model tables.

---

## 2. Why physical dimensions

`gold_risk_daily` has a complete station-date grid, but it is a fact table. The
semantic model needs two conformed dimensions:

- `gold_df_dim_date` — one row per date in the gold window (90 rows)
- `gold_df_dim_station` — one row per station (5 rows)

They are **physical Delta tables**, not DAX calculated tables. In Direct Lake,
calculated tables and calculated columns are still preview and can cause
unexpected fallback. Physical dimensions avoid that risk and keep the model
fully Direct Lake.

---

## 3. Direct Lake publishing findings

These were confirmed with a temporary probe semantic model
(`sm_probe_directlake`), which was deleted after testing.

1. **REST publishing works.** A semantic model is created with
   `POST /v1/workspaces/{workspaceId}/items`, `type: SemanticModel`.
2. **Definition layout.** TMDL parts must be sent as:
   - `definition/database.tmdl`
   - `definition/model.tmdl`
   - `definition/expressions.tmdl`
   - `definition/tables/<table>.tmdl`
   - `definition.pbism` at the **root** (not under `definition/`)
3. **Direct Lake table names are not cosmetic.** The probe used model table
   `Stations` over Delta table `gold_dim_station`. The model was stored
   correctly, but refresh failed with *table `Stations` does not exist or access
   was denied*. Direct Lake resolves the physical table by the model table name.
   **Model table names must equal the Delta table names.**
4. **Omit `schemaName` for this non-schema lakehouse.** A Direct Lake partition
   with `schemaName: dbo` imported but failed on refresh with *table does not
   exist or access was denied*. Removing `schemaName` fixed it. The working
   partition source is:

   ```text
   partition gold_risk_daily = entity
       mode: directLake
       source
           entityName: gold_risk_daily
           expressionSource: DatabaseQuery
   ```

   For a schema-enabled lakehouse the `schemaName` would be required; `lh_gold`
   is not schema-enabled.
5. **Use the ID-based OneLake path.** The expression must point at the lakehouse
   root using workspace and lakehouse IDs:
   `https://onelake.dfs.fabric.microsoft.com/<workspaceId>/<lakehouseId>`.
   Adding `/Tables`, or using the workspace/lakehouse display names, produced
   *Direct Lake On OneLake requires a valid OneLake data source*.
6. **Refresh is required before querying.** After creation, trigger a refresh
   (Power BI `POST /datasets/{id}/refreshes`) and check the refresh history. A
   fresh model without a successful refresh cannot be queried with DAX.
7. **Always group/filter dates through `gold_df_dim_date`.** Grouping or
   filtering the fact table's own `date` column while a dimension filter is
   present can drop the dimension filter in this Direct Lake model. Observed
   with `SUMMARIZECOLUMNS` and with `CALCULATE` inside measures. Use
   `gold_df_dim_date[date]` in report axes, table columns and date filters.
   This rule fixed the station-detail table and the “latest” measures.

---

## 4. Target model

Model: `sm_df_early_warning`, Direct Lake over `lh_gold`.

| Model table | Physical table | Role |
|---|---|---|
| `gold_risk_daily` | `gold_risk_daily` | Daily risk fact (station × date) |
| `gold_deviation_daily` | `gold_deviation_daily` | Long-form deviations (heatmap) |
| `gold_alert` | `gold_alert` | Fired-alert log |
| `gold_alert_outcome` | `gold_alert_outcome` | Outcome / lead-time view |
| `gold_entity_baseline` | `gold_entity_baseline` | Normal ranges for station detail |
| `gold_df_dim_date` | `gold_df_dim_date` | Calendar dimension |
| `gold_df_dim_station` | `gold_df_dim_station` | Station dimension |

Relationships:

- `gold_df_dim_date[date]` → `gold_risk_daily[date]`
- `gold_df_dim_date[date]` → `gold_deviation_daily[date]`
- `gold_df_dim_date[date]` → `gold_alert[alert_date]`
- `gold_df_dim_station[station_id]` → `gold_risk_daily[station_id]`
- `gold_df_dim_station[station_id]` → `gold_deviation_daily[entity_id]`
- `gold_df_dim_station[station_id]` → `gold_alert[station_id]`
- `gold_df_dim_station[station_id]` → `gold_entity_baseline[entity_id]`
- `gold_alert[alert_id]` → `gold_alert_outcome[alert_id]`

Core measures:

- Risk: scored/observed days, coverage %, Red/Amber days, excess value at risk,
  latest risk score, latest risk tier, stations at Red (latest)
- Alerts: alerts fired, Red/Amber alerts, open alerts, excess USD at alert,
  alert rate per station per week
- Outcomes: alerts with outcome, confirmed alerts, precision %, false-alarm
  rate %, median/average lead time, alerts awaiting outcome
- Deviations: bad-direction z (`Bad Z`), scored bad z

---

## 5. Vertical slices

Each slice is runnable and verifiable on its own. Do not start the next slice
until the current one is signed off.

### Slice 1 — dimensions + semantic model ✅

1. Rename the notebook to `nb_05_df_gold_dimensions`.
2. Write `gold_df_dim_date` and `gold_df_dim_station`.
3. Deploy and run; verify row counts and uniqueness.
4. Publish `sm_df_early_warning` with the seven tables and relationships above.
5. Refresh the model and run DAX smoke tests:
   - `COUNTROWS('gold_df_dim_station')` = 5
   - `COUNTROWS('gold_df_dim_date')` = 90
   - risk tiers for scored observed rows = 25 Red / 22 Amber / 226 Green
   - fired alerts = 17
6. Record the model ID and verification results in the build log.

**Acceptance:** refresh succeeds, all smoke-test values match the SQL ground
truth, and the model is not falling back to DirectQuery.

**Result (2026-10-21):** passed. See §6 for IDs and evidence.

### Slice 2 — executive report page ✅

`rpt_df_early_warning` page 1: KPI cards (alerts, value at risk, stations at
Red, coverage), ranking by station, tier mix, alert trend, latest alerts.

**Result (2026-10-21):** passed. See §7 for IDs and evidence.

### Slice 3 — station drill-down ✅

Page 2: station slicer, latest risk, actual vs expected oil, baseline table,
recent reasons.

**Result (2026-10-21):** passed. See §8 for IDs and evidence.

### Slice 4 — deviation heatmap ✅

Page 3: metric × month matrix of `Bad Z` with conditional formatting.

**Result (2026-10-21):** passed. See §9 for IDs and evidence.

### Slice 5 — alert log and outcomes ✅

Pages 4–5: alert log table + slicers, outcome/lead-time cards and table.

**Result (2026-10-21):** passed. See §10 for IDs and evidence.

### Slice 6 — orchestration ✅

Data Factory pipeline `01 → 02 → 03 → 04 → 05`, daily schedule, retries,
failure alert. Outcome/lead-time job after that.

**Result (2026-10-21/22):** passed. See §11 for IDs and evidence.

### Slice 7 — alert outcomes and realised lead time ✅

Fills `gold_alert_outcome` with a future coded onset or large-loss onset within
7 days, then computes median lead time and false-alarm rate.

**Result (2026-10-22):** passed. See §12 for IDs and evidence.

### Slice 8 — parity check against the local reference ✅

Re-implements the documented notebook rules independently in pandas over the
same seed CSVs, then compares every silver/gold table with the Fabric output.

**Acceptance:** row counts, keys, numeric values, risk tiers, alerts and
outcomes agree; any text difference is explained and display-only.

**Result (2026-10-22):** passed with two documented floating-point tie effects.
See §12a and `docs/fabric-parity-check-slice8.md`.

### Slice 9 — Layer 2 onset model v1 ❌ (rejected)

Builds 7-day onset labels, trains a regularised logistic-regression challenger,
runs a 3-fold chronological backtest and compares it with rules v1 at the same
alert budget.

**Result (2026-10-22):** the model improves ranking (PR-AUC) but does not add
lead time at equal false alarms on the primary material target. Rules v1 is
retained. See §12b and `docs/slice9-onset-model-report.md`.

---

## 6. Slice 1 result

| Item | Value |
|---|---|
| Notebook | `nb_05_df_gold_dimensions` |
| Notebook ID | `effcd5bf-f960-4523-9028-661e0f6401fe` |
| Latest run ID | `e62eccf4-2408-4a21-ad62-0c113398cb8b` |
| Semantic model | `sm_df_early_warning` |
| Semantic model ID | `0f5395f6-2365-48a2-ae9d-c6c2e814bc9f` |
| Model refresh | **Completed** |

Dimensions:

| Table | Rows | Checks |
|---|---:|---|
| `gold_df_dim_date` | 90 | unique dates, 2026-07-10 → 2026-10-07 |
| `gold_df_dim_station` | 5 | one row per station, no null ids |

DAX smoke tests (all match SQL ground truth):

| Check | DAX result | Expected |
|---|---:|---:|
| Stations | 5 | 5 |
| Dates | 90 | 90 |
| Scored days | 273 | 273 |
| Red days | 25 | 25 |
| Amber days | 22 | 22 |
| Green days | 226 | 226 |
| Alerts fired | 17 | 17 |

Additional relationship checks:

| Check | DAX | SQL |
|---|---:|---:|
| Alerts by station A / B / C / D / E | 1 / 5 / 0 / 6 / 5 | 1 / 5 / 0 / 6 / 5 |
| Total excess value at risk | $20,584,946.59 | $20,584,947 |
| Alerts awaiting outcome | 17 | 17 (outcome table empty) |
| Alert rate per station per week | 0.572 | — |

Model table names must remain identical to the Delta table names. The TMDL
source of truth is:

- `fabric/semantic_model/model_spec.py` — physical columns
- `fabric/semantic_model/model_logic.py` — selected tables, measures, relationships
- `fabric/semantic_model/definition/` — generated TMDL, committed for review
- `tools/deploy_semantic_model.py` — build, publish, refresh and smoke tests

---

## 7. Slice 2 result

| Item | Value |
|---|---|
| Report | `rpt_df_early_warning` |
| Report ID | `a76b8d4b-3243-4d5b-b13b-da01c3d298ed` |
| Format | PBIR (Power BI enhanced report format) |
| Page | `execOverview` — “Executive overview” |
| Bound semantic model | `sm_df_early_warning` (`0f5395f6-2365-48a2-ae9d-c6c2e814bc9f`) |
| Web URL | `https://app.powerbi.com/groups/355cd573-8b17-430a-b606-c6b9424d36a1/reports/a76b8d4b-3243-4d5b-b13b-da01c3d298ed` |

Visuals on the page:

| Visual | Type | Fields |
|---|---|---|
| Title | Textbox | Deferment Early Warning + window subtitle |
| Alerts fired | Card | `gold_alert[Alerts Fired]` |
| Open alerts | Card | `gold_alert[Open Alerts]` |
| Excess value at risk | Card | `gold_risk_daily[Excess Value at Risk (USD)]` |
| Stations at Red (latest) | Card | `gold_risk_daily[Stations at Red (latest)]` |
| Data coverage | Card | `gold_risk_daily[Data Coverage %]` |
| Excess value at risk by station | Clustered bar | station × value at risk |
| Scored risk-day mix | Donut | risk tier × `Scored Days` |
| Latest alerts | Table | date, station, tier, excess USD |
| Alerts by date and tier | Column chart | date × tier × `Alerts Fired` |

Verification:

- Report detail API confirms `format: PBIR` and `datasetId` = the semantic model.
- Pages API returns `execOverview` / “Executive overview”.
- PBIR round-trip returns all 16 parts (15 generated + `.platform`).
- PDF export succeeded (68.7 KB, 1 page).
- PDF render checks: **5 filled bars** in the station ranking, **3 filled
donut segments**, latest-alerts rows present, trend chart present.
- Card values in the render: 17 alerts, 17 open, $21M value at risk, 0 stations
  at Red on the latest date, 88.7% coverage.

> The “Stations at Red (latest)” measure uses `COALESCE(..., 0)` so an
> all-green latest day shows **0**, not “(Blank)”.

Report source:

- `fabric/report/report_spec.py` — page layout, visuals, PBIR assembly
- `fabric/report/definition.pbir` + `definition/` — generated PBIR, committed
- `tools/deploy_report.py` — builds, publishes and verifies the report

---

## 8. Slice 3 result

Page 2 (`stationDetail`) is published and PDF-export verified.

| Item | Value |
|---|---|
| Page | `stationDetail` — “Station detail” |
| Default station | **Test Station B** (the outage example) |
| Slicer | single-select `gold_df_dim_station[station_name]`, default B |
| Cards | latest risk score, latest risk tier, latest observed date, excess value at risk |
| Charts | risk score over time; oil actual vs expected |
| Tables | station normal range; recent risk reasons (one row per date) |

Verification:

- Pages API returns `execOverview` and `stationDetail`.
- PDF export: **2 pages, 137,909 bytes**.
- Page 2 subtitle renders; the slicer glyph shows Test Station B selected.
- Cards: 0.000 / Green / 2026-10-07 / $5M; recent-reasons table has one row
  per date and no total row.

Rendered values for the default station (Test Station B):

| Check | Value | Ground truth |
|---|---:|---:|
| Latest risk score | 0.000 | 0.0 |
| Latest risk tier | Green | Green |
| Latest observed date | 2026-10-07 | 2026-10-07 |
| Excess value at risk | $5M | $4,998,669 |
| Normal-range rows | 8 metrics | 8 metrics for station B |
| Recent-reason rows | one per date | one per station-date |

Fixes made during this slice:

1. **Latest measures lost the station filter.** `ALLSELECTED('gold_df_dim_date')`
   in `Latest Risk Score` / `Latest Risk Tier` / `Stations at Red (latest)`
   dropped the slicer filter, so the cards showed another station's score.
   The measures now use
   `CALCULATE(MAX('gold_risk_daily'[date]), 'gold_risk_daily'[is_observed] = TRUE())`
   in the current filter context and filter the **date dimension**.
2. **Fact-date grouping produced duplicate tiers per date.** The recent-reasons
   table now uses `gold_df_dim_date[date]` instead of
   `gold_risk_daily[date]`. It shows one row per station-date.
3. **Subtitle clipped in PDF.** The title textbox height was increased from 55
   px to 65 px; the page-2 subtitle now renders.
4. **Meaningless total row.** The recent-reasons table hides the total row.

> **Rule:** in this model, group and filter dates through `gold_df_dim_date`.
> Fact-date grouping/filtering can lose dimension filters.

---

## 9. Slice 4 result

Page 3 (`deviationHeatmap`) is published and PDF-export verified.

| Item | Value |
|---|---|
| Page | `deviationHeatmap` — “Deviation heatmap” |
| Matrix | rows = metric; columns = calendar month; values = `Bad Z (scored)` |
| Station slicer | dropdown, all stations by default; one station drills in |
| Conditional formatting | light green (better) → white (normal) → light red (worse) |

Fleet heatmap values in the render (all stations, scored rows only):

| Metric | 2026-08 | 2026-09 | 2026-10 | Total |
|---|---:|---:|---:|---:|
| bean | 0.00 | 0.31 | 0.29 | 0.18 |
| deferment_pct | -0.09 | 1.62 | 0.74 | 0.81 |
| deferred_oil | -0.10 | 1.64 | 0.66 | 0.81 |
| oil | 0.18 | 1.17 | 1.33 | 0.78 |
| target_gap_pct | -0.11 | 1.47 | -0.01 | 0.72 |
| thp | -0.68 | -3.72 | 3.07 | -1.64 |
| uptime | -0.08 | 2.55 | 1.10 | 1.29 |
| water_cut | 0.05 | -0.40 | -0.06 | -0.17 |

Verification:

- Pages API returns `execOverview`, `stationDetail` and `deviationHeatmap`.
- PDF export: **3 pages, 216,289 bytes**.
- Matrix shows 8 metrics × 3 scored months (2026-08/09/10) plus totals.
- Conditional-formatting fills were detected in the PDF: light-green and
  light-red cells, not just white. The gradient is min −3, mid 0, max +6.
- The station slicer is a dropdown (a Basic slicer clipped the fifth station at
  this page height).

> **Conditional-formatting trap:** the `objects.values` selector must include
> `metadata` equal to the value queryRef
> (`gold_deviation_daily.Bad Z (scored)`). With only a data wildcard selector,
> the `backColor` FillRule is silently ignored.

---

## 10. Slice 5 result

Pages 4 and 5 are published and PDF-export verified.

### Page 4 — Alert log (`alertLog`)

| Item | Value |
|---|---|
| Slicers | tier, station and month (dropdowns) |
| Cards | 17 alerts, 9 Red, 8 Amber, **$1,316,717** excess USD at alert |
| Table | 17 fired alerts, newest first: date, station, tier, alert type, top signal, risk score, excess USD, reasons |

The table uses `gold_df_dim_date[date]` and `gold_df_dim_station[station_name]`
so the date and station filters are applied correctly.

### Page 5 — Outcomes & lead time (`outcomes`)

| Item | Value |
|---|---|
| Cards | alerts with outcome **0**, confirmed **0**, precision **“No outcomes yet”**, median lead time **“No outcomes yet”**, awaiting **17** |
| Table | empty outcome table: alert date, station, tier, event, event date, lead days, detection, disposition, action note |
| Note | states that `gold_alert_outcome` is intentionally empty until the outcome / lead-time job exists |

The empty state is deliberate and explicit. Precision and lead time are not
invented; they will populate when the outcome job runs.

### Verification

- Pages API returns all five pages.
- PDF export: **5 pages, 312,554 bytes**.
- Alert counts match SQL: 17 total, 9 Red, 8 Amber.
- Excess USD at alert: **$1,316,717**.
- The alert log shows all 17 rows.
- The outcome page shows 0 / 0 / “No outcomes yet” / “No outcomes yet” / 17,
  and the outcome table is empty by design.

### Fix

`COUNTROWS` on the empty `gold_alert_outcome` Direct Lake table returns
**blank**, not 0. `Alerts with Outcome` and `Alerts Confirmed` are now wrapped in
`COALESCE(..., 0)` so the cards show 0 rather than “(Blank)”.

---

## 11. Slice 6 result

The build is now orchestrated end to end.

| Item | Value |
|---|---|
| Pipeline | `pl_df_daily_build` |
| Pipeline ID | `5612dc63-d473-4457-8b90-6ca93aa62412` |
| Schedule ID | `c039be42-53ec-4e69-a793-a7302ea29031` |
| Schedule | **Daily at 06:00 UTC**, enabled from 2026-10-23 to 2027-10-23 |
| End-to-end run | `f994239e-6d08-44db-a8da-72d31e5e36a7` — **Completed** |
| Runtime | ~24 minutes on F2 (seven notebooks) |

### What the pipeline does

```text
Run_notebooks (ForEach, sequential)
  ├── nb_01_bronze_ingest
  ├── nb_02_silver_conform
  ├── nb_03_gold_features
  ├── nb_04_gold_risk_alerts
  ├── nb_07_df_alert_outcomes
  ├── nb_05_df_gold_dimensions
  └── nb_06_df_dq_gate
        ↓ (Succeeded)
     done
        ↓ (Failed after retries)
  Webhook_configured
     ├── true  → Send_failure_alert (WebActivity)
     └── false → Wait 1s
        ↓
  Fail_pipeline (Fail, errorCode DF_DAILY_BUILD_FAILED)
```

- The seven notebooks are passed as a pipeline parameter (`notebook_ids`), so a
  backfill or partial run can override the list.
- Each notebook activity has **retry 2** with a 120-second interval and a
  2-hour timeout.
- The DQ gate (`nb_06_df_dq_gate`) is **warn-only**; it writes
  `gold_pipeline_dq_log` and never blocks the pipeline.

### Verification

- Pipeline run **Completed**; all seven notebooks ran (confirmed by notebook job
  instances, including `nb_07` and `nb_06` in the latest run).
- Gold counts after the run: `gold_risk_daily` 450, `gold_alert` 17,
  `gold_df_dim_date` 90, `gold_df_dim_station` 5.
- DQ log: **3 batches × 12 checks = 36 rows, all OK**. The third batch came
  from the latest pipeline run.
- Failure path tested with a temporary pipeline containing an invalid notebook
  id: status **Failed**, error code **`DF_DAILY_BUILD_FAILED`**, clear message.
  The probe was deleted afterwards.
- Daily schedule confirmed via the schedules API: enabled, daily, 06:00 UTC.

### Notes and limits

- The optional webhook alert is **empty by default**. Set
  `alert_webhook_url` (pipeline parameter) to a Teams incoming-webhook URL to
  receive a push alert. Without it, the pipeline still fails visibly with
  `DF_DAILY_BUILD_FAILED` in the Monitoring hub.
- The pipeline does **not** refresh the semantic model. Direct Lake
  auto-refreshes when the report is queried; an explicit model refresh can be
  added later if needed.
- `gold_pipeline_dq_log` is an operational table; it is not in the semantic
  model.
- Existing pipelines `pl_deferment_daily` and `pl_sc_analytics` were left
  untouched.

---

## 12. Slice 7 result

`gold_alert_outcome` is now populated automatically by
`nb_07_df_alert_outcomes`.

| Item | Value |
|---|---|
| Notebook | `nb_07_df_alert_outcomes` |
| Notebook ID | `db3753c3-9b77-4341-8e43-194646352681` |
| Manual run | `2df90f27-b1fc-46ae-bc9d-204cc5be119c` — Completed |
| Pipeline run | `f994239e-6d08-44db-a8da-72d31e5e36a7` — Completed |
| Outcome rows | **17** (one per alert) |
| Confirmed | **14** |
| False alarms | **3** |
| Pending | **0** |
| Median lead time | **2.0 days** |
| Mean lead time | **2.5 days** |
| Precision | **82.4%** |
| False-alarm rate | **17.6%** |

### Definition used

- **H = 7 days.** The event must be strictly **after** the alert date.
- **Coded onset:** a coded deferment episode starts at the same station within
  the window.
- **Large-loss onset:** deferred oil reaches the station’s own p90 after
  **3 quiet observed days** below p90.
- **Pending:** the 7-day window extends beyond the data and no event has
  occurred yet.
- `actual_lead_days = event_date − alert_date` (1–7 for a confirmed future
  event).

The 3 false alarms are Test Station D on 2026-09-18, Test Station E on
2026-09-26, and Test Station E on 2026-09-28. The Station B example remains a
useful one: the Amber alert on 2026-09-08 is confirmed by a large-loss onset
on 2026-09-10, **2 days later**.

### Safety

- The notebook uses a Delta `MERGE` by `alert_id`.
- Manual fields are preserved: `acknowledged_by`, `acknowledged_at_utc`,
  `action_note`, `false_reason`.
- A non-computed `disposition` is preserved; a computed `pending` row can later
  become `confirmed` or `false_alarm`.
- `Alerts with Outcome` in the model counts only **evaluated** rows
  (`event_occurred` not null), so pending rows do not depress precision.

### Report

The outcomes page now shows **17 / 14 / 82.4% / 2.0 days / 0** and a 17-row
outcome table. PDF export: **5 pages, 323,611 bytes**.

> **Definition note:** same-day events are not counted as future onsets. An
> alert that fires on the event day can still be confirmed by a later onset;
> this is deliberate, because the KPI is “did a new event follow the alert?”,
> not “was the alert raised on the event day?”.

---

## 12a. Slice 8 result

The parity harness is `tools/parity_check.py`; the clean-room reference is
`tools/parity_reference.py`. The report is
`docs/fabric-parity-check-slice8.md` (machine-readable result:
`test_data/parity/parity-result.json`, git-ignored).

| Check | Result |
|---|---|
| Tables compared | 15 (7 silver, 8 gold) |
| Local rows vs Fabric rows | identical for every table |
| Row key sets | identical, no left/right-only rows |
| Risk tiers (scored observed) | 25 Red / 22 Amber / 226 Green |
| Alerts | 17 (9 Red / 8 Amber) |
| Outcomes | 14 confirmed / 3 false / 0 pending |
| Median / mean lead time | 2.0 / 2.5 days |
| Precision / false-alarm rate | 82.4% / 17.6% |
| Dimensions | 90 dates / 5 stations |
| Excess value at risk | $20,584,946.59 |
| Excess USD at alert | $1,316,716.74 |
| Verdict | **PASS** |

Documented differences:

1. **8 feature rows** where `oil` and `target_gap_pct` have equal `|z|` by
   construction. Sub-1e-15 runtime differences choose which one is labelled
   `top_signal`; the risk score, tier and alerts are unaffected.
2. **11 `uptime_roll_std_7` values** differ by at most `7.6e-7` around a true
   value of zero (constant-window floating-point dust).

Defect found: `silver_deferment_episode.episode_id` is not unique (70
duplicate rows, 68 duplicated ids) because it omits `cause_group`. The
outcome job does not use the id, so parity is unaffected; tracked as ISS-018.

---

## 12b. Slice 9 result

The experiment is `tools/onset_model.py`; the report is
`docs/slice9-onset-model-report.md`.

| Target | Model PR-AUC | Rules PR-AUC | Model alerts (c/f, lead) | Rules alerts (c/f, lead) | Gate |
|---|---:|---:|---|---|---|
| `material` (primary) | **0.706** | 0.603 | 9 / 4, 2.0 d | **10 / 3, 3.0 d** | **fail** |
| `large_loss` | **0.401** | 0.178 | 4 / 9, 3.5 d | 4 / 9, **4.5 d** | **fail** |
| `coded_material` | **0.680** | 0.564 | **10 / 3, 3.5 d** | 8 / 5, 3.5 d | **fail** (no lead gain) |

Decision: **keep rules v1**. The model is a ranking challenger only.

---

## 13. Verification queries (SQL ground truth)

```bash
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT COUNT(*) FROM dbo.gold_df_dim_date"

FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT risk_tier, COUNT(*) FROM dbo.gold_risk_daily
   WHERE is_observed=1 AND baseline_phase='scored' GROUP BY risk_tier"

FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT COUNT(*) FROM dbo.gold_alert"
```

Model checks use the Power BI `executeQueries` API:
`POST /v1.0/myorg/groups/{workspaceId}/datasets/{semanticModelId}/executeQueries`.

### 13.1 Report render check

The report is verified by exporting it to PDF through the Power BI API:

1. `POST /v1.0/myorg/groups/{workspaceId}/reports/{reportId}/ExportTo`
   with `{"format": "PDF"}` → `202` + operation `Location`.
2. Poll the `Location` until `status: Succeeded`.
3. Download `resourceLocation` **with the Power BI bearer token** (the URL is not
   anonymous).
4. Optionally render page 1 to PNG with PyMuPDF and inspect the chart regions.

For Slice 2 the PDF was 68.7 KB / 1 page. The station ranking had 5 filled
bars, the tier donut had 3 filled segments, the latest-alerts table and the
alert trend were present.

---

## 14. Traps

- Do not rename the physical tables to friendly names after creating the model.
- Do not add `schemaName` for this non-schema lakehouse; omit it.
- Do not add `/Tables` to the OneLake expression or use display names; use the
  ID-based lakehouse root.
- Do not use calculated tables/columns in the Direct Lake model; keep
  dimensions physical.
- **Use `gold_df_dim_date[date]` for date axes, table date columns and date
  filters.** Fact-date grouping/filtering can drop dimension filters.
- Do not use `ALLSELECTED('gold_df_dim_date')` inside a measure that must
  respect a station slicer; it can drop the station filter.
- Direct Lake refresh can take a few seconds on F2. Poll refresh history.
- The SQL endpoint metadata can lag; use `spark.read` or OneLake when in doubt.
- `gold_alert` is rebuilt by `nb_04`. In production, merge by `alert_key` so
  delivery state survives. `gold_alert_outcome` must be preserved.
- The seed is synthetic and anonymised. The 17 alerts are a starting alert
  budget, not a tuned production threshold.
- The PBIR file is generated; re-run `tools/deploy_report.py` after changing
  `report_spec.py`. Do not hand-edit `definition.pbir` (it carries the bound
  model id).
- PDF export needs the Power BI token; the download URL is not anonymous.
- Conditional formatting in PBIR needs a selector with `metadata` matching the
  value queryRef; otherwise `backColor` is silently ignored.
- `COUNTROWS` on an empty Direct Lake table returns blank. Wrap count measures
  in `COALESCE(..., 0)` when the empty state should read as zero.
- The daily pipeline takes ~15 minutes on F2. Do not overlap manual runs with
  the 06:00 UTC schedule.
- The DQ log table can take a few minutes to appear in the SQL endpoint after
  its first write; the Delta table itself exists immediately.
- The failure webhook is empty by default. Set `alert_webhook_url` to a Teams
  incoming webhook to receive a push alert.
- Outcomes use a **future** event only (strictly after the alert). A same-day
  large loss does not count as a lead; the alert may still be confirmed by a
  later onset.
- `gold_alert_outcome` is merged by `alert_id`; manual acknowledgement fields
  are preserved. Do not overwrite the table wholesale.
- `Alerts with Outcome` counts only evaluated rows. Pending rows have
  `event_occurred = null` and belong in “awaiting outcome”.
- On this page a Basic station slicer clipped the fifth station; use the
  dropdown mode for compact station filters.
- The latest-alerts table is narrow (300 px). Widen or move it in a later slice
  if the station/date labels start to truncate.
