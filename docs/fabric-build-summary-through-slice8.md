# Fabric build summary through Slice 8

**Project:** Deferment Early-Warning Solution — Advanced Analytics & AI (Part 1, Project 1)
**Environment:** `maf` sandbox, Wragby tenant
**Status:** Through **Slice 8 (parity check)** — complete and verified in the sandbox
**Last updated:** 2026-10-22

**Companion guide:** `docs/fabric-implementation-and-location-guide.md` — detailed Fabric implementation, item IDs and UI navigation.  
**Follow-on:** `docs/slice9-onset-model-report.md` — Layer 2 v1 was tested and rejected; rules v1 remains the alert engine.

---

## 1. Executive summary

A complete deferment early-warning MVP has been built end to end in Microsoft Fabric using a 90-day anonymised seed window for **OML 24** and **5 flow stations**.

The build runs from raw CSVs to a five-page Power BI report:

```text
Seed CSVs
  → lh_bronze (raw + audit columns)
  → lh_silver (conformed production, deferment, station-day and episode tables)
  → lh_gold (baselines, features, deviations, risk, alerts, outcomes, dimensions)
  → sm_df_early_warning (Direct Lake semantic model)
  → rpt_df_early_warning (5-page PBIR report)
  → pl_df_daily_build (daily orchestration + warn-only DQ gate)
``` 

The solution is deliberately a **transparent rules-v1 MVP**:

- No trained onset model yet.
- No deep learning, forecasting or black-box scoring.
- Risk is explained by bad-direction deviations from each station's own normal.
- Every alert carries its reasons.
- Outcomes are measured after the fact, so lead time and false alarms are real numbers rather than claims.

The sandbox data is **synthetic/anonymised** and must not be treated as production truth. The historical local prototype code was not available in the repository for Slice 8, so parity was checked against a clean-room pandas implementation of the same documented rules.

---

## 2. What the system does

The problem is framed as **event prediction**, not oil-volume forecasting:

1. Learn each station's normal behaviour from the first 28 days.
2. Measure how far today's oil, deferment, uptime, THP, bean, water cut and target gap deviate from that normal.
3. Count only deviations in the **bad** direction.
4. Combine them into a 0–1 risk score.
5. Assign Red / Amber / Green tiers.
6. Fire alerts only when a station **changes into** Amber/Red or escalates to Red.
7. Record whether a coded onset or large-loss event followed the alert within 7 days.
8. Report risk, deviations, alerts, outcomes and lead time in Power BI.

The current seed result:

| Metric | Value |
|---|---:|
| Stations | 5 |
| Dates | 90 (2026-07-10 → 2026-10-07) |
| Observed station-days | 399 / 450 (88.7%) |
| Scored observed rows | 273 |
| Red / Amber / Green days | 25 / 22 / 226 |
| Alerts | 17 (9 Red / 8 Amber) |
| Confirmed outcomes | 14 |
| False alarms | 3 |
| Median lead time | 2.0 days |
| Mean lead time | 2.5 days |
| Precision | 82.4% |
| False-alarm rate | 17.6% |
| Excess value at risk | $20,584,946.59 |
| Excess USD at alert | $1,316,716.74 |

---

## 3. Environment and item inventory

### 3.1 Workspace and capacity

| Item | Value |
|---|---|
| Tenant | `wragbysolutions.com` |
| Workspace | `maf` |
| Workspace ID | `355cd573-8b17-430a-b606-c6b9424d36a1` |
| Capacity | `mafcapacity` |
| Capacity ID | `f874d5a0-467b-493c-aa43-ef099de4c979` |
| SKU | **F2** |
| Region | **North Europe** |
| SQL endpoint | `lnzik4a56abe3li4wgukn5cbay-opkvynixrmfehnqgy24uetjwue.datawarehouse.fabric.microsoft.com` |

All three lakehouses share the same SQL server; the **database name** selects the lakehouse (`lh_bronze`, `lh_silver`, `lh_gold`).

### 3.2 Lakehouses

| Lakehouse | ID | Contents |
|---|---|---|
| `lh_bronze` | `0cde2eb7-937b-49c6-a4ed-b95bd66dc49e` | `Files/raw`, `Files/ref` and 11 `bronze_*` Delta tables |
| `lh_silver` | `b6d8fe8b-bad2-4ac5-a605-f0b13893df7f` | 12 `silver_*` Delta tables |
| `lh_gold` | `df9a08e5-b370-4c2a-b608-6d0f326003ef` | Baselines, features, deviations, risk, alerts, outcomes, dimensions and DQ tables |

