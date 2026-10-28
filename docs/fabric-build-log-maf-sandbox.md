# Fabric build log — `maf` sandbox

> Deferment early-warning build in the **Wragby Business Solutions & Technology**
> Fabric tenant.
>
> **Last updated:** 2026-10-22
> **Status:** Bronze ✅ · Silver ✅ · Gold ✅ (features, risk and alerts) · Serving ✅ (dimensions + Direct Lake model) · Report ✅ (5 pages) · Orchestration ✅ (daily pipeline) · Outcomes ✅ · Parity ✅ · Layer 2 ❌ (rejected)

---

## 1. Purpose

This document records what has been built so far in the new Fabric environment,
why each piece exists, the exact identifiers, how it was verified, and what
remains. It is the operational handover for the sandbox build.

The build follows the medallion design in
`technology-stack-and-fabric-implementation.md`:

```
lh_bronze  →  lh_silver  →  lh_gold
raw / audit   conformed      features, risk, alerts
```

---

## 2. Environment

| Item | Value |
|---|---|
| Tenant | `wragbysolutions.com` |
| Tenant ID | `7085725b-f01d-4d02-ad1c-b1a8a6f44106` |
| Signed-in user | `<Azure CLI account in the Wragby tenant>` (email redacted) |
| Workspace | `maf` |
| Workspace ID | `355cd573-8b17-430a-b606-c6b9424d36a1` |
| Workspace type | Fabric |
| Capacity | `mafcapacity` |
| Capacity ID | `f874d5a0-467b-493c-aa43-ef099de4c979` |
| SKU | **F2** |
| Region | **North Europe** |
| SQL analytics endpoint | `lnzik4a56abe3li4wgukn5cbay-opkvynixrmfehnqgy24uetjwue.datawarehouse.fabric.microsoft.com` |

All lakehouses share the same SQL server; the **database name selects the
lakehouse** (`lh_bronze`, `lh_silver`, `lh_gold`).

### 2.1 Build lakehouses created

| Lakehouse | ID | Purpose |
|---|---|---|
| `lh_bronze` | `0cde2eb7-937b-49c6-a4ed-b95bd66dc49e` | Raw CSV files + bronze Delta tables |
| `lh_silver` | `b6d8fe8b-bad2-4ac5-a605-f0b13893df7f` | Conformed event, production, station-day and episode tables |
| `lh_gold` | `df9a08e5-b370-4c2a-b608-6d0f326003ef` | Baselines, station-day features, deviations, risk, alerts and outcomes |

---

## 3. What was left untouched

The workspace already contained other work. **No existing item was edited,
deleted or uploaded into.** The following were inventoried and left as-is:

| Existing item | Type | Notes |
|---|---|---|
| `maf_lake` | Lakehouse | Contains `asset_registry.csv`, `compressor_readings.csv`, `maintenance_history.csv` |
| `StagingLakehouseForDataflows_20260608140408` | Lakehouse | Dataflow staging |
| `StagingWarehouseForDataflows_20260608140422` | Warehouse | Dataflow staging |
| `maf-data-agent` | Data Agent | Existing |
| `push_table_into_warehouse` | Notebook | Existing |
| `deferement_newcross` | Notebook | Confirmed **empty**; definition retrieved read-only and ignored |

The sandbox build uses only the three new lakehouses and two new notebooks
listed below.

---

## 4. Build topology

```
maf (workspace)
├── lh_bronze
│   ├── Files/raw/*.csv            ← uploaded seed extracts
│   ├── Files/ref/*.csv            ← reference / price / owner tables
│   └── Tables/bronze_*            ← 11 Delta tables
│
├── nb_01_bronze_ingest   ────────── reads Files/, writes bronze_*
│
├── lh_silver
│   └── Tables/silver_*            ← 12 Delta tables
│
├── nb_02_silver_conform  ────────── reads bronze, writes silver
│
└── lh_gold
    └── Tables/gold_*            ← baselines, features, deviations, risk, alerts

nb_03_gold_features   ────────── reads silver, writes gold feature tables
nb_04_gold_risk_alerts ───────── reads gold features, writes risk + alerts
nb_05_df_gold_dimensions ─────── reads gold, writes gold_df_dim_date / gold_df_dim_station

sm_df_early_warning   ────────── Direct Lake semantic model over the seven gold tables
rpt_df_early_warning  ────────── PBIR report; executive, station detail, heatmap, alert log and outcomes pages built
nb_06_df_dq_gate      ────────── warn-only data-quality gate; writes gold_pipeline_dq_log
pl_df_daily_build     ────────── runs nb_01 → nb_06 sequentially; daily 06:00 UTC
```

