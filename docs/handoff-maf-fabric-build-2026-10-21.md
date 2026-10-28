# Handoff — Fabric sandbox build (`maf`)

**Date:** 2026-10-21
**Repo:** `C:/Users/OlawaleBello/workspace/Advanced_analytics_deferement`
**Branch:** `dev`
**Next focus:** production hardening and longer real history. Slice 9 Layer 2 v1 was tested and rejected; rules v1 remains the champion. Fix ISS-018 before using episode ids as keys.

---

## 1. Where things stand

The **bronze, silver and gold layers are built, run and verified** in the new Fabric tenant. Gold now contains baselines, station-day features, deviations, a rules-v1 risk score, 17 alerts and an empty outcome skeleton. There is **no semantic model, report or schedule yet**.

Do not re-derive the details — they are already written down:

| Topic | Artifact |
|---|---|
| Full build log: environment IDs, tables, row counts, runs, verification, known issues, next steps | `docs/fabric-build-log-maf-sandbox.md` |
| New-tenant setup, profiles, tenant/capacity discovery, Member-role notes | `docs/test-environment-setup.md` |
| Architecture, medallion design, Fabric workload mapping | `docs/technology-stack-and-fabric-implementation.md` |
| Requirements and KPIs | `docs/prd-deferment-early-warning.md` |
| Fabric productionisation backlog item | `Issues/ISS-013-vs9-fabric-productionisation.md` |
| Model design (baselines, deviations, onset, value ranking) | `docs/early-warning-model-design.md` |
| Serving-layer plan, `df` naming, Direct Lake findings, slices | `docs/fabric-semantic-model-and-report-plan.md` |
| Data-quality findings and constraints | `docs/data-quality-findings.md` |

**Short version:** `lh_bronze` has 11 Delta tables; `lh_silver` has 12; `lh_gold` has 8. Bronze, silver, gold features and gold risk/alert notebooks all completed and their outputs were verified. See the build log for exact run IDs and metrics.

---

## 2. Environment

- Workspace **`maf`** in the Wragby tenant.
- Capacity **`mafcapacity`**, **F2**, **North Europe**.
- Tenant ID, workspace ID, capacity ID, SQL endpoint, lakehouse IDs and notebook run IDs are in `docs/fabric-build-log-maf-sandbox.md` §2 and §11.1.
- Local profile: **`.env.sandbox`** (git-ignored). It contains no secrets.
- Authentication is via the existing Azure CLI login. The account email is intentionally not repeated here (PII).
- If re-authentication is needed:

```bash
az login --tenant wragbysolutions.com
```

The tenant GUID is not required for interactive login; the signed-in tenant supplies it.

### Existing workspace items — do not modify

`maf_lake`, `StagingLakehouseForDataflows_20260608140408`, `StagingWarehouseForDataflows_20260608140422`, `maf-data-agent`, `push_table_into_warehouse`, `deferement_newcross` (confirmed empty).

The new build uses only the three new lakehouses and four new notebooks. Deployment tooling is **create-only** by default; do not pass `--update` or use existing names.

---

## 3. New build items (names only)

- Lakehouses: `lh_bronze`, `lh_silver`, `lh_gold`
- Notebooks: `nb_01_bronze_ingest`, `nb_02_silver_conform`, `nb_03_gold_features`, `nb_04_gold_risk_alerts`

IDs, run IDs and endpoint details: build log §11.1 and §8.1/§9.1.

---

## 4. Repo state

Added/changed in the working tree (nothing committed yet):

```text
docs/fabric-build-log-maf-sandbox.md
docs/test-environment-setup.md
docs/README.md                      (index + layout updated)
docs/handoff-maf-fabric-build-2026-10-21.md
fabric/notebooks/nb_01_bronze_ingest.ipynb
fabric/notebooks/nb_02_silver_conform.ipynb
fabric/notebooks/nb_03_gold_features.ipynb
fabric/notebooks/nb_04_gold_risk_alerts.ipynb
tools/env_config.py
tools/fabric_query.py                (--env, --show-env)
tools/generate_test_data.py
tools/provision_sandbox.py
tools/deploy_notebook.py
tools/run_notebook.py                (trigger + poll a notebook run)
.env.example                         (profile documentation)
.gitignore                           (.env.*, test_data/, .azure-fabric/)
data/README.md
```

Local-only / git-ignored:

```text
.env.sandbox
test_data/sandbox/
logs/fabric_queries.log
```

---

## 5. Next steps

1. **Power BI report — done.** `rpt_df_early_warning` has all five pages and is PDF-export verified. Model/report ids: `docs/fabric-semantic-model-and-report-plan.md` §6–§10.
2. **Orchestration — done.** `pl_df_daily_build` runs `nb_01 → nb_07` daily at 06:00 UTC with retries, a failure branch and a warn-only DQ gate.
3. **Outcome / lead-time job — done.** `nb_07_df_alert_outcomes` fills `gold_alert_outcome`; 14 confirmed / 3 false, median lead 2.0 days, precision 82.4%.
4. **Parity check — done.** `tools/parity_check.py`; verdict PASS. See `docs/fabric-parity-check-slice8.md`.
5. **Data-quality gate — done** (warn, do not block) in the pipeline.
6. **Layer 2 onset model — tested and rejected.** Logistic regression improved ranking but did not add lead time at equal false alarms. Rules v1 retained. See `docs/slice9-onset-model-report.md`.
7. **Fix ISS-018:** `silver_deferment_episode.episode_id` is not unique (omits `cause_group`) before using it as a join key.
8. **Production hardening:** real data, longer history, tuned alert budget, formal prototype parity, RLS/app publication, Data Activator and monitoring.