### 3.3 Notebooks

| Notebook | ID | Default lakehouse |
|---|---|---|
| `nb_01_bronze_ingest` | `7b53bc2e-e4f9-49f4-a0ec-18f33ad7a74f` | `lh_bronze` |
| `nb_02_silver_conform` | `aee945bd-02a7-49aa-adaa-f57799106b05` | `lh_silver` |
| `nb_03_gold_features` | `31649865-f498-427c-91c7-fd77ed5eeb8d` | `lh_gold` |
| `nb_04_gold_risk_alerts` | `ed822f3c-c442-47f6-82f4-d7313f7f6e2a` | `lh_gold` |
| `nb_05_df_gold_dimensions` | `effcd5bf-f960-4523-9028-661e0f6401fe` | `lh_gold` |
| `nb_06_df_dq_gate` | `a6ffe2c4-5de0-4bbf-9f5e-2d663fb96a0a` | `lh_gold` |
| `nb_07_df_alert_outcomes` | `db3753c3-9b77-4341-8e43-194646352681` | `lh_gold` |

### 3.4 Serving and operations items

| Item | Type | ID |
|---|---|---|
| `sm_df_early_warning` | Semantic model (Direct Lake) | `0f5395f6-2365-48a2-ae9d-c6c2e814bc9f` |
| `rpt_df_early_warning` | Report (PBIR) | `a76b8d4b-3243-4d5b-b13b-da01c3d298ed` |
| `pl_df_daily_build` | Data pipeline | `5612dc63-d473-4457-8b90-6ca93aa62412` |
| Daily schedule | Pipeline schedule | `c039be42-53ec-4e69-a793-a7302ea29031` |

---

## 4. How the build was done in Fabric

### 4.1 Sandbox provisioning and seed upload

The new tenant had no OML 24 source data. The sandbox was seeded from the existing local extracts using:

```bash
python tools/generate_test_data.py --env sandbox --days 90 --anonymise --force
```

This produced the CSVs under `test_data/sandbox/raw` and `test_data/sandbox/ref`. They were uploaded to:

- `lh_bronze/Files/raw/`
- `lh_bronze/Files/ref/`

The upload uses the Fabric/OneLake API and is driven by `tools/provision_sandbox.py` plus the REST helpers in `tools/fabric_items.py`.

### 4.2 Notebooks: author locally, deploy and run in Fabric

The notebooks are versioned as `.ipynb` files in `fabric/notebooks/`. They are deployed into the workspace with:

```bash
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/nb_01_bronze_ingest.ipynb
```

They run on Fabric Spark in the F2 capacity. Each notebook has a default lakehouse attached (see the table in §3.3). The notebooks use PySpark and pandas, read/write Delta through OneLake ABFSS paths, and register tables with:

```sql
CREATE TABLE IF NOT EXISTS <name> USING DELTA LOCATION '<path>'
```

Run and poll helper:

```bash
python tools/run_notebook.py --env sandbox --name nb_03_gold_features
```

### 4.3 Bronze ingestion

`nb_01_bronze_ingest`:

- Reads the uploaded CSVs from `lh_bronze/Files`.
- Writes 11 Delta tables to `lh_bronze/Tables/bronze_*`.
- Adds audit columns: `_batch_id`, `_ingested_at_utc`, `_source_file`.
- Overwrites the bronze snapshot on every run.

Bronze tables:

| Table | Rows |
|---|---:|
| `bronze_production_fact` | 5,226 |
| `bronze_deferment_fact` | 5,225 |
| `bronze_flowstations_dim` | 5 |
| `bronze_deferment_category_dim` | 23 |
| `bronze_deferment_subcategory_dim` | 66 |
| `bronze_dim_asset` | 3 |
| `bronze_dim_date` | 90 |
| `bronze_dim_station` | 5 |
| `bronze_dim_well` | 67 |
| `bronze_oil_prices` | 90 |
| `bronze_owner_map` | 5 |

### 4.4 Silver conformance

`nb_02_silver_conform`:

- Cast IDs, volumes and dates.
- Trim string fields.
- Deduplicate production and deferment IDs.
- Normalise blank cause IDs to `Unknown`.
- Mark `Mismatch` / `Unknown` as `is_coded = false`.
- Deduplicate station-level `target_oil` using `max` per station-day.
- Build the full station-day mart from production plus deferment aggregates.
- Reconstruct deferment episodes from consecutive loss days.
- Write a silver DQ audit table.