---

## 5. Seed data

The new tenant had no source data. We seeded from the existing local extracts
in `data/` (git-ignored) using `tools/generate_test_data.py`.

### 5.1 Command

```bash
python tools/generate_test_data.py --env sandbox --days 90 --anonymise --force
```

### 5.2 What was produced

| Output | Rows |
|---|---:|
| `raw/production_fact.csv` | 5,226 |
| `raw/deferment_fact.csv` | 5,225 |
| `raw/flowstations_dim.csv` | 5 |
| `raw/deferment_category_dim.csv` | 23 |
| `raw/deferment_subcategory_dim.csv` | 66 |
| `ref/dim_date.csv` | 90 |
| `ref/dim_asset.csv` | 3 |
| `ref/dim_station.csv` | 5 |
| `ref/dim_well.csv` | 67 |
| `ref/oil_prices.csv` | 90 |
| `ref/owner_map.csv` | 5 |

- Window: **2026-07-10 → 2026-10-07** (90 days).
- Station/well/asset names anonymised (`Test Station A…E`, `TST…`).
- Output: `test_data/sandbox/{raw,ref}/`.
- Manifest: `test_data/sandbox/_manifest.json`.
- Fabric record: `test_data/sandbox/_fabric_items.json`.

### 5.3 Known seed warnings

The source extract contains blanks, preserved deliberately:

- **93** deferment rows with a blank `category_id`.
- **17** deferment rows with a blank `subcategory_id`.

These are normalised to `Unknown` in silver, never treated as zero.

---

## 6. Bronze layer

### 6.1 Notebook

| Item | Value |
|---|---|
| Name | `nb_01_bronze_ingest` |
| ID | `7b53bc2e-e4f9-49f4-a0ec-18f33ad7a74f` |
| Source | `fabric/notebooks/nb_01_bronze_ingest.ipynb` |
| Run ID | `f4bd40df-3ecd-43fb-82cc-71fb75d1b40e` |
| Status | **Completed** |

### 6.2 What it does

1. Reads the uploaded CSVs from `lh_bronze/Files/raw` and `Files/ref`.
2. Writes Delta tables to `lh_bronze/Tables/bronze_*`.
3. Adds audit columns:
   - `_batch_id`
   - `_ingested_at_utc`
   - `_source_file`
4. Overwrites the bronze snapshot on each run (idempotent).

### 6.3 Tables

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

All **11** tables are visible through the `lh_bronze` SQL endpoint.

---

## 7. Silver layer

### 7.1 Notebook

| Item | Value |
|---|---|
| Name | `nb_02_silver_conform` |
| ID | `aee945bd-02a7-49aa-adaa-f57799106b05` |
| Source | `fabric/notebooks/nb_02_silver_conform.ipynb` |
| Run ID | `de41fd90-b912-43a7-8fee-8a884548c434` |
| Status | **Completed** |
| Runtime | ~2m 18s |

The notebook's default lakehouse is `lh_silver`, so `saveAsTable` registers the
silver tables in the correct item.

### 7.2 Transformations applied

- Cast IDs, volumes and dates from CSV strings to typed values.
- Trim string fields.
- Deduplicate on `production_id` and `deferment_id` (latest batch wins).
- Normalise blank `category_id` / `subcategory_id` to `Unknown`.
- `is_coded` = false for `Mismatch` and `Unknown`.
- Deduplicate station-level `target_oil` (`max` per station-day) into
  `station_target_oil`.
- Reconstruct episodes from consecutive loss days (gap > 1 day starts a new
  episode).
- Build a data-quality audit table.

### 7.3 Tables

| Table | Rows | Grain |
|---|---:|---|
| `silver_production_day` | 5,226 | production string-day |
| `silver_deferment_event` | 5,225 | deferment event |
| `silver_station_day` | 399 | flow station-day (observed only) |
| `silver_deferment_episode` | 1,004 | station × string × cause episode |
| `silver_dim_date` | 90 | date |
| `silver_dim_station` | 5 | station |
| `silver_dim_well` | 67 | well / production string |
| `silver_dim_cause_group` | 23 | category (L1) |
| `silver_dim_cause_code` | 66 | sub-category (L2) |
| `silver_oil_prices` | 90 | date |
| `silver_owner_map` | 5 | station |
| `silver_data_quality` | 16 | metric/value |

