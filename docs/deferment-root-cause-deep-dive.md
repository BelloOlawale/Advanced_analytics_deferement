# Deep Dive — Deferment Root-Cause & Production Loss Prediction

> Project: **Part 1, Project 1** of Wragby's Advanced Analytics & AI proposal to NewCross EP
> Asset: **OML 24** (Awoba, Awoba North West, Ekulama) · western Niger Delta · >130,000 bbl/day capacity · target 100,000 bopd
> Platform: **Microsoft Fabric** + enterprise data warehouse; source of truth = `lh_silver` lakehouse
> Status: proposal stage — scope below blends *confirmed proposal language* with a *proposed delivery blueprint* to be validated in discovery.

---

## 1. Why this project (business case)

Production deferment is the single most direct lever between NewCross EP's current output and its **100,000 bopd growth target**. Every deferred barrel is lost revenue, a missed target, and a governance/partner-reporting issue (NUIMS/JV). The proposal frames the project as:

> "Built directly on production and deferment-cause data confirmed available in the `lh_silver` lakehouse, this project identifies the two or three root causes responsible for the majority of production loss using root-cause Pareto analysis and extends into predictive flagging of emerging loss patterns before they escalate."

**Core thesis:** a small number of root causes typically drive the majority of deferred volume (classic Pareto / 80‑20). If Wragby can (a) *quantify* those causes and (b) *predict* emerging ones, NewCross can move from reactive firefighting to targeted, prioritised intervention — protecting barrels and recovering production faster.

**Business value levers:**
| Lever | Mechanism | Example metric |
|---|---|---|
| Recover deferred barrels | Prioritise interventions by barrels-at-risk | bbl/month recovered |
| Reduce downtime duration | Faster diagnosis & response | MTTR (mean time to restore) |
| Reduce downtime frequency | Predict/prevent failures | Failure rate / events per well-month |
| Protect target | Reduce variance to plan | Deferment % of potential |
| Revenue protection | Convert deferred bbl → $ | $ protected / month |
| Partner credibility | Defensible cause narrative | Cause attribution accuracy |
| Operational focus | Rank the top 2–3 causes | Pareto coverage |

**Proposal deliverables (confirmed):**
- Root-cause Pareto breakdown of deferment volume by cause, field, and flow station
- Trend and pattern detection for recurring loss drivers
- Early-warning flags for deferment risk based on historical patterns
- Field-by-field and flow-station-by-flow-station loss comparison

---

## 2. Domain primer — deferment vocabulary

Getting the language right is critical; inconsistencies here corrupt every downstream number.

- **Deferment / production loss:** the difference between *potential* (theoretical/allowable) production and *actual* production, attributable to a cause.
- **Potential / allowable / capability:** what the wells + facilities could produce if unconstrained (often from well models, test data, or capacity).
- **Deferred volume (bbl):** integral of lost rate over lost time. `Deferred = Σ (Potential rate − Actual rate) × duration`.
- **Unplanned downtime:** equipment failure, power outage, third-party/community, sabotage, weather, etc.
- **Planned downtime:** maintenance, well interventions, facility turnarounds (still deferment, but schedulable/avoidable via timing).
- **Constraint types:** subsurface (reservoir, sand, water cut, GOR), wellbore (ESP/gas-lift failure, scale, sand), facility (separator, compressor, pump, flare), utilities (power, gas), export (pipeline, terminal), logistics/people, third-party, regulatory/community.
- **Flow station / facility / field hierarchy:** OML → Field → Flow Station → Facility/Equipment → Well. Attribution must respect this hierarchy.
- **Gross vs net / entitlement:** for partner (NUIMS/JV) reporting, deferred gross volumes must convert to net entitlement.
- **Cause code / downtime code:** operator/maintenance taxonomy used to tag each event. **This taxonomy is the backbone of Pareto and the #1 data-quality risk.**
- **MTBF / MTTR / run-life:** reliability metrics for predictive features.
- **Deferment register / downtime log:** the event-level record (start, end, cause, equipment, well, volume).

> **Discovery question:** Is deferred volume logged directly (measured) or *derived* from potential-vs-actual? The entire methodology hinges on this answer.

---

## 3. Objectives & success metrics

**Primary objectives**
1. Establish a single, governed view of deferment by cause/field/flow station.
2. Identify the 2–3 root causes behind the majority of lost volume.
3. Predict/flag emerging loss patterns before escalation.
4. Enable field-by-field and flow-station benchmarking.

