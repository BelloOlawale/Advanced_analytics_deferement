# Technology Stack & Implementation on Microsoft Fabric

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Purpose: the **full technology stack** needed, how each piece maps to Microsoft Fabric, how the build is implemented end to end, **how the model is trained**, whether we must work directly in Fabric, and **where the output lives**.
> Status: design · Version 0.1 · 2026-10-12
> Companion: `alert-log-and-feedback-loop.md`, `automation-and-human-in-the-loop.md`, `early-warning-architecture.md`, `how-fabric-delivers-results.md`.

---

## 1. The short answers up front

- **Do we have to work directly in Fabric?**
  - **To build and prototype:** no. Development can happen locally (Python, notebooks, version control) and be synced into Fabric.
  - **To operate in production:** yes. The pipelines, notebooks, training and scoring run **inside Fabric** so the data never leaves the client's tenant and everything shares one governance model.
  - **For the end users:** never. They see a Power BI report and Teams/email alerts. They do not open Fabric.

- **Where does the output live?**
  - In **OneLake**, as **Delta tables in a gold lakehouse** inside the Fabric workspace (the risk table, the deviation table, the daily position table, the alert log and outcomes, and the reference dimensions).
  - Read directly by a **Direct Lake semantic model**, surfaced through **Power BI**, and pushed through **Data Activator** as alerts.

- **Where does training happen?**
  - In a **Fabric Data Science notebook**, using **MLflow** (built into Fabric) to track runs and register model versions. The registered model is then used by a **batch scoring notebook** that runs on a schedule and writes the daily risk table.

- **What does it cost / run on?**
  - One **Fabric capacity (F16 in the proposal)** powers storage, Spark, ML and BI together. Scheduling is off-peak and reads prefer OneLake over engine queries.

---

## 2. The stack at a glance

One sentence: **Microsoft Fabric is the entire factory** — ingestion, storage, transformation, machine learning, serving and alerting all live on one platform, over one copy of the data, under one security model.

| Concern | What we use | Fabric item / workload |
|---|---|---|
| Source systems | Field production DB, deferment log, reference tables | external (warehouse in the tenant) |
| Ingestion | Scheduled copy / shortcuts, read-only | **OneLake shortcuts** + **Data Factory** pipelines |
| Raw storage | Faithful copy of what arrived | **Lakehouse** `lh_bronze` (Delta in OneLake) |
| Cleaning & conforming | Standardise, de-duplicate, taxonomy, episodes | **Spark notebooks** (Data Engineering) → `lh_silver` |
| Features & baselines | Entity-day clues, per-entity normal, deviations | **Spark/SQL notebooks** → `lh_gold` |
| Model training | Gradient-boosted trees + survival companion | **Fabric Data Science** notebook + **MLflow** |
| Model registry | Versioned models, metrics, promotion gate | **MLflow** (workspace model registry) |
| Batch scoring | Daily risk per station/well | **Spark/Python notebook**, scheduled |
| Orchestration | Run order, schedule, retries, failure alerts | **Data Factory pipelines** (or Airflow job) |
| Serving model | Governed business logic, measures, drill-down | **Power BI semantic model** over gold (Direct Lake) |
| Reports | Persona pages + app | **Power BI** report + **Power BI app** |
| Alerts | Rule + routing + delivery | **Data Activator** (Reflex) → Teams / email |
| Feedback capture | One-click acknowledgement + write-back | **Power Automate** / Teams cards / **Power Apps** |
| Real-time (later) | Hourly historian signals | **Eventstream** + **Eventhouse** (Real-Time Intelligence) |
| Governance | Access, labels, lineage | Workspaces, **RBAC**, **Purview**, sensitivity labels |
| Secrets | Connections and keys | **Key Vault** / Fabric connections |
| CI/CD | Promote definitions across environments | **Git integration** + **Deployment pipelines** |
| Monitoring | Freshness, volume, drift, DQ | Monitoring hub + notebook checks + Power BI |