Silver tables:

| Table | Rows |
|---|---:|
| `silver_production_day` | 5,226 |
| `silver_deferment_event` | 5,225 |
| `silver_station_day` | 399 |
| `silver_deferment_episode` | 1,004 |
| `silver_dim_date` | 90 |
| `silver_dim_station` | 5 |
| `silver_dim_well` | 67 |
| `silver_dim_cause_group` | 23 |
| `silver_dim_cause_code` | 66 |
| `silver_oil_prices` | 90 |
| `silver_owner_map` | 5 |
| `silver_data_quality` | 16 |

Key design decision: `silver_station_day` contains only **observed** station-days (399, not the full 450). The gold layer builds the complete grid so missing data is explicit.

### 4.5 Gold features and baselines

`nb_03_gold_features`:

1. Builds the complete **5 × 90 = 450-row** station-date grid.
2. Learns per-station baselines on the first **28 calendar days**:
   - median and MAD
   - robust scale with IQR and absolute floors
   - p10/p90
   - day-of-week profile, shrunk 75% weekday / 25% overall
3. Applies the baseline forward and writes, per metric:
   - `expected`
   - `deviation`
   - `robust_z` (capped at ±25)
   - percentage deviation
   - direction
   - outlier flag
4. Adds sequential features:
   - lags 1 and 7
   - deltas 1 and 7
   - rolling means/std 7 and 28
   - EWMA
   - 7-day slope
   - two-sided CUSUM
5. Adds a composite deviation score, top signal, reasons and `signals_json`.
6. Adds barrel and USD value context.
7. Labels rows inside the estimation window as `estimation`; only `scored` rows can alert, preventing in-sample leakage.

Metrics: oil, deferred oil, deferment %, target-gap %, uptime, THP, bean/choke and water cut.

Gold feature tables:

| Table | Rows |
|---|---:|
| `gold_entity_baseline` | 40 |
| `gold_entity_day_features` | 450 |
| `gold_deviation_daily` | 3,111 |
| `gold_data_quality` | 20 |

### 4.6 Rules-v1 risk and alerts

`nb_04_gold_risk_alerts`:

- Counts only **bad-direction** deviations.
- Caps each signal at 6σ.
- Applies weights:

| Signal | Weight |
|---|---:|
| Deferment % | 0.25 |
| Oil | 0.20 |
| Uptime | 0.15 |
| Deferred oil | 0.10 |
| Gap to target % | 0.10 |
| THP | 0.10 |
| Water cut | 0.05 |
| Bean/choke | 0.05 |

```text
risk_score = 1 - exp(-max(0, weighted_severity - 0.5) / 2)
```

- **Red:** score ≥ 0.70, sustained high score, multiple strong signals, or ≥ $250k value at risk.
- **Amber:** score ≥ 0.40, sustained moderate score, slow deterioration, or material value at risk.
- **Fire on change:** only entry into Amber/Red or escalation to Red.
- **Cooldown:** 3 days to stop flip-flopping.
- **No reasons, no alert.**
- Estimation rows are `Unscored`; unobserved rows are `NoData`.

Tables:

| Table | Rows |
|---|---:|
| `gold_risk_daily` | 450 |
| `gold_alert` | 17 |
| `gold_risk_data_quality` | 20 |

`gold_alert_outcome` starts empty and is preserved on rerun.

### 4.7 Dimensions

`nb_05_df_gold_dimensions` builds two physical Delta dimensions in `lh_gold`:

| Table | Rows | Grain |
|---|---:|---|
| `gold_df_dim_date` | 90 | one row per date |
| `gold_df_dim_station` | 5 | one row per station |

They are physical tables rather than DAX calculated tables so the Direct Lake model stays fully Direct Lake. The date range and station list come from `gold_risk_daily`, not hard-coded values. The notebook asserts date uniqueness, station uniqueness and no null station IDs.

### 4.8 Alert outcomes and lead time

`nb_07_df_alert_outcomes` fills `gold_alert_outcome` with a 7-day forward-looking outcome:

| Outcome | Rule |
|---|---|
| Confirmed — coded onset | A coded episode starts after the alert, within 7 days, same station |
| Confirmed — large loss | Deferred oil reaches the station's own p90 after 3 quiet observed days |
| False alarm | Full 7-day window available and neither event occurs |
| Pending | Window extends beyond the data and no event has occurred |