**KPIs / success measures (proposed):**
| KPI | Definition | Baseline | Target |
|---|---|---|---|
| Deferment % | Deferred / Potential × 100 | from assessment | ↓ trend |
| Top-3 cause coverage | % of deferred volume in top 3 causes | measure | ≥70–80% |
| Early-warning precision | % of flags that become real events | n/a | set in pilot |
| Early-warning lead time | Hours/days of advance notice | 0 | ≥24–72h |
| Recovery time (MTTR) | Mean duration of loss events | baseline | ↓ X% |
| Deferred bbl recovered | Volume recovered vs. counterfactual | 0 | quantify |
| Data completeness | % events with valid cause/duration | assess | ≥95% |
| Report adoption | Active users / decision actions | 0 | set |

**Scope boundary (proposed):**
- **In:** deferment analytics + prediction for OML 24 producing fields, on data available in `lh_silver`.
- **Out (unless added):** real-time SCADA/streaming ingestion, automated field control actions, physical intervention execution, new instrumentation.

---

## 4. Data requirements & `lh_silver` mapping

The readiness assessment mapped ~**51 datasets across 17 directories** in `lh_silver`. Below is the proposed data contract for this use case. Column names are illustrative — to be confirmed in discovery.

### 4.1 Core (must-have)
| Data domain | Typical tables/fields | Use |
|---|---|---|
| **Deferment register** | event_id, start_ts, end_ts, duration, well_id, facility_id, flow_station_id, field_id, cause_code, cause_desc, deferred_volume_bbl, planned/unplanned, notes | Target + cause Pareto |
| **Production actuals** | well_id, date/ts, oil_bbl, gas, water, choke, runtime/hours-on, downtime_flag | Actual vs potential |
| **Potential / allowable** | well_id, date, potential_oil_bbl, allowable, capacity, source | Denominator for loss |
| **Well master** | well_id, field, flow_station, completion type, artificial lift, spud/completion date, status | Dimension/benchmark |
| **Facility/equipment master** | facility_id, type, station, install date, criticality, capacity | Failure attribution |
| **Cause code catalogue** | cause_code, cause_description, category, parent cause | Taxonomy/Pareto hierarchy |
| **Allocation / test data** | well_test_id, test_date, rate, GOR, water cut, choke, allocation factor | Potential estimation |

### 4.2 Enrichment (high-value)
| Data domain | Use |
|---|---|
| **Maintenance / work orders** (WO id, equipment, type, date, failure code, repair hours) | Root-cause linkage, MTTR, predict failures |
| **Equipment run hours / run-life** (ESP, compressor, pump) | Survival/time-to-failure features |
| **Power / utilities logs** | Third-party/utility cause attribution |
| **Weather / metocean** | Weather-driven deferment features |
| **HSE/incident logs** | Correlation with safety events |
| **Gas-lift / injection data** | Subsurface/artificial-lift diagnosis |
| **Pipeline/export & terminal data** | Export-constraint loss |
| **Community/security incident logs** | Third-party/sabotage causes |
| **Drilling/rig schedule** | Planned deferment & demand spikes |
| **Financial (oil price, opex)** | Value quantification of deferred bbl |

### 4.3 Data-quality assessment checklist
- [ ] Cause codes: coverage, consistency, free-text vs. coded, multiple causes per event?
- [ ] Event timing: exact start/end vs. date-only; overlapping events; zero/negative durations
- [ ] Deferred volume: measured vs. derived; units; gross vs. net
- [ ] Key integrity: well_id/facility_id referential integrity across tables
- [ ] Potential/allowable: consistent methodology over time; stale well models
- [ ] Allocations: test recency and allocation factor stability
- [ ] Duplicates and reconciliation vs. the enterprise DW / source systems
- [ ] Time zones, DST, units (bbl, m3, scf), currency
- [ ] Late-arriving and restated data (slowly changing dimensions)
- [ ] Historical depth & completeness (enough history for seasonality/training)

---

## 5. Analytics methodology

A layered approach — **descriptive → diagnostic → predictive → prescriptive** — with each layer producing a shareable deliverable.