All **12** tables are visible through the `lh_silver` SQL endpoint.

### 7.4 Data-quality results

| Metric | Value |
|---|---:|
| Date range | 2026-07-10 → 2026-10-07 |
| Stations | 5 |
| Wells | 67 |
| Production rows | 5,226 |
| Deferment events | 5,225 |
| Coded events | 801 (**15.33%**) |
| Unknown-cause events | 17 (**0.33%**) |
| Duplicate production IDs | 0 |
| Duplicate deferment IDs | 0 |
| THP missing | 0.04% |
| Bean missing | 4.67% |
| Station-days | 399 |

The coded-event share is close to the ~13.5% found in the full history, so the
seed behaves like the real data.

### 7.5 Episodes

- **1,004 episodes**
- Average duration **5.23 days**
- Longest episode **23 days**
- All **5,225 events** assigned to an episode

### 7.6 Important design note

`silver_station_day` contains only **observed** station-days (399, not the full
5 × 90 = 450 grid). This is deliberate: **missing is not zero**. The gold layer
will build the complete station-date grid and carry an explicit `is_observed`
flag so absence of a feed is not mistaken for zero production.

---

## 8. Gold features

### 8.1 Notebook

| Item | Value |
|---|---|
| Name | `nb_03_gold_features` |
| ID | `31649865-f498-427c-91c7-fd77ed5eeb8d` |
| Source | `fabric/notebooks/nb_03_gold_features.ipynb` |
| Latest run ID | `3f5d89d1-359e-46e4-8611-07e668c976a4` |
| Status | **Completed** |
| Runtime | ~70s |

### 8.2 What it does

1. Builds the **complete station-date grid** (5 stations × 90 dates = 450 rows).
   `silver_station_day` has only observed days, so the grid is explicit and
   `is_observed` marks the rest. **Missing is not zero.**
2. Learns **per-station baselines** on the first **28 calendar days** only:
   median, MAD, robust scale, p10/p90 and a shrunk day-of-week profile.
3. Applies the baseline forward and writes, per metric, `expected`, `deviation`,
   `robust_z`, `pct_deviation`, direction and an outlier flag.
4. Adds lag, rolling, delta, slope, EWMA and two-sided CUSUM features, plus
   plain-language reasons and barrel/USD context.
5. Marks rows inside the estimation window as `baseline_phase = estimation`;
   only `scored` rows are eligible for alerts. This prevents in-sample leakage.

Metrics: oil, deferred oil, deferment %, target-gap %, uptime, THP, bean/choke,
water cut. Robust z is capped at ±25 so a static seed signal cannot dominate.

### 8.3 Tables

| Table | Rows | Grain |
|---|---:|---|
| `gold_entity_baseline` | 40 | station × metric (5 × 8) |
| `gold_entity_day_features` | 450 | station × date (complete grid) |
| `gold_deviation_daily` | 3,111 | station × date × observed metric |
| `gold_data_quality` | 20 | metric/value |

### 8.4 Results

| Metric | Value |
|---|---:|
| Baseline version | `gold-v1-20260806` |
| Estimation window | 2026-07-10 → 2026-08-06 (28 days) |
| Observed station-days | 399 |
| Unobserved station-days | 51 |
| Grid completeness | 88.67% |
| Scored observed rows | 273 |
| Estimation observed rows | 126 |
| Outliers (`|z| ≥ 3`) | 266 |
| Largest deviation | Test Station B 2026-09-10, oil z = −25 (outage day) |

Observed counts per station: A 78, B 79, C 79, D 80, E 83. The 51 missing
station-days are preserved as nulls with `is_observed = false`.

---

## 9. Gold risk and alerts

### 9.1 Notebook

| Item | Value |
|---|---|
| Name | `nb_04_gold_risk_alerts` |
| ID | `ed822f3c-c442-47f6-82f4-d7313f7f6e2a` |
| Source | `fabric/notebooks/nb_04_gold_risk_alerts.ipynb` |
| Latest run ID | `76d8fa74-c064-45eb-9229-f942b4f480cb` |
| Status | **Completed** |
| Runtime | ~65s |

### 9.2 Rules v1

A transparent, rule-based score — no model is trained yet.