`actual_lead_days = event_date − alert_date` for confirmed future events. Same-day events do not count as a lead.

The notebook uses a Delta `MERGE` by `alert_id` so manual acknowledgement fields are preserved.

### 4.9 Semantic model

`sm_df_early_warning` is a **Direct Lake** semantic model over `lh_gold` with seven tables:

- `gold_risk_daily`
- `gold_deviation_daily`
- `gold_alert`
- `gold_alert_outcome`
- `gold_entity_baseline`
- `gold_df_dim_date`
- `gold_df_dim_station`

Relationships:

- date → risk, deviations, alerts
- station → risk, deviations, alerts, baseline
- alert → outcome

Published with TMDL via `tools/deploy_semantic_model.py`, refreshed through the Power BI API, and smoke-tested with DAX against SQL ground truth.

Direct Lake constraints encountered and applied:

- Model table names must exactly match the physical Delta table names.
- Omit `schemaName` for this non-schema lakehouse.
- Use the ID-based OneLake root, with no `/Tables` suffix.
- Keep dimensions physical; do not use calculated tables/columns.
- Group and filter dates through `gold_df_dim_date`.
- Do not use `ALLSELECTED('gold_df_dim_date')` in measures that must respect a station slicer.
- Wrap `COUNTROWS` on potentially empty Direct Lake tables in `COALESCE(..., 0)`.

### 4.10 Power BI report

`rpt_df_early_warning` is a **PBIR** report bound to `sm_df_early_warning`, with five pages:

| Page | Page ID | Contents |
|---|---|---|
| Executive overview | `execOverview` | 5 KPI cards, station ranking, tier mix, latest alerts, alert trend |
| Station detail | `stationDetail` | station slicer (default B), latest-risk cards, risk/oil lines, normal-range table, recent reasons |
| Deviation heatmap | `deviationHeatmap` | 8 metrics × month matrix of bad-direction z, green/white/red formatting |
| Alert log | `alertLog` | tier/station/month slicers, 4 cards, 17-row alert table |
| Outcomes & lead time | `outcomes` | 17 / 14 / 82.4% / 2.0 days / 0 cards, 17-row outcome table |

The report is generated from `fabric/report/report_spec.py` and published with `tools/deploy_report.py`. It is verified by exporting to PDF through the Power BI API and checking the rendered pages.

### 4.11 Orchestration and DQ gate

`pl_df_daily_build` runs the seven notebooks in this order:

```text
nb_01_bronze_ingest
  → nb_02_silver_conform
  → nb_03_gold_features
  → nb_04_gold_risk_alerts
  → nb_07_df_alert_outcomes
  → nb_05_df_gold_dimensions
  → nb_06_df_dq_gate
```

Pipeline behaviour:

- Sequential ForEach execution
- Retry 2× with a 120-second interval
- 2-hour per-notebook timeout
- Failure branch with error code `DF_DAILY_BUILD_FAILED`
- Optional Teams webhook (empty by default)
- Daily schedule at **06:00 UTC**
- Runtime roughly 15–25 minutes on F2

`nb_06_df_dq_gate` is **warn-only**. It writes `gold_pipeline_dq_log` and runs 12 checks per batch: row counts, grid completeness, dates, z cap, alert reconciliation and feature/deviation presence. It never blocks the pipeline.

The pipeline is generated from `fabric/pipeline/pipeline-content.json` and deployed with `tools/deploy_pipeline.py`.

### 4.12 Parity check — Slice 8

`tools/parity_check.py` compares Fabric output with `tools/parity_reference.py`, a clean-room pandas implementation of the documented notebook rules, over the same seed CSVs.

What is compared:

- 7 silver tables
- 8 gold tables
- Row counts and key sets
- Numeric values with `atol=1e-6`, `rtol=1e-9`
- Text fields
- JSON payloads semantically

Result: **PASS**.

- All tables have identical row counts and key sets.
- Risk tiers, alerts, outcomes, dimensions and headline KPIs match.
- Two benign differences:
  - 8 feature rows where `oil` and `target_gap_pct` have equal `|z|`; sub-1e-15 runtime differences decide the `top_signal` label. Risk score/tier/alerts are unaffected.
  - 11 `uptime_roll_std_7` values differ by at most `7.6e-7` around true zero.
- Defect found: `silver_deferment_episode.episode_id` is not unique (70 duplicate rows, 68 duplicated IDs) because it omits `cause_group`. Tracked as **ISS-018**. It does not affect outcomes because outcome matching uses station + episode start + cause code.