Follow `docs/fabric-build-log-maf-sandbox.md` §14 for the agreed sequence.

---

## 6. How to resume

```bash
cd C:/Users/OlawaleBello/workspace/Advanced_analytics_deferement

# confirm the active profile and target
python tools/fabric_query.py --env sandbox --show-env
python tools/fabric_query.py --env sandbox --test

# deploy a notebook (create-only)
python tools/deploy_notebook.py --env sandbox \
  --file fabric/notebooks/<notebook>.ipynb
```

Run a notebook through the Fabric UI, the Job Scheduler API, or the local helper:

```bash
python tools/run_notebook.py --env sandbox --name nb_04_gold_risk_alerts
```

Verification examples (full commands in build log §10.1):

```bash
FABRIC_SQL_DATABASE=lh_silver \
  python tools/fabric_query.py --env sandbox \
  "SELECT metric, value FROM dbo.silver_data_quality ORDER BY metric"

FABRIC_SQL_DATABASE=lh_gold \
  python tools/fabric_query.py --env sandbox \
  "SELECT risk_tier, COUNT(*) FROM dbo.gold_risk_daily WHERE is_observed=1 GROUP BY risk_tier"
```

---

## 7. Traps and notes

- **Do not modify existing `maf` items.** Create new items only. `provision_sandbox.py` and `deploy_notebook.py` are create-only by default.
- **F2 is small.** Notebook runs take roughly 1–2 minutes and can be throttled. Keep the test window short and run off-peak.
- **SQL endpoint metadata can lag** after new writes. Spark and Direct Lake are unaffected. Wait a few minutes or refresh the lakehouse before concluding a table is missing.
- **`silver_station_day` is observed-only** (399 rows, not 450). This is deliberate. Gold builds the complete station-date grid and carries an explicit `is_observed` flag; missing is not zero.
- **Gold baselines use the first 28 days only** (`baseline_phase = estimation`). Rows in that window are `Unscored`; only later rows can alert. Do not change this without re-checking leakage.
- **Robust z is capped at ±25** and per-metric scales have absolute floors. The seed's near-static THP/bean would otherwise produce meaningless z≈1000. Use `max_abs_z` in the DQ table with that in mind.
- **`gold_alert` is rebuilt on every run.** It is a deterministic backfill. In production, merge by `alert_key` so delivery/acknowledgement state survives. `gold_alert_outcome` is preserved.
- **`exp_usd` is current excess over normal**, not a forecast of future production. The early-warning value is the signal lead, not a promise of avoided barrels.
- **Alert rate in the seed is ~0.38 per station per week** (17 alerts over 62 scored days). That is a starting point for the alert budget, not a tuned production threshold.
- **`gold_alert_outcome` is empty by design.** The outcome/lead-time job is the next build item.
- **Local disk is nearly full** (~300 MB free on `C:`). Free 10–20 GB before heavy local work; Windows previously failed with `paging file is too small`.
- **Do not commit** `.env*`, `test_data/`, `.azure-fabric/`, or logs.
- **PII:** the build log’s account email has been redacted. Two older docs still contain a client admin email and should be redacted before external sharing: `docs/data-quality-findings.md` and `docs/fabric-build-end-to-end.md`.
- **The seed data is derived and anonymised.** Treat it as test data, not production truth.
- The existing `deferement_newcross` notebook is empty; ignore it.

---

## 8. Suggested skills

Invoke these if the next session needs them:

| Skill | When |
|---|---|
| **`tdd`** | When adding testable geospatial/Spark transformation logic or regression checks for gold outputs. |
| **`diagnosing-bugs`** | When a Fabric notebook run fails, row counts do not reconcile, or numbers look wrong. |
| **`azure-validate`** | Before promoting the build to test/prod or validating Fabric configuration, RBAC, and deployment readiness. |
| **`domain-modeling`** | To keep deferment terminology consistent (episode, onset, potential, lead time, tier) as gold and the semantic model are designed. |
| **`codebase-design`** | If refactoring notebook code into reusable modules/helpers. |
| **`find-skills`** | If a capability gap appears that an installable skill may cover. |

---

## 9. One-line continuation prompt

> Read `docs/fabric-build-log-maf-sandbox.md` and `docs/fabric-semantic-model-and-report-plan.md`. Slices 1–6 are complete: `sm_df_early_warning` and all five report pages are built and verified, and `pl_df_daily_build` orchestrates `nb_01 → nb_06` daily at 06:00 UTC with retries, a failure branch and a warn-only DQ gate. Next: build the outcome / lead-time job that fills `gold_alert_outcome`. Keep existing `maf` items untouched and do not overwrite `gold_alert_outcome`.