- Only **bad-direction** deviations count; each signal is capped at 6σ.
- Weights: deferment % 0.25, oil 0.20, uptime 0.15, deferred oil 0.10,
  target gap 0.10, THP 0.10, water cut 0.05, bean 0.05.
- `risk_score = 1 − exp(−max(0, weighted − 0.5) / 2)` → 0 to ~0.92.
- **Red** requires corroborating signals, a sustained score, or ≥ $250k at risk.
- **Amber** adds a “slow deterioration” path: a primary signal (oil, deferment %,
  deferred oil or THP) stays ≥ 1.5σ for 3 scored days.
- **Fire on change**: only entry into Amber/Red or escalation to Red fires.
  Same-tier days are suppressed; a 3-day cooldown stops flip-flopping.
- **No reasons, no alert.** Reasons are bad-direction only and use percentage
  points for ratio metrics.

Value at risk uses the station’s own normal deferment rate, its p90 and current
run-rate. `exp_usd` is the **excess over normal**, not a production forecast.

### 9.3 Tables

| Table | Rows | Grain |
|---|---:|---|
| `gold_risk_daily` | 450 | station × date (complete grid) |
| `gold_alert` | 17 | one row per fired alert (deterministic dedup key) |
| `gold_alert_outcome` | 0 | alert outcome skeleton; preserved on rerun |
| `gold_risk_data_quality` | 20 | metric/value |

### 9.4 Results

| Metric | Value |
|---|---:|
| Scored observed rows | 273 |
| Red days | 25 |
| Amber days | 22 |
| Green days | 226 |
| Alerts fired | 17 (9 Red, 8 Amber) |
| Suppressed: no change | 26 |
| Suppressed: de-escalation | 14 |
| Suppressed: cooldown | 0 |
| Alert rate | ~0.38 per station per week |
| Top alert | Test Station B, 2026-09-10, Red, **$457,750** at risk |

The Station B outage is a useful lead-time example: an **Amber fired on
2026-09-08**, two days before the 2026-09-10 Red/collapse, on a sustained
below-normal oil signal. The model has no forecast power beyond the signals in
the data; this is process-deviation detection, not a crystal ball.

---

## 10. Verification performed

| Check | Method | Result |
|---|---|---|
| Tenant / workspace access | Azure CLI + Fabric REST | OK |
| Lakehouse SQL connectivity | `fabric_query.py --test` | `SELECT 1` OK |
| Uploaded file sizes | OneLake DFS listing | All 11 CSVs match local sizes |
| Bronze table presence | OneLake `Tables` listing | 11 tables |
| Bronze row counts | SQL endpoint | 5,226 / 5,225 / 5 |
| Silver table presence | OneLake `Tables` listing | 12 tables |
| Silver row counts + DQ | DuckDB over downloaded Delta Parquet | Matches notebook output |
| SQL endpoint metadata | `INFORMATION_SCHEMA.TABLES` | 11 bronze + 12 silver + 8 gold visible |
| Gold grid | SQL count/distinct | 450 rows, 450 unique station-dates |
| Gold observed flag | SQL count | 399 observed, 51 unobserved, all unobserved levels null |
| Gold feature invariants | Notebook asserts | No alerts outside scored observed rows; alert keys unique |
| Gold risk counts | SQL | 273 scored → 25 Red / 22 Amber / 226 Green |
| Gold alerts | SQL | 17 alerts, dedup keys unique, outcome table empty |
| Dimensions | Notebook asserts + SQL | `gold_df_dim_date` 90 unique dates; `gold_df_dim_station` 5 stations |
| Direct Lake model | Fabric REST + refresh history | `sm_df_early_warning` refresh **Completed** |
| Model smoke tests | DAX `executeQueries` | 5 stations, 90 dates, 273 scored, 25 Red / 22 Amber / 226 Green, 17 alerts |
| Model relationships | DAX vs SQL | Alerts by station 1 / 5 / 0 / 6 / 5; total excess USD matches SQL |
| Report publish | Fabric Report API | `rpt_df_early_warning`, format PBIR, bound to `sm_df_early_warning` |
| Report render | Power BI `ExportTo` PDF | 68.7 KB, 1 page; 5 bars, 3 donut segments, alert table and trend present |
| Station page render | Power BI `ExportTo` PDF | 2 pages; default Station B shows 0.000 / Green / 2026-10-07 / $5M |
| Station filters | DAX vs SQL | Latest measures and recent-reasons table respect the station slicer; one row per date |
| Heatmap render | PDF export | 3 pages, 216,289 bytes; metric × month matrix with green/red conditional formatting |
| Alert log render | PDF export | 5 pages, 312,554 bytes; 17 alerts, 9 Red / 8 Amber, $1,316,717 at alert |
| Outcomes empty state | DAX + PDF | 0 outcomes, 0 confirmed, “No outcomes yet”, 17 awaiting; table empty by design |
| Pipeline end-to-end | Fabric Pipeline job | `pl_df_daily_build` Completed; six notebooks ran; ~15 min on F2 |
| Pipeline failure path | Probe with invalid notebook id | Failed with `DF_DAILY_BUILD_FAILED` and a clear message |
| DQ gate | `gold_pipeline_dq_log` | 2 runs × 12 checks = 24 rows, all OK |
| Daily schedule | Schedules API | Enabled, daily 06:00 UTC, 2026-10-23 → 2027-10-23 |