---

## 5. Slice-by-slice history

| Slice | Deliverable | Status |
|---|---|---|
| Foundation | Sandbox, lakehouses, seed data, bronze, silver, gold features/risk | ✅ |
| Slice 1 | `gold_df_dim_date`, `gold_df_dim_station`, `sm_df_early_warning` | ✅ |
| Slice 2 | Executive overview report page | ✅ |
| Slice 3 | Station detail page | ✅ |
| Slice 4 | Deviation heatmap page | ✅ |
| Slice 5 | Alert log and outcomes pages | ✅ |
| Slice 6 | `pl_df_daily_build`, DQ gate, daily schedule | ✅ |
| Slice 7 | `nb_07_df_alert_outcomes`, realised lead time | ✅ |
| Slice 8 | Fabric-vs-local parity check | ✅ |

---

## 6. Where to find everything in Fabric

### 6.1 Open the workspace

1. Go to `https://app.fabric.microsoft.com/`.
2. Sign in to the Wragby tenant.
3. Open **Workspaces** in the left rail.
4. Select **`maf`**.

Everything below is inside the `maf` workspace.

### 6.2 Lakehouses and tables

| What | Where |
|---|---|
| Bronze files | `maf` → `lh_bronze` → **Files** → `raw/` and `ref/` |
| Bronze tables | `maf` → `lh_bronze` → **Tables** → `bronze_*` |
| Silver tables | `maf` → `lh_silver` → **Tables** → `silver_*` |
| Gold tables | `maf` → `lh_gold` → **Tables** → `gold_*` |

To inspect a table:

1. Open the lakehouse.
2. In the left pane, expand **Tables**.
3. Select the table.
4. Use the **Preview** / data grid.
5. For SQL, open the **SQL analytics endpoint** from the lakehouse ribbon or the workspace item list.

The physical OneLake paths follow:

```text
abfss://355cd573-8b17-430a-b606-c6b9424d36a1@onelake.dfs.fabric.microsoft.com/<lakehouse-id>/Tables/<table>
```

Do not edit Delta tables directly in `Files`; use the notebooks or SQL.

### 6.3 Notebooks

| Notebook | Open from |
|---|---|
| `nb_01_bronze_ingest` | `maf` → **Notebooks** → `nb_01_bronze_ingest` |
| `nb_02_silver_conform` | `maf` → **Notebooks** → `nb_02_silver_conform` |
| `nb_03_gold_features` | `maf` → **Notebooks** → `nb_03_gold_features` |
| `nb_04_gold_risk_alerts` | `maf` → **Notebooks** → `nb_04_gold_risk_alerts` |
| `nb_05_df_gold_dimensions` | `maf` → **Notebooks** → `nb_05_df_gold_dimensions` |
| `nb_06_df_dq_gate` | `maf` → **Notebooks** → `nb_06_df_dq_gate` |
| `nb_07_df_alert_outcomes` | `maf` → **Notebooks** → `nb_07_df_alert_outcomes` |

Each notebook has its default lakehouse already attached. Run history is available from the notebook toolbar and from the Monitoring hub.

### 6.4 Pipeline and schedule

1. Open `maf`.
2. Select **Data pipelines**.
3. Open **`pl_df_daily_build`**.
4. Use **Run history** to see notebook-level status and durations.
5. Use **Schedule** to see the daily 06:00 UTC schedule (`c039be42-53ec-4e69-a793-a7302ea29031`).
6. Use the **Monitoring hub** to see all runs in one place, filtered to `maf`.

The pipeline passes notebook IDs as a parameter, so a partial or backfill run can override the list.

### 6.5 Semantic model

1. Open `maf`.
2. Select **Semantic models**.
3. Open **`sm_df_early_warning`**.
4. Use **Refresh history** to confirm the latest refresh.
5. Use **Open data model** / DAX query view to inspect tables, relationships and measures.

The model is Direct Lake over `lh_gold`; it does not import a copy of the data.

### 6.6 Report

1. Open `maf`.
2. Select **Reports**.
3. Open **`rpt_df_early_warning`**.
4. Use the page navigator for:
   - Executive overview
   - Station detail
   - Deviation heatmap
   - Alert log
   - Outcomes & lead time

Direct report URL recorded during the build:

```text
https://app.powerbi.com/groups/355cd573-8b17-430a-b606-c6b9424d36a1/reports/a76b8d4b-3243-4d5b-b13b-da01c3d298ed
```

