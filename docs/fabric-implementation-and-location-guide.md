# Fabric implementation and location guide

**Project:** Deferment Early-Warning Solution — Advanced Analytics & AI (Part 1, Project 1)
**Environment:** `maf` sandbox, Wragby tenant
**Scope:** How the solution was built in Fabric, what each item does, and where to find it
**Status:** Through Slice 8 (parity check) — complete and verified in the sandbox; Slice 9 Layer 2 experiment is documented separately
**Last updated:** 2026-10-22

---

## 1. Purpose of this guide

This document explains:

1. What was built in Fabric.
2. How each piece was implemented.
3. Where each item lives in the Fabric UI, OneLake and the repository.

It is the implementation and navigation companion to:

- `docs/fabric-build-summary-through-slice8.md` — full build summary
- `docs/fabric-build-log-maf-sandbox.md` — live build log and evidence
- `docs/fabric-semantic-model-and-report-plan.md` — serving-layer plan
- `docs/fabric-parity-check-slice8.md` — Slice 8 parity report
- `docs/slice9-onset-model-report.md` — Slice 9 Layer 2 experiment (rejected; rules v1 retained)

---

## 2. What was built

A complete deferment early-warning MVP in the **`maf`** workspace on the **F2 capacity in North Europe**.

```text
Seed CSVs
  → lh_bronze   raw files + 11 bronze Delta tables
  → lh_silver   12 conformed Delta tables
  → lh_gold     baselines, features, deviations, risk, alerts,
                outcomes, dimensions and DQ tables
  → sm_df_early_warning   Direct Lake semantic model
  → rpt_df_early_warning  5-page PBIR report
  → pl_df_daily_build     daily orchestration + warn-only DQ gate
```

Current seed-window results:

| Metric | Value |
|---|---:|
| Stations | 5 |
| Dates | 90 (2026-07-10 → 2026-10-07) |
| Observed station-days | 399 / 450 (88.7%) |
| Scored observed rows | 273 |
| Red / Amber / Green | 25 / 22 / 226 |
| Alerts | 17 (9 Red / 8 Amber) |
| Confirmed / false outcomes | 14 / 3 |
| Median lead time | 2.0 days |
| Mean lead time | 2.5 days |
| Precision / false-alarm rate | 82.4% / 17.6% |
| Excess value at risk | $20,584,946.59 |
| Excess USD at alert | $1,316,716.74 |

The data is synthetic/anonymised and is not production truth.

---

## 3. Fabric environment

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

All lakehouses share the SQL server; the **database name** selects the lakehouse.

### 3.1 Lakehouses

| Lakehouse | ID | Contents |
|---|---|---|
| `lh_bronze` | `0cde2eb7-937b-49c6-a4ed-b95bd66dc49e` | `Files/raw`, `Files/ref`, 11 `bronze_*` Delta tables |
| `lh_silver` | `b6d8fe8b-bad2-4ac5-a605-f0b13893df7f` | 12 `silver_*` Delta tables |
| `lh_gold` | `df9a08e5-b370-4c2a-b608-6d0f326003ef` | Features, risk, alerts, outcomes, dimensions and DQ |

### 3.2 Notebooks and default lakehouses

| Notebook | ID | Default lakehouse |
|---|---|---|
| `nb_01_bronze_ingest` | `7b53bc2e-e4f9-49f4-a0ec-18f33ad7a74f` | `lh_bronze` |
| `nb_02_silver_conform` | `aee945bd-02a7-49aa-adaa-f57799106b05` | `lh_silver` |
| `nb_03_gold_features` | `31649865-f498-427c-91c7-fd77ed5eeb8d` | `lh_gold` |
| `nb_04_gold_risk_alerts` | `ed822f3c-c442-47f6-82f4-d7313f7f6e2a` | `lh_gold` |
| `nb_05_df_gold_dimensions` | `effcd5bf-f960-4523-9028-661e0f6401fe` | `lh_gold` |
| `nb_06_df_dq_gate` | `a6ffe2c4-5de0-4bbf-9f5e-2d663fb96a0a` | `lh_gold` |
| `nb_07_df_alert_outcomes` | `db3753c3-9b77-4341-8e43-194646352681` | `lh_gold` |