### 10.1 Useful verification commands

```bash
# which profile is live?
python tools/fabric_query.py --env sandbox --show-env

# connection test
python tools/fabric_query.py --env sandbox --test

# bronze tables
FABRIC_SQL_DATABASE=lh_bronze \
  python tools/fabric_query.py --env sandbox \
  "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'bronze_%'"

# silver data-quality metrics
FABRIC_SQL_DATABASE=lh_silver \
  python tools/fabric_query.py --env sandbox \
  "SELECT metric, value FROM dbo.silver_data_quality ORDER BY metric"
```

> The lakehouse SQL endpoint metadata can lag by a few minutes after a notebook
> writes new tables. Spark and Direct Lake reads are unaffected. In this build
> it caught up and now shows all tables.

Gold checks:

```bash
# feature grid and observed counts
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT COUNT(*) rows, SUM(CASE WHEN is_observed=1 THEN 1 ELSE 0 END) observed FROM dbo.gold_entity_day_features"

# risk tiers
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT risk_tier, COUNT(*) FROM dbo.gold_risk_daily WHERE is_observed=1 GROUP BY risk_tier"

# fired alerts
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT alert_date, station_name, tier, risk_reasons FROM dbo.gold_alert ORDER BY exp_usd DESC"

# dimensions
FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT (SELECT COUNT(*) FROM dbo.gold_df_dim_date) dates,
          (SELECT COUNT(*) FROM dbo.gold_df_dim_station) stations"
```

Serving checks:

```bash
# rebuild/redeploy the Direct Lake model, refresh it and run DAX smoke tests
python tools/deploy_semantic_model.py --env sandbox --update
```

---

## 11. Tooling and artefacts added

### 11.1 Fabric items (new)

| Item | Type | ID |
|---|---|---|
| `lh_bronze` | Lakehouse | `0cde2eb7-937b-49c6-a4ed-b95bd66dc49e` |
| `lh_silver` | Lakehouse | `b6d8fe8b-bad2-4ac5-a605-f0b13893df7f` |
| `lh_gold` | Lakehouse | `df9a08e5-b370-4c2a-b608-6d0f326003ef` |
| `nb_01_bronze_ingest` | Notebook | `7b53bc2e-e4f9-49f4-a0ec-18f33ad7a74f` |
| `nb_02_silver_conform` | Notebook | `aee945bd-02a7-49aa-adaa-f57799106b05` |
| `nb_03_gold_features` | Notebook | `31649865-f498-427c-91c7-fd77ed5eeb8d` |
| `nb_04_gold_risk_alerts` | Notebook | `ed822f3c-c442-47f6-82f4-d7313f7f6e2a` |
| `nb_05_df_gold_dimensions` | Notebook | `effcd5bf-f960-4523-9028-661e0f6401fe` |
| `sm_df_early_warning` | Semantic model | `0f5395f6-2365-48a2-ae9d-c6c2e814bc9f` |
| `rpt_df_early_warning` | Report | `a76b8d4b-3243-4d5b-b13b-da01c3d298ed` |
| `nb_06_df_dq_gate` | Notebook | `a6ffe2c4-5de0-4bbf-9f5e-2d663fb96a0a` |
| `pl_df_daily_build` | Data pipeline | `5612dc63-d473-4457-8b90-6ca93aa62412` |

### 11.2 Repository files