### 6.7 SQL queries

Use the read-only query tool from the repository:

```bash
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT risk_tier, COUNT(*) FROM dbo.gold_risk_daily
   WHERE is_observed=1 AND baseline_phase='scored' GROUP BY risk_tier"
```

Change `FABRIC_SQL_DATABASE` to `lh_silver` or `lh_bronze` for other layers.

### 6.8 Repository locations

| Area | Path |
|---|---|
| Notebook sources | `fabric/notebooks/` |
| Semantic model source | `fabric/semantic_model/` |
| Report source | `fabric/report/` |
| Pipeline definition | `fabric/pipeline/pipeline-content.json` |
| Deployment tools | `tools/deploy_*.py` |
| Sandbox provisioning | `tools/provision_sandbox.py` |
| Seed generation | `tools/generate_test_data.py` |
| Query tool | `tools/fabric_query.py` |
| Parity harness | `tools/parity_check.py`, `tools/parity_reference.py` |
| Build log | `docs/fabric-build-log-maf-sandbox.md` |
| Serving plan | `docs/fabric-semantic-model-and-report-plan.md` |
| Parity report | `docs/fabric-parity-check-slice8.md` |
| Open defect | `Issues/ISS-018-episode-id-not-unique.md` |

---

## 7. Verification evidence

The build was verified at every layer:

| Check | Evidence |
|---|---|
| Bronze | 11 tables, row counts match source CSVs |
| Silver | 12 tables, DQ 399 station-days, 801 coded events (15.33%), 0 duplicate IDs |
| Gold features | 450 grid rows, 399 observed, 273 scored, 266 outliers |
| Risk | 25 Red / 22 Amber / 226 Green, 17 alerts |
| Outcomes | 14 confirmed / 3 false, median 2.0 days, precision 82.4% |
| Dimensions | 90 dates, 5 stations, unique keys |
| Semantic model | Refresh Completed, DAX matches SQL ground truth |
| Report | PDF export verified, 5 pages, visuals and cards checked |
| Pipeline | End-to-end Completed, failure path tested with `DF_DAILY_BUILD_FAILED` |
| DQ gate | 12 checks per batch, all OK |
| Parity | PASS, 15 tables, headline KPIs match |

---

## 8. Known limitations

### Data and modelling

- Seed data is synthetic/anonymised, not production truth.
- Baseline uses only 28 days; production needs longer history.
- THP and bean are near-constant in the seed, so their deviations look like step changes.
- The real extract has a high share of `Mismatch` cause codes, limiting cause-specific models.
- Rules v1 is not tuned against a production alert budget.
- Value at risk is current excess over normal, not a forecast of future production.
- Same-day events are not counted as leads.

### Operations

- F2 is the smallest SKU; Spark runs are slow and can throttle.
- The pipeline does not explicitly refresh the semantic model; Direct Lake auto-refreshes on query.
- The failure webhook is empty by default.
- `gold_alert` is overwritten by `nb_04` in the sandbox; production should merge by `alert_key` so delivery/acknowledgement state survives.
- SQL endpoint metadata can lag behind Delta writes.

### Known defect

- **ISS-018:** duplicate `episode_id` because `cause_group` is omitted. Fix before using it as a join key.

---

## 9. What remains

1. **Fix ISS-018** and re-run the pipeline and parity check.
2. **Layer 2 onset model**, only if it beats rules v1 on lead time at the same alert budget:
   - onset labels
   - LightGBM / onset model
   - chronological backtest
   - head-to-head vs rules v1
   - keep only if it adds lead time at equal false alarms
3. **Production hardening:**
   - real data and longer history
   - tuned alert budget
   - formal parity against the original prototype if its code is recovered
   - RLS, app publication and Data Activator delivery
   - monitoring and model/version governance
   - real-time historian feed if required

---

## 10. One-paragraph handover

The `maf` sandbox now contains a complete deferment early-warning MVP: bronze/silver/gold Delta tables in three lakehouses, a Direct Lake semantic model, a five-page Power BI report, a daily pipeline with retries and a warn-only DQ gate, and a passing parity check against an independent local implementation. On the 90-day seed it produces 17 alerts (9 Red / 8 Amber), 14 confirmed outcomes and 3 false alarms, with a median lead time of 2.0 days and 82.4% precision. It is ready for the Layer 2 modelling experiment, subject to fixing the duplicate episode ID and validating on real production data.