### 5.1 Descriptive — "What happened?"
- **Pareto:** rank cause categories by deferred volume; cumulative % line; identify top 2–3 causes. Repeat at **field** and **flow-station** level.
- **Decomposition:** split loss into **frequency × duration × rate impact** (how much is many short events vs. few long ones).
- **Waterfall / bridge:** potential → less each cause category → actual, per period.
- **Trends:** monthly/weekly deferment %, by cause/field; seasonality; shift patterns.
- **Benchmarking:** field vs. field, flow station vs. flow station, planned vs. unplanned ratio.
- **Cost overlay:** deferred bbl × realized oil price = value deferred; value at risk by cause.

### 5.2 Diagnostic — "Why did it happen?"
- **Root-cause analysis:** 5-Whys and fishbone on the top causes (people, process, equipment, environment, third-party).
- **Contribution analysis / drivers:** relate event frequency & duration to equipment age, run-life, maintenance backlog, operating envelope, water cut, GOR, choke, power reliability.
- **Correlation & lag analysis:** do maintenance deferrals precede failures? Does weather lead third-party events?
- **Repeat-event detection:** recurring loss drivers per equipment/well (the proposal's "trend and pattern detection for recurring loss drivers").
- **Cause-code hygiene:** quantify "unknown/other" and re-classify where free text allows (NLP on notes is a candidate quick win).

### 5.3 Predictive — "What is likely next?"
Two complementary prediction problems:

**(A) Event occurrence / risk scoring** — *will a loss event start in the next N days on this well/equipment?*
- Framing: binary classification (next 24–72h) at well × facility × day granularity.
- Candidates: gradient-boosted trees (LightGBM/XGBoost), regularized logistic regression baseline.
- Features: prior event history (counts, recency, duration), equipment run-life/age, maintenance backlog, water cut/GOR trends, choke/pressure deviations, power reliability, weather forecasts, gas-lift performance, well-test recency.
- Output: probability per entity + ranked **early-warning flag list**.

**(B) Deferred volume / duration forecasting** — *how many barrels/days are at risk?*
- Framing: time-series regression / hierarchical forecasting (well → flow station → field → OML).
- Candidates: gradient boosting with lag features, seasonal/prophet-style models, hierarchical reconciliation to OML total.
- Output: expected deferment and target variance; confidence intervals.

**(C) Anomaly detection (supporting)** — unsupervised detection of abnormal well/equipment behaviour (pressure, rate, temperature, runtime) that precedes failure. Isolation Forest / autoencoders / robust z-scores / change-point detection.

**Optional (D) Survival analysis** — time-to-failure modelling for critical equipment (ESP/compressor) to estimate remaining useful life.

### 5.4 Prescriptive — "What should we do?"
- **Barrels-at-risk × probability × cost** ranking → prioritised intervention list.
- **What-if / scenario:** impact of maintenance timing, spare availability, logistics on deferment.
- **Recommended actions** surfaced to the right owner (linking to Part 3 MAF for automated routing).

### 5.5 Model design, training & evaluation
- **Data splits:** time-based (no leakage); train on historical, validate on recent, hold out for backtest.
- **Class imbalance:** production failures are rare → use class weighting, PR-AUC, not accuracy.
- **Business-weighted evaluation:** score = `(bbl prevented × price) − intervention cost`; prioritise **lift** in top-K alerts.
- **Metrics:** Precision/Recall, PR-AUC, ROC-AUC, MAE/MAPE (volume), lead time, alert precision@K.
- **Explainability:** SHAP per prediction so engineers can trust/act.
- **Retraining:** scheduled refresh as new events accrue; monitor drift.

---

## 6. Fabric / Microsoft architecture

```
Sources (historian/SCADA, maintenance, production db, ERP, spreadsheets, enterprise app)
        │  Data Factory / pipelines / shortcuts
        ▼
   lh_bronze  →  lh_silver (validated, conformed)  →  lh_gold (analytics-ready)
        │                                   │
        │                             Semantic model (Direct Lake)
        │                                   │
        ├── Fabric Notebooks (PySpark, MLflow) ──► ML models & scores
        │
        ├── Power BI (Executive Pareto, cause drill-down, heatmaps, alert list)
        └── Data Activator (alerting) ──► Teams/Email → owner action
        (Part 3) MAF multi-agent layer on top for autonomous, approved outputs
```

**Component roles**
| Component | Purpose |
|---|---|
| Data Factory / pipelines | Ingest + orchestrate; scheduled & event-driven |
| `lh_silver` | Single governed source of conformed deferment/production data |
| `lh_gold` | Purpose-built facts/dims: fact_deferment_event, dim_well, dim_facility, dim_cause, fact_production_daily |
| Fabric Notebooks | Feature engineering, model training, scoring, backtests |
| MLflow | Model/run tracking, versioning |
| Semantic model (Direct Lake) | Fast, governed BI over OneLake |
| Power BI | Dashboards per audience (exec, asset/OPM, field) |
| Data Activator | Threshold/ML-driven alerts & routing |
| MAF (Part 3) | Autonomous reasoning, narrative generation, approved actions |

**Data model anchors (proposed star schema):**
- `fact_deferment_event` (event_id, well_key, facility_key, cause_key, field_key, station_key, start, end, duration_hrs, deferred_bbl, planned_flag, restored_ts)
- `fact_production_daily` (well_key, date, actual_bbl, potential_bbl, deferred_bbl, runtime_hrs, water_cut, gor, choke)
- `dim_cause` (cause_key, cause_desc, category, parent_cause) — **hierarchical**
- `dim_well`, `dim_facility`, `dim_field`, `dim_flow_station`, `dim_date`

**Governance:** cause-code standard, data stewardship, definition catalogue (KPIs), lineage, row-level security by asset/field where needed, refresh SLAs.

---

## 7. Deliverables & dashboard design

**Analytical deliverables**
1. **Cause Pareto** — top causes by deferred volume (OML / field / flow station filters).
2. **Volume bridge/waterfall** — potential → causes → actual.
3. **Field & flow-station comparison** — ranked bars + heatmap of deferment %.
4. **Recurring-driver trend view** — causes over time, seasonality.
5. **Early-warning list** — ranked wells/equipment with probability + barrels-at-risk + recommended owner.
6. **Event detail drill-through** — timeline of individual events with notes/WO linkage.
7. **Value view** — deferred bbl × price, value at risk, recovery tracking.

**Dashboard audiences**
| Audience | View focus |
|---|---|
| Executive/OPM | Deferment %, top causes, value at risk, trend vs. target, exceptions |
| Asset Manager | Asset/field performance, intervention priorities, early warnings |
| Production/Field Ops | Event timeline, MTTR, WOs, immediate alerts |
| Business Excellence | Standardised cause reporting, integrity of cause attribution |

**Alerting examples (Data Activator)**
- New loss event exceeding X bbl or Y hrs → notify production/asset owner
- Predicted failure probability > threshold for critical equipment → notify maintenance
- Deferment % breaches daily/weekly threshold → notify exec

---

## 8. Delivery plan (proposed, within the 45-day implementation)

| Stage | Activities | Output | Indicative days |
|---|---|---|---|
| **1. Discovery & Value Definition** | Workshops; confirm sources, cause taxonomy, potential methodology; agree KPIs; SOW | BRD, data contract, backlog | ~5 |
| **2. Data preparation (in Advanced Use Case Development)** | Profile & clean `lh_silver`; build conformed gold model; DQ remediation | Governed `lh_gold` facts/dims | (within 20) |
| **3. Descriptive & diagnostic** | Pareto, decomposition, trends, benchmarking, root-cause analysis | Pareto + comparison dashboards | (within 20) |
| **4. Predictive** | Feature engineering, model training, backtest, early-warning scoring | Flag list + model card | (within 20) |
| **5. Validation** | Business validation with ops/maintenance; refine; UAT | Signed-off views/models | — |
| **6. Knowledge transfer** | Instructor-led enablement; documentation | Trained users, runbook | ~3 |
| **7. Managed services** | Monitoring, retraining, support | SLA-backed operation | annually |

*Projects will be selected/sequenced by the weighted scoring model; this use case runs inside the Part-1 sprint(s), delivered under SAFe with reviews feeding the next sprint backlog.*

---

## 9. Roles & responsibilities (proposed RACI)

| Role | Wragby | NewCross |
|---|---|---|
| Solution/engagement lead | R/A | C |
| Data engineer | R | C |
| Data analyst / BI | R | C |
| Data scientist | R | C |
| Production/data SME | C | **A/R** |
| Maintenance/reliability SME | C | **A/R** |
| Cause-code/data steward | C | **A/R** |
| Business Excellence owner | C | **A/R** |
| IT/platform (Fabric) | C | **A/R** |

*(R=responsible, A=accountable, C=consulted. Exact split to be agreed.)*

---

## 10. Risks specific to this use case

| Risk | Impact | Mitigation |
|---|---|---|
| Inconsistent/unreliable cause codes | High — invalidates Pareto | Cause-code workshop; standardise & re-map; NLP on notes; "unknown" tracking |
| No true potential/allowable data | High — can't compute loss | Agree proxy (well models, test rates, capacity); document assumptions |
| Deferred volume derived inconsistently | High | Reconcile to source; define single formula; version it |
| Sparse/few failure events | Medium | Class weighting; broader target windows; survival analysis; regularise |
| Event timing granularity (date-only) | Medium | Reconstruct from WO/SCADA where possible; quantify uncertainty |
| Concept drift / new equipment | Medium | Scheduled retraining; drift monitoring; champion/challenger |
| Low operational trust/adoption | High | Explainability (SHAP), early co-design with ops, plain-language narratives |
| Overlapping/multi-cause events | Medium | Define primary-cause rule; allow cause contribution split |
| Scope creep into real-time control | Medium | Clear scope boundary; change management (SOW clause) |

---

## 11. Value quantification (illustrative framework)

```
Value = (Deferred bbl addressable × Recovery rate × Realised oil price)
        − (Intervention cost + implementation cost)
```
- **Addressable** = deferred volume under top-3 causes within operational control.
- **Recovery rate** = assumed improvement from faster/prioritised response (calibrate in pilot).
- **Value at risk** = predicted deferred bbl × price (feeds prioritisation).
- Track **baseline vs. post-deployment** deferment % and MTTR to attribute benefit.
- Align benefits to **target vs. plan** and **NUIMS/JV partner reporting**.

---

## 12. Discovery checklist & open questions

**Data**
- [ ] What is the exact deferment/potential data model in `lh_silver`? Which of the 51 datasets cover deferment?
- [ ] Is deferred volume measured, derived, or both? Single formula? Gross/net?
- [ ] Cause-code catalogue & hierarchy; how many "unknown/other"?
- [ ] Event timing granularity; overlapping events; planned vs. unplanned tagging.
- [ ] Maintenance/WO and equipment run-life availability and keys.
- [ ] History depth and completeness; restatements.
- [ ] Well-test/allocation recency and methodology.

**Business**
- [ ] What defines "the 2–3 root causes" success — volume or frequency?
- [ ] Which decisions/owners will act on the early warnings?
- [ ] Acceptable lead time and precision for alerts (to avoid alert fatigue)?
- [ ] How is deferment reported to partners (NUIMS) and Business Excellence today?
- [ ] What is the current baseline deferment % and MTTR?
- [ ] Priorities: recover volume, reduce frequency, or reduce duration first?

**Technical**
- [ ] Fabric capacity/workspace access; `lh_silver` read permissions; gold layer ownership.
- [ ] Direct Lake vs. import for the semantic model.
- [ ] Power BI for the Org / deployment pipelines; Data Activator licensing.
- [ ] MLflow/model registry availability; retraining cadence.
- [ ] Security/RLS by asset and role.

---

## 13. Quick wins (first demos)

1. **Cause Pareto on historical data** (OML / field / flow station) — immediate, high-credibility.
2. **Deferment % trend + waterfall** by month with value overlay.
3. **Field/flow-station heatmap** benchmarking.
4. **"Unknown/other" cause cleanup** using NLP on free-text notes.
5. **Rule-based early warning** (recurring equipment patterns) before the ML model is productionised.

These can be demonstrated quickly on validated `lh_silver` data — consistent with the proposal's claim that three projects can be built and demoed immediately.

---

## 14. Relationship to other projects

- **Production Performance Forecasting & Target Variance Analytics** identifies *where* underperformance occurs; **this project explains *why*** production is lost.
- **Supply Chain / Bottleneck Analytics** determines whether procurement/maintenance delays are blocking the interventions needed to recover loss.
- **Part 2 (Asset Manager/OPM, Executive, Business Excellence views)** consumes this project's gold model and Pareto outputs.
- **Part 3 (MAF)** automates continuous monitoring, narrative generation, and approved alerting/action on top of these predictions.

---

*Prepared as a working blueprint. All field/table names, KPIs, and targets are proposals to be confirmed during Discovery and Value Definition.*