| File | Purpose |
|---|---|
| `fabric/notebooks/nb_01_bronze_ingest.ipynb` | Versioned bronze notebook source |
| `fabric/notebooks/nb_02_silver_conform.ipynb` | Versioned silver notebook source |
| `fabric/notebooks/nb_03_gold_features.ipynb` | Versioned gold feature/baseline notebook |
| `fabric/notebooks/nb_04_gold_risk_alerts.ipynb` | Versioned gold risk/alert notebook |
| `fabric/notebooks/nb_05_df_gold_dimensions.ipynb` | Versioned date/station dimension notebook |
| `fabric/notebooks/nb_06_df_dq_gate.ipynb` | Warn-only data-quality gate notebook |
| `fabric/pipeline/pipeline-content.json` | Generated pipeline definition (six notebooks, retries, failure branch) |
| `tools/deploy_pipeline.py` | Builds/publishes the pipeline, schedule and optional run |
| `fabric/semantic_model/model_spec.py` | Physical column schema for the serving model |
| `fabric/semantic_model/model_logic.py` | Selected tables, measures and relationships |
| `fabric/semantic_model/definition/` | Generated TMDL (committed for review) |
| `fabric/report/report_spec.py` | PBIR page/visual specification for the report |
| `fabric/report/definition/` | Generated PBIR (committed for review) |
| `tools/fabric_items.py` | Shared Fabric/Power BI REST client (LRO, refresh, DAX) |
| `tools/deploy_semantic_model.py` | Builds TMDL, publishes, refreshes and smoke-tests the model |
| `tools/deploy_report.py` | Builds PBIR, publishes and verifies the report |
| `tools/env_config.py` | Loads one `.env.<profile>` per run |
| `tools/fabric_query.py` | Read-only warehouse/lakehouse query tool; `--env`, `--show-env` |
| `tools/generate_test_data.py` | Seed/synthetic data generator |
| `tools/provision_sandbox.py` | Creates lakehouses and uploads seed data (create-only) |
| `tools/deploy_notebook.py` | Publishes a notebook to Fabric (create-only; `--update` required to modify) |
| `tools/run_notebook.py` | Triggers a notebook run and polls the job to completion |
| `docs/test-environment-setup.md` | New-tenant setup, profiles, tenant/capacity discovery |
| `docs/fabric-build-log-maf-sandbox.md` | This document |
| `docs/fabric-semantic-model-and-report-plan.md` | Serving-layer plan, `df` convention, Direct Lake findings, vertical slices |

### 11.3 Local-only (git-ignored)

| Path | Contents |
|---|---|
| `.env.sandbox` | Sandbox profile: tenant, workspace, capacity, SQL endpoint. No secrets. |
| `test_data/sandbox/` | Seed CSVs, manifests, verification downloads |
| `logs/fabric_queries.log` | Query audit log |

---

## 12. Reproduce from scratch

```bash
# 1. Sign in to the Wragby tenant
az login --tenant wragbysolutions.com

# 2. Confirm the profile
python tools/fabric_query.py --env sandbox --show-env

# 3. Generate the seed data
python tools/generate_test_data.py --env sandbox --days 90 --anonymise --force

# 4. Create lakehouses and upload the seed data
python tools/provision_sandbox.py --env sandbox --upload

# 5. Publish the bronze notebook (create-only)
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/nb_01_bronze_ingest.ipynb

# 6. Publish the silver notebook (create-only)
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/nb_02_silver_conform.ipynb

# 7. Publish the gold feature notebook (create-only)
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/nb_03_gold_features.ipynb

# 8. Publish the gold risk/alert notebook (create-only)
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/nb_04_gold_risk_alerts.ipynb

# 9. Run the chain and wait
python tools/run_notebook.py --env sandbox --name nb_03_gold_features
python tools/run_notebook.py --env sandbox --name nb_04_gold_risk_alerts
```

Run a notebook through the Fabric UI, or via the Job Scheduler API:

```
POST /v1/workspaces/{workspaceId}/items/{itemId}/jobs/instances?jobType=RunNotebook
```

Poll the returned `Location` until `status` is `Completed`.

---

## 13. Known issues and caveats

1. **F2 is the smallest SKU.** It is sufficient for this test build, but Spark
   runs are slow (bronze ~1 min, silver ~2m 18s) and can be throttled. Schedule
   off-peak and keep the test window short.
2. **SQL endpoint metadata lag.** New tables may take a few minutes to appear in
   `INFORMATION_SCHEMA`. It has caught up for this build; expect it after future
   writes.