**Alternative stacks we are deliberately not choosing.** The same solution could be assembled from Azure Data Factory + ADLS + Databricks + Azure ML + Power BI. It would work, but it would mean several platforms, several security models and several bills. Because the client **already owns Fabric**, the native build removes the integration overhead and keeps the data in one governed place. (Azure ML remains a valid fallback only if the ML team standardises on it; it is not preferred here.)

---

## 3. The end-to-end build, mapped to Fabric items

```
  SOURCE (tenant)                 ONE LAKE  (OneLake, Delta)
  ┌───────────────┐   shortcut    ┌──────────────────────────────────────────┐
  │ production DB │──────────────▶│  lh_bronze   raw + ingest audit          │
  │ deferment log │   / Data      │      │  notebooks: clean / taxonomy /     │
  │ reference     │   Factory     │      ▼            episodes               │
  └───────────────┘   copy        │  lh_silver   cleansed, conformed         │
                                  │      │  notebooks: features + baselines  │
                                  │      ▼                                    │
                                  │  lh_gold     entity-day features,         │
                                  │              deviations, risk, alerts     │
                                  └───────┬───────────────────────┬──────────┘
                                          │                       │
                            Direct Lake   │                       │  Data Activator
                                          ▼                       ▼
                                 Power BI semantic model     Teams / email alert
                                          │                       │
                                          ▼                       ▼
                                   Power BI report/app      one-click outcome
                                                           → write-back to lh_gold
```

**Stage by stage**

1. **Ingestion** — a **Data Factory** pipeline (or a shortcut, which makes the source data appear in OneLake without copying) brings the source tables into `lh_bronze`, stamping each batch with an ingestion timestamp. Read-only throughout.
2. **Cleaning / conforming** — a **Spark notebook** standardises dates, de-duplicates the station-level target, groups causes, reconstructs episodes, and writes `lh_silver`. Missing readings are preserved as missing.
3. **Features & baselines** — a notebook builds the **entity-day feature table** (one row per station-day, and per well-day) and each entity's "own normal", writing `lh_gold`.
4. **Labels** — the notebook (or a shared step) also writes the training **answer key**: for each entity-day, whether an onset started within the next 1/3/7 days.
5. **Training** — the Data Science notebook reads the feature+label table, trains the model, logs to MLflow, registers a version (Section 4).
6. **Scoring** — a scheduled notebook loads the latest registered model, scores the newest feature rows, applies the value ranking and tiering, and writes the **daily risk table** in `lh_gold`.
7. **Serving** — a **Direct Lake semantic model** points at the gold tables; the **Power BI report** reads it; the **app** is published to the client workspace.
8. **Alerting** — **Data Activator** watches the risk output, fires on threshold crossings, and routes messages to owners.
9. **Feedback** — recipients act on the alert in Teams; an automation flow writes the outcome back to the alert log (**see the companion alert document**).
10. **Learning** — a monthly job re-tunes the thresholds (config tables) and retrains the model, then re-validates before promotion.

**Orchestration.** A single **Data Factory pipeline** runs the whole chain in order — bronze → silver → gold → score → refresh → outcome job — with dependencies, timeouts, retries and a failure alert. One look at the pipeline run history tells you whether the overnight job succeeded.

---

## 4. How training works, specifically in Fabric

Training is a repeatable, scheduled activity, not a one-off.

**The inputs.** A single **entity-day feature table** in `lh_gold` containing every clue, plus the **label** column (did an onset start within H days). One row = one entity on one day.

**The training notebook (Fabric Data Science):**

1. **Load** the feature + label table from the gold lakehouse.
2. **Split by time** — older data to learn, middle to fine-tune, newest held back as the final exam. Never shuffled.
3. **Train** the gradient-boosted-tree model (and the survival companion). Rare event days are weighted so the model does not ignore them.
4. **Log to MLflow** — parameters, metrics, the trained artifact, and the data window are recorded as a run. This gives full reproducibility.
5. **Evaluate on the held-back period** — lead time, precision/recall, false alarms — and compare against the current incumbent and against the simple rule.
6. **Register the model** as a new version in the workspace MLflow registry, tagged with its metrics and data window.
7. **Promote only if it wins** — if it does not beat the incumbent on lead time at the same alert budget, it is not promoted.