### 3.3 Serving and operations items

| Item | Type | ID |
|---|---|---|
| `sm_df_early_warning` | Semantic model (Direct Lake) | `0f5395f6-2365-48a2-ae9d-c6c2e814bc9f` |
| `rpt_df_early_warning` | Report (PBIR) | `a76b8d4b-3243-4d5b-b13b-da01c3d298ed` |
| `pl_df_daily_build` | Data pipeline | `5612dc63-d473-4457-8b90-6ca93aa62412` |
| Daily schedule | Pipeline schedule | `c039be42-53ec-4e69-a793-a7302ea29031` |

---

## 4. How it was built in Fabric

### 4.1 Sandbox provisioning and seed upload

The tenant had no OML 24 source data. Seed data was generated locally:

```bash
python tools/generate_test_data.py --env sandbox --days 90 --anonymise --force
```

This produced:

```text
test_data/sandbox/raw/
  production_fact.csv
  deferment_fact.csv
  flowstations_dim.csv
  deferment_category_dim.csv
  deferment_subcategory_dim.csv

test_data/sandbox/ref/
  dim_date.csv
  dim_asset.csv
  dim_station.csv
  dim_well.csv
  oil_prices.csv
  owner_map.csv
```

The files were uploaded to:

```text
lh_bronze/Files/raw/
lh_bronze/Files/ref/
```

Provisioning and upload are handled by:

- `tools/provision_sandbox.py`
- `tools/fabric_items.py`

No existing workspace item was modified.

### 4.2 Notebook deployment

Notebooks are authored locally as `.ipynb` files under `fabric/notebooks/`, then published into Fabric with:

```bash
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/nb_01_bronze_ingest.ipynb
```

They run on Fabric Spark. Each notebook has a default lakehouse attached and uses PySpark/pandas. Delta tables are written through OneLake ABFSS paths and registered with:

```sql
CREATE TABLE IF NOT EXISTS <name>
USING DELTA LOCATION '<abfss-path>'
```

Runs can be triggered and polled with:

```bash
python tools/run_notebook.py --env sandbox --name nb_03_gold_features
```

### 4.3 Bronze ingestion — `nb_01_bronze_ingest`

What it does:

- Reads CSVs from `lh_bronze/Files/raw` and `Files/ref`.
- Writes 11 Delta tables to `lh_bronze/Tables/bronze_*`.
- Adds audit columns:
  - `_batch_id`
  - `_ingested_at_utc`
  - `_source_file`
- Overwrites the bronze snapshot each run.

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

### 4.4 Silver conformance — `nb_02_silver_conform`

What it does:

- Casts IDs, volumes and dates.
- Trims strings.
- Deduplicates `production_id` and `deferment_id`.
- Normalises blank cause IDs to `Unknown`.
- Marks `Mismatch` / `Unknown` as `is_coded = false`.
- Deduplicates station-level `target_oil` using `max` per station-day.
- Builds `silver_station_day` from production plus deferment aggregates.
- Reconstructs deferment episodes.
- Writes a silver DQ audit table.

| Table | Rows | Grain |
|---|---:|---|
| `silver_production_day` | 5,226 | production string-day |
| `silver_deferment_event` | 5,225 | deferment event |
| `silver_station_day` | 399 | observed flow station-day |
| `silver_deferment_episode` | 1,004 | station × string × cause episode |
| `silver_dim_date` | 90 | date |
| `silver_dim_station` | 5 | station |
| `silver_dim_well` | 67 | well / production string |
| `silver_dim_cause_group` | 23 | category |
| `silver_dim_cause_code` | 66 | sub-category |
| `silver_oil_prices` | 90 | date |
| `silver_owner_map` | 5 | station |
| `silver_data_quality` | 16 | metric/value |

Key design decision: `silver_station_day` has only **observed** station-days (399, not 450). Gold builds the complete grid so missing data is explicit.

### 4.5 Gold features — `nb_03_gold_features`

What it does:

1. Builds the complete **5 × 90 = 450-row** station-date grid.
2. Learns per-station baselines on the **first 28 calendar days**:
   - median / MAD
   - robust scale with IQR and floors
   - p10 / p90
   - shrunk weekday profile (75% weekday / 25% overall)
3. Applies baselines forward and computes per metric:
   - `expected`
   - `deviation`
   - `robust_z` (capped at ±25)
   - percentage deviation
   - direction
   - outlier flag
4. Adds:
   - lags 1 and 7
   - deltas 1 and 7
   - rolling means and std (7 and 28)
   - EWMA
   - 7-day slope
   - two-sided CUSUM
5. Adds composite deviation score, top signal and reasons.
6. Adds barrel and USD value context.
7. Labels rows as `estimation` or `scored`; only scored rows can alert.

Metrics: oil, deferred oil, deferment %, target-gap %, uptime, THP, bean/choke and water cut.

| Table | Rows |
|---|---:|
| `gold_entity_baseline` | 40 |
| `gold_entity_day_features` | 450 |
| `gold_deviation_daily` | 3,111 |
| `gold_data_quality` | 20 |

### 4.6 Risk and alerts — `nb_04_gold_risk_alerts`

Rules v1:

- Only bad-direction deviations count.
- Each signal capped at 6σ.
- Weights:

```text
deferment % 0.25 · oil 0.20 · uptime 0.15 · deferred oil 0.10
target gap 0.10 · THP 0.10 · water cut 0.05 · bean 0.05
```

- Score:

```text
risk_score = 1 - exp(-max(0, weighted - 0.5) / 2)
```

- **Red:** high score, sustained score, multiple strong signals, or ≥ $250k at risk.
- **Amber:** moderate score, sustained deterioration, slow signal run, or material value at risk.
- Fire on change into Amber/Red or escalation to Red.
- 3-day cooldown.
- No reasons, no alert.
- Estimation rows are `Unscored`; unobserved rows are `NoData`.

| Table | Rows |
|---|---:|
| `gold_risk_daily` | 450 |
| `gold_alert` | 17 |
| `gold_risk_data_quality` | 20 |

### 4.7 Dimensions — `nb_05_df_gold_dimensions`

Builds two physical Delta dimensions:

| Table | Rows |
|---|---:|
| `gold_df_dim_date` | 90 |
| `gold_df_dim_station` | 5 |

They are physical tables, not DAX calculated tables, so the Direct Lake model stays fully Direct Lake. The notebook asserts unique dates, unique stations and no null station IDs.

### 4.8 Outcomes — `nb_07_df_alert_outcomes`

For each alert, looks 7 days forward:

| Outcome | Rule |
|---|---|
| Confirmed — coded onset | Coded episode starts after the alert, within 7 days, same station |
| Confirmed — large loss | Deferred oil reaches the station's own p90 after 3 quiet observed days |
| False alarm | Full 7-day window and no event |
| Pending | Window extends beyond the data and no event has occurred |

`actual_lead_days = event_date − alert_date`. Same-day events do not count as leads.

The notebook uses a Delta `MERGE` by `alert_id`, preserving manual acknowledgement fields.

### 4.9 Semantic model — `sm_df_early_warning`

Direct Lake semantic model over `lh_gold`.

Tables:

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

Published from TMDL with `tools/deploy_semantic_model.py`, refreshed via the Power BI API and smoke-tested with DAX.

Direct Lake constraints applied:

- Model table names must equal physical Delta table names.
- Omit `schemaName` for this non-schema lakehouse.
- Use the ID-based OneLake root, no `/Tables`.
- Keep dimensions physical.
- Group/filter dates through `gold_df_dim_date`.
- Avoid `ALLSELECTED('gold_df_dim_date')` in measures that must respect a station slicer.
- Wrap `COUNTROWS` on potentially empty tables in `COALESCE`.

### 4.10 Report — `rpt_df_early_warning`

PBIR report bound to `sm_df_early_warning`. Five pages:

| Page | Contents |
|---|---|
| Executive overview | KPI cards, station ranking, tier mix, latest alerts, alert trend |
| Station detail | Station slicer (default B), latest risk cards, risk/oil lines, normal-range table, recent reasons |
| Deviation heatmap | 8 metrics × month matrix of bad-direction z with green/white/red formatting |
| Alert log | Tier/station/month slicers, 4 cards, 17-row alert table |
| Outcomes & lead time | 17 / 14 / 82.4% / 2.0 days / 0 cards, 17-row outcome table |

Generated from `fabric/report/report_spec.py`, published with `tools/deploy_report.py`, verified by PDF export.

### 4.11 Orchestration — `pl_df_daily_build`

Pipeline order:

```text
nb_01_bronze_ingest
  → nb_02_silver_conform
  → nb_03_gold_features
  → nb_04_gold_risk_alerts
  → nb_07_df_alert_outcomes
  → nb_05_df_gold_dimensions
  → nb_06_df_dq_gate
```

Behaviour:

- Sequential ForEach
- Retry 2× with 120-second interval
- 2-hour per-notebook timeout
- Failure branch with `DF_DAILY_BUILD_FAILED`
- Optional Teams webhook
- Daily schedule at 06:00 UTC
- Runtime roughly 15–25 minutes on F2

`nb_06_df_dq_gate` is warn-only and writes `gold_pipeline_dq_log` with 12 checks per batch.

### 4.12 Parity check — Slice 8

`tools/parity_check.py` compares Fabric with `tools/parity_reference.py`, a clean-room pandas implementation of the same documented rules over the same seed CSVs.

Result: **PASS**.

- 15 tables compared: 7 silver, 8 gold.
- Row counts and key sets identical.
- Risk tiers, alerts, outcomes, dimensions and headline KPIs match.
- Two benign differences:
  - 8 feature rows where `oil` and `target_gap_pct` have equal `|z|`; sub-1e-15 runtime differences choose `top_signal`.
  - 11 `uptime_roll_std_7` values differ by at most `7.6e-7` around true zero.
- Defect found: `silver_deferment_episode.episode_id` is not unique because it omits `cause_group` — 70 duplicate rows, 68 duplicated IDs. Tracked as **ISS-018**.

---

## 5. Where to find everything in Fabric

Open:

```text
https://app.fabric.microsoft.com/
```

Sign in to the Wragby tenant, then open **Workspaces → `maf`**.

### 5.1 Lakehouses and tables

| What | Where |
|---|---|
| Bronze files | `maf` → `lh_bronze` → **Files** → `raw/`, `ref/` |
| Bronze tables | `maf` → `lh_bronze` → **Tables** → `bronze_*` |
| Silver tables | `maf` → `lh_silver` → **Tables** → `silver_*` |
| Gold tables | `maf` → `lh_gold` → **Tables** → `gold_*` |

To inspect a table:

1. Open the lakehouse.
2. Expand **Tables** in the left pane.
3. Select the table.
4. Use the preview grid.
5. For SQL, open the **SQL analytics endpoint** from the lakehouse ribbon.

Physical OneLake paths:

```text
abfss://355cd573-8b17-430a-b606-c6b9424d36a1@onelake.dfs.fabric.microsoft.com/<lakehouse-id>/Tables/<table>
```

### 5.2 Notebooks

**Workspace → Notebooks → `<notebook name>`**

- `nb_01_bronze_ingest`
- `nb_02_silver_conform`
- `nb_03_gold_features`
- `nb_04_gold_risk_alerts`
- `nb_05_df_gold_dimensions`
- `nb_06_df_dq_gate`
- `nb_07_df_alert_outcomes`

Run history is available from each notebook and from the Monitoring hub.

### 5.3 Pipeline

**Workspace → Data pipelines → `pl_df_daily_build`**

Use:

- **Run history** for notebook-level status.
- **Schedule** for the daily 06:00 UTC schedule.
- **Monitoring hub** for all workspace runs.

### 5.4 Semantic model

**Workspace → Semantic models → `sm_df_early_warning`**

Use:

- **Refresh history**
- **Open data model**
- DAX query view

### 5.5 Report

**Workspace → Reports → `rpt_df_early_warning`**

Pages:

- Executive overview
- Station detail
- Deviation heatmap
- Alert log
- Outcomes & lead time