3. **Observed station-days only.** `silver_station_day` has 399 rows, not 450.
   Gold will add the complete grid with `is_observed`.
4. **Local disk pressure.** The workstation `C:` drive was at 100% during the
   build; only ~1 GB was free after clearing temp caches. Spark/Fabric work runs
   in the cloud, but local tooling can fail (Windows `paging file is too small`).
   Free 10–20 GB before heavy local work.
5. **Gold is rule-based v1.** The Direct Lake semantic model exists, but there
   is no trained onset model, no Power BI report, no schedule and no Data
   Activator rule yet.
6. **Baseline window is short.** The seed has 90 days, so baselines use the
   first 28 and the weekday profile is shrunk (75% weekday / 25% overall).
   Re-estimate with a longer history before production use.
7. **Seed signals are partly static.** THP and bean are near-constant per
   station in the seed, so their deviations look like step changes. Robust z is
   capped at ±25 to keep them from dominating. This is a seed artefact, not
   production behaviour.
8. **`gold_alert` is a deterministic backfill.** A rerun rebuilds it. In
   production, merge by `alert_key` so delivery/acknowledgement state survives.
   `gold_alert_outcome` is preserved.
9. **Value at risk is current excess.** `exp_usd` is the expected excess over the
   station’s normal loss rate, not a forecast of future production.
10. **Existing work untouched.** `maf_lake`, the staging items, the Data Agent
    and the two existing notebooks were not modified. `deferement_newcross` is
    empty and was ignored.
11. **Seed data is synthetic/anonymised.** It is derived from the real extract
    but must not be treated as production truth.
12. **Direct Lake on this non-schema lakehouse must omit `schemaName`.** A
    partition with `schemaName: dbo` imports but fails refresh with "table does
    not exist or access was denied". The working TMDL omits `schemaName` and
    points `DatabaseQuery` at the ID-based lakehouse root (no `/Tables` suffix).
    See `docs/fabric-semantic-model-and-report-plan.md` §3.
13. **Group/filter dates through `gold_df_dim_date`.** In this Direct Lake
    model, grouping or filtering the fact table's own `date` column while a
    dimension filter is present can drop the dimension filter. This affected
    the station-detail table and the “latest” measures. Use the date dimension
    in report axes, table date columns and date filters.
14. **PBIR conditional formatting needs a metadata selector.** For matrix or
    table `backColor` rules, the `objects.values` selector must include
    `metadata` equal to the value queryRef. A wildcard-only selector is
    silently ignored.
15. **Empty Direct Lake tables return blank from `COUNTROWS`.** Wrap count
    measures in `COALESCE(..., 0)` where the empty state should read as zero.
    This affects `gold_alert_outcome` until the outcome job runs.
16. **The daily pipeline takes ~15 minutes on F2.** Do not overlap manual runs
    with the 06:00 UTC schedule. The failure webhook is empty by default; set
    `alert_webhook_url` to receive a push alert. The DQ log table can take a few
    minutes to appear in the SQL endpoint after its first write.

---

## 14. Next steps

1. **Semantic model + Power BI report** over `lh_gold` (Direct Lake): risk
   ranking, station drill-down, deviation heatmap, alert log and outcome view.
   **Semantic model done:** `sm_df_early_warning` is published and refreshed.
   **Report done:** `rpt_df_early_warning` now has all five pages — executive
   overview, station detail, deviation heatmap, alert log and outcomes — built
   and export-verified.
2. **Orchestration done:** `pl_df_daily_build` runs `nb_01 → nb_07`
   sequentially with retries, a failure branch and a daily 06:00 UTC schedule.
   The serving-layer design, `df` naming convention, Direct Lake findings and
   vertical-slice sequence are in `docs/fabric-semantic-model-and-report-plan.md`.
3. **Outcome / lead-time job done:** `nb_07_df_alert_outcomes` fills
   `gold_alert_outcome` (14 confirmed / 3 false, median 2.0 days) and is in the
   daily pipeline.
4. **Parity check done:** `tools/parity_check.py` compares 15 silver/gold
   tables with a clean-room local reference. Verdict **PASS**; the only
   differences are documented floating-point tie effects. Report:
   `docs/fabric-parity-check-slice8.md`.
5. **Data-quality gate done:** `nb_06_df_dq_gate` is wired into the daily
   pipeline; it writes `gold_pipeline_dq_log` and only warns.