**Schedule.** Training runs **monthly** (or when drift is detected). Scoring runs **daily**. Baselines refresh more often than the full model.

**How scoring uses the model.** A separate **scoring notebook** loads the registered model version by name/tag, builds the same clues for the newest day, predicts a probability for every station and well, applies the survival estimate for lead time and the value ranking for money, and writes the daily risk table. Because the model is loaded from the registry, promoting a new version changes behaviour without editing the scoring code — and every output row records which `model_version` produced it.

**Why Fabric Data Science fits.** MLflow is built in, so there is no separate experiment-tracking service to run. The training and scoring notebooks sit in the same workspace, read the same OneLake tables and use the same capacity, so there is no data movement between platforms and no second security model.

> If the ML team preferred, the model could be trained in **Azure ML** instead and the predictions consumed in Fabric. We do not recommend it here: it buys nothing the client does not already have, and it spreads the solution across two platforms.

---

## 5. Do we need to work directly in Fabric?

Three different roles, three different answers.

| Role | Works directly in Fabric? | How |
|---|---|---|
| **Data engineer / data scientist (build)** | Optionally | Develop locally in Python/notebooks under version control, then **sync into Fabric via Git integration** — or author notebooks directly in the Fabric workspace. Either way the item ends up as a Fabric artifact. |
| **Operations (run the solution)** | Yes | The pipelines, notebooks and schedules live in Fabric. Post-go-live, managed services checks that the overnight run succeeded. |
| **Business users (consume)** | No | They open a **Power BI report/app** and receive **Teams/email alerts**. They never see Fabric. |

**Development options for the build team, concretely:**

- **Local-friendly path (used during prototyping now):** write Python/Spark logic locally, test against extracts, keep it in Git, and promote into Fabric when ready. This is how the current prototype works (a local read-only connector plus a local analytics engine).
- **Fabric-native path (target for production):** author notebooks and pipelines inside the Fabric workspace; use **Git integration** so the workspace items are backed by the repository and can be code-reviewed.

Both paths converge on the same production state: the logic runs as Fabric items, on a Fabric schedule, against OneLake data.

**What the client must provide for this to work:**

1. A **Fabric capacity** (the proposal sizes this at **F16**) and a workspace (plus separate dev/test/prod workspaces for a clean promotion path).
2. A **read-only identity** (service principal or least-privilege account) for ongoing source access, replacing the current admin account.
3. **Source access** to the warehouse tables and, later, historian/CMMS feeds.
4. A **gateway** only if a source sits outside the Fabric network.
5. **Teams** for alert delivery and **Entra groups** for report access and row-level security.
6. **Workspace admin** rights for the delivery team, and **Key Vault** (or Fabric connections) for secrets.
7. Confirmation of **scope** (which assets/stations are in scope) for security design.

---

## 6. Where the output lives (in detail)

Everything the business consumes originates from **gold Delta tables in OneLake**. There is no separate output database.

```
Fabric tenant / workspace
├── lh_bronze      (raw snapshots + ingestion audit)
├── lh_silver      (cleansed, conformed, taxonomy, episodes)
├── lh_gold        ◀── THE OUTPUT LIVES HERE (Delta tables)
│     ├── risk_daily            (one row per station-day; the main product)
│     ├── deviation_daily       (station × signal × day; the evidence)
│     ├── station_day           (the production scoreboard)
│     ├── alert                 (every alert raised)
│     ├── alert_outcome         (accept/action/verdict per alert)
│     └── dim_*                 (date, station, well, cause, signal, tier)
├── Semantic model   (Direct Lake over lh_gold)  ← measures + relationships
├── Power BI report  (ranking, drill-down, well-vs-baseline, heatmap, alert log, exec)
└── Power BI app     (published to users, with RLS by asset)
```