Recorded report URL:

```text
https://app.powerbi.com/groups/355cd573-8b17-430a-b606-c6b9424d36a1/reports/a76b8d4b-3243-4d5b-b13b-da01c3d298ed
```

### 5.6 SQL endpoint

From any lakehouse, open the **SQL analytics endpoint**.

```text
Server: lnzik4a56abe3li4wgukn5cbay-opkvynixrmfehnqgy24uetjwue.datawarehouse.fabric.microsoft.com
Database: lh_bronze | lh_silver | lh_gold
```

Example:

```bash
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT risk_tier, COUNT(*) FROM dbo.gold_risk_daily
   WHERE is_observed=1 AND baseline_phase='scored' GROUP BY risk_tier"
```

### 5.7 Repository locations

| Area | Path |
|---|---|
| Notebook sources | `fabric/notebooks/` |
| Semantic model source | `fabric/semantic_model/` |
| Report source | `fabric/report/` |
| Pipeline definition | `fabric/pipeline/pipeline-content.json` |
| Deployment scripts | `tools/deploy_*.py` |
| Sandbox setup | `tools/provision_sandbox.py` |
| Seed generation | `tools/generate_test_data.py` |
| Query tool | `tools/fabric_query.py` |
| Parity harness | `tools/parity_check.py`, `tools/parity_reference.py` |
| Layer 2 backtest | `tools/onset_model.py` |
| Build log | `docs/fabric-build-log-maf-sandbox.md` |
| Serving plan | `docs/fabric-semantic-model-and-report-plan.md` |
| Parity report | `docs/fabric-parity-check-slice8.md` |
| Full summary | `docs/fabric-build-summary-through-slice8.md` |
| Open defect | `Issues/ISS-018-episode-id-not-unique.md` |

---

## 6. Verification evidence

| Check | Evidence |
|---|---|
| Bronze | 11 tables, row counts match source CSVs |
| Silver | 12 tables, 399 station-days, 801 coded events (15.33%), 0 duplicate IDs |
| Gold features | 450 grid rows, 399 observed, 273 scored, 266 outliers |
| Risk | 25 Red / 22 Amber / 226 Green, 17 alerts |
| Outcomes | 14 confirmed / 3 false, median 2.0 days, precision 82.4% |
| Dimensions | 90 dates, 5 stations, unique keys |
| Semantic model | Refresh Completed, DAX matches SQL |
| Report | PDF export verified, 5 pages |
| Pipeline | End-to-end Completed; failure path tested |
| DQ gate | 12 checks per batch, all OK |
| Parity | PASS, 15 tables, KPIs match |

---

## 7. Known limitations and next steps

Limitations:

- Seed data is synthetic/anonymised.
- Baseline uses only 28 days.
- THP and bean are near-constant in the seed.
- Rules v1 is not tuned for production.
- F2 is slow.
- The pipeline does not explicitly refresh the semantic model; Direct Lake auto-refreshes.
- `gold_alert` is overwritten by `nb_04` in the sandbox; production should merge by `alert_key`.
- `episode_id` is not unique — ISS-018.
- No Layer 2 model, RLS, app publication, Data Activator or real-time historian yet.

Next:

1. Fix **ISS-018**.
2. Build the **Layer 2 onset model**, only if it beats rules v1 on lead time at the same alert budget.
3. Production hardening: real data, longer history, tuned alert budget, formal prototype parity, RLS/app publication, Data Activator, monitoring, real-time historian.

---

## 8. One-paragraph handover

The `maf` sandbox now contains a complete deferment early-warning MVP: three lakehouses with bronze/silver/gold Delta tables, seven notebooks, a Direct Lake semantic model, a five-page Power BI report, a daily pipeline with retries and a warn-only DQ gate, and a passing parity check against an independent local implementation. On the 90-day seed it produces 17 alerts (9 Red / 8 Amber), 14 confirmed outcomes and 3 false alarms, with a median lead time of 2.0 days and 82.4% precision. It is ready for the Layer 2 modelling experiment, subject to fixing the duplicate episode ID and validating on real production data.