6. **Layer 2 onset model tested — rejected.** `tools/onset_model.py` compares a
   logistic-regression challenger with rules v1 on a 3-fold chronological
   backtest. The model improves ranking (material PR-AUC 0.706 vs 0.603) but
   does not add lead time at equal false alarms (model 9/4, 2.0 days vs rules
   10/3, 3.0 days). Rules v1 is retained. Report:
   `docs/slice9-onset-model-report.md`.
7. **Fix ISS-018:** `silver_deferment_episode.episode_id` is not unique
   because it omits `cause_group`; add it or use a surrogate key before using
   the id as a join key.
8. **Production hardening / longer history** is now the main follow-on:
   real data, more than 28 baseline days, tuned alert budget, formal prototype
   parity, RLS/app publication, Data Activator and monitoring.

---

## 15. Security and source control

- No secrets are stored in the repository. `.env*` is git-ignored except
  `.env.example`; `.env.sandbox` stays local.
- `test_data/` is git-ignored because it may contain client-derived values.
- The query tool is read-only by design and refuses anything other than
  `SELECT` / `WITH`.
- `.env.sandbox` points at the Wragby tenant; the existing NewCross profile
  (`.env`) was not changed.
- Notebook deployment is create-only by default; modifying an existing notebook
  requires the explicit `--update` flag.

---

## 16. Change history

| Date | Change |
|---|---|
| 2026-10-21 | Sandbox created: 3 lakehouses, seed data uploaded, bronze and silver notebooks built and run, silver verified. |
| 2026-10-21 | Gold features and rules-v1 risk/alert notebooks built, run and verified; 17 alerts (9 Red / 8 Amber) and an empty outcome skeleton written to `lh_gold`. |
| 2026-10-21 | Serving-layer plan written (`fabric-semantic-model-and-report-plan.md`); `df` naming convention adopted; Direct Lake probe confirmed that model table names must match the physical Delta table names. |
| 2026-10-21 | `nb_05_df_gold_dimensions` built and run: `gold_df_dim_date` (90 rows) and `gold_df_dim_station` (5 rows). `sm_df_early_warning` published, refreshed and verified with DAX smoke tests (all match SQL ground truth). Slice 1 complete. |
| 2026-10-21 | `rpt_df_early_warning` created as PBIR and bound to `sm_df_early_warning`; executive overview page (5 cards, station ranking, tier mix, latest alerts, alert trend) published and PDF-export verified. Slice 2 complete. |
| 2026-10-21 | Station detail page added: station slicer (default B), latest-risk cards, risk/oil lines, normal-range and recent-reasons tables. Fixed latest measures losing the station filter and fact-date grouping dropping dimension filters. Slice 3 complete. |
| 2026-10-21 | Deviation heatmap page added: metric × month matrix of `Bad Z (scored)` with a green/white/red conditional-formatting gradient, dropdown station slicer and legend. Slice 4 complete. |
| 2026-10-21 | Alert log page added (tier/station/month slicers, 4 cards, 17-row table). Outcomes page added with honest empty state (0 / 0 / “No outcomes yet” / 17 awaiting). Fixed empty-table `COUNTROWS` blanks with `COALESCE`. Slice 5 complete; report has 5 pages. |
| 2026-10-22 | Added `nb_06_df_dq_gate` (warn-only, writes `gold_pipeline_dq_log`). Built `pl_df_daily_build` with sequential notebook execution, retry 2×/120s, failure branch (`DF_DAILY_BUILD_FAILED`) and optional webhook. End-to-end run Completed (~15 min on F2); failure path tested; daily 06:00 UTC schedule enabled. Slice 6 complete. |
| 2026-10-22 | Added `nb_07_df_alert_outcomes`; `gold_alert_outcome` now has 17 rows (14 confirmed, 3 false), median lead 2.0 days, precision 82.4%. Outcomes page now live. Slice 7 complete. |
| 2026-10-22 | Slice 8 parity check passed: 15 silver/gold tables match a clean-room local reference (row counts, keys, values, tiers, alerts, outcomes). Two benign floating-point tie effects documented; `episode_id` uniqueness defect raised as ISS-018. |
| 2026-10-22 | Slice 9 Layer 2 v1 tested and rejected: logistic regression improved ranking (material PR-AUC 0.706 vs 0.603) but did not add lead time at equal false alarms. Rules v1 retained. |