- **Consumption:** the semantic model reads the gold tables directly (Direct Lake), so reports are fast and always current without a copy step. If Direct Lake is unavailable for any reason, the model falls back to Import with a scheduled refresh.
- **Alerts:** Data Activator reads the same risk data; there is no second pipeline for alerting.
- **Feedback:** the outcome write-back lands in the same gold layer, so the monitoring reports sit beside the risk reports.
- **Governance:** sensitivity labels and row-level security apply to these gold tables and the model, so each user sees only their asset.

---

## 7. Environments, deployment and CI/CD

- **Separate workspaces per environment:** **Dev → Test → Prod**, each with its own lakehouses, so experimentation never touches production data.
- **Git integration:** workspace items (notebooks, pipelines, semantic models) are backed by the repository; changes are reviewed like code.
- **Deployment pipelines:** promote the same artifacts from Dev to Test to Prod; **connections and thresholds are parameterised per environment** (Config-as-data), so no code edit is needed to point at a different source or capacity.
- **Testing gates:** a **parity check** confirms the Fabric output matches the validated prototype for the same window before go-live; a data-quality gate runs every day and **warns rather than blocks** (a bad cause code must never stop the daily run).
- **Rollback:** because every model is versioned and every output row records its `model_version`, a bad promotion can be reverted by pointing scoring back at the previous version.

---

## 8. Security, governance and cost

- **Read-only on sources.** The analytics never writes back to operational systems.
- **Least privilege:** separate roles for ingestion, modelling and consumption; a read-only identity for source access; no secrets in code (Key Vault / Fabric connections).
- **Data residency:** the client's data stays in the client's tenant; nothing is exfiltrated.
- **Lineage and labelling:** Purview lineage and sensitivity labels on the gold outputs.
- **Row-level security:** by asset, so a multi-asset deployment shows each user only their own stations.
- **Auditability:** every source query is logged; every alert records its model and ruleset version; a model card accompanies each version.
- **Capacity and cost:** one F16 capacity powers storage, Spark, ML and BI. Costs are controlled by scheduling off-peak, preferring OneLake reads to engine scans, and using Direct Lake to avoid data copies.

---

## 9. Roadmap: from prototype to platform

| Phase | Where it runs | What exists |
|---|---|---|
| **Phase 0 (now)** | Local | Read-only extraction to files; feature + deviation logic prototyped locally; the **measured lead-time number** |
| **Phase 1** | Fabric | Bronze→silver→gold pipeline in Fabric; the deviation engine and value ranking running on a schedule; a Power BI station view |
| **Phase 2** | Fabric | Data Activator alerts + the feedback loop |
| **Phase 3** | Fabric | The learned onset + survival model, trained via MLflow, plus monthly retraining |
| **Phase 4** | Fabric | Real-time historian signals through Eventstream/Eventhouse for hourly risk |

Each phase is a thin end-to-end increment: data → features → score → a surface a person can use.

---

## 10. Glossary of the platform terms

| Term | Plain meaning |
|---|---|
| **OneLake** | The single storage layer under all of Fabric |
| **Lakehouse** | A store of Delta tables (bronze/silver/gold) in OneLake |
| **Delta table** | A table that can be updated and read efficiently; the default format |
| **Data Factory** | The scheduling and data-movement engine |
| **Notebook** | A runnable document of code (Spark/Python) for transforming data or training models |
| **Data Science / MLflow** | The model-training workspace and the experiment/model registry |
| **Semantic model** | The governed layer of business logic and measures that reports read |
| **Direct Lake** | A report mode that reads OneLake Delta tables directly, with no copy |
| **Data Activator** | Fabric's alerting engine: watch data, fire a message on a condition |
| **Eventstream / Eventhouse** | The real-time path for streaming signals (later phase) |
| **Purview** | The governance service for lineage and sensitivity labelling |
| **Deployment pipeline** | The tool that promotes the same build from dev to test to prod |
| **Capacity (F16)** | The compute/storage entitlement that powers the whole workspace |

---

*Design note, 2026-10-12. Items, schedules and thresholds are proposals to be confirmed during Discovery and against the client's Fabric capacity and governance standards.*
