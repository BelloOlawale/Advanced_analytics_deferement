# Proposal Summary — "Advanced Analytics & AI Proposal" (Wragby → NewCross)

> Source document: `Advanced Analytics & AI Proposal_Newcross.docx`
> Author: Wragby Business Solutions & Technologies Ltd. · Last modified by Daniel Opanubi
> Version control: v1.0 Ayooluwa Amole (Jul 2026); v1.1 Olanna Ogbenna (Jul 2026)
> Created 8 Jul 2026 · Last modified 7 Oct 2026 · ~3,458 words

**Related documents in this repo:**
- `deferment-root-cause-deep-dive.md` — analytics deep dive on Part 1, Project 1 (Deferment Root-Cause & Production Loss Prediction)
- `deferment-fabric-build-spec.md` — what is proposed to the customer, how it is built, and how it works in Microsoft Fabric
- `deferment-ml-engineering-blueprint.md` — pure technical ML/AI engineering blueprint (problem framing, potential engine, models, causal, LLM layer, MLOps, tools)

---

## 1. Executive Summary

Wragby proposes an **Advanced Analytics and Decision Intelligence** engagement for **NewCross Exploration & Production (NewCross EP)**.

**Client context:**
- Operates **OML 24** — a **162 sq. km onshore asset** in the **western Niger Delta**
- Comprises the **Awoba, Awoba North West, and Ekulama** producing fields
- Combined facility capacity **>130,000 bbl/day**, growth target **100,000 bopd within 5–7 years**
- **33% recent production uplift** plus ongoing drilling campaigns
- Already invested in **Microsoft Fabric** and an enterprise data warehouse

**De-risking:** Wragby ran a data readiness assessment of the existing environment, mapping roughly **51 datasets across 17 directories in the `lh_silver` lakehouse**, confirming data depth/quality sufficient to build and demo three high-value analytics projects immediately.

**Three-part roadmap:**
1. **Part 1 — Three data-validated projects:** Deferment Root-Cause & Production Loss Prediction; Supply Chain Spend & Bottleneck Analytics; Production Performance Forecasting & Target Variance Analytics (selected via a weighted scoring model: business value, data availability, data strength, demo readiness).
2. **Part 2 — Full enterprise coverage:** Asset Management Analytics, Executive View, Business Excellence, HoD View, and full redesign of deferment and production reporting.
3. **Part 3 — Multi-Agentic Framework (MAF):** deeper automation, alerting, predictive maturity.

**Outcome:** a proactive, insight-driven operating model that starts from proven data and expands deliberately — maximising ROI on the existing Fabric investment while managing risk.

---

## 2. About Us (Wragby)
- "Anxiety-free IT partner"; "pedigree of firsts"; **N10B+ revenue**.
- Differentiators: first-in-class services, strategic partnerships, technical expertise, exceeding expectations; awards.
- Operates from **9 divisions**: Software Engineering, Technology Services Solutions, Business Solutions, Marketing & Communications, Sales & Customer Success, Cloud & Infra, Digital Advisory, Data Management & Analytics, G.R.C.S., PMO.

---

## 3. Business Context and Opportunities
- Upstream needs more than retrospective visibility: know *what happened*, *what's next*, *where to focus*, *what action to take*.
- Priority areas: financially sensitive operations, base logistics in challenging Niger Delta terrain, ageing asset-intensive infrastructure, executive oversight across a growing portfolio.
- Sector shifts: **Petroleum Industry Act (PIA)**, IOC divestments, Federal Government production targets → indigenous operators must decide faster/better.
- Since Fabric + EDW exist, focus is on **accelerating value** (advanced analytics, ML, intelligent alerting, automation) on a governed, scalable platform.

---

## 4. Advanced Analytics and Automation
- **Advanced analytics** = predictive models, anomaly detection, forecasting, optimization, scenario analysis.
- **Automation** = the operational response following insight.
- Practical automation examples:
  - Alert finance when cost thresholds/cash-flow forecasts deviate
  - Trigger maintenance when asset health crosses thresholds (via **RADA-AMS**)
  - Notify base ops on logistics demand spikes (drilling/crew rotations)
  - Route executive exceptions on production/safety/ESG breaches
  - Generate automated **JV partner reports** aligned with **NUIMS** governance
- Goal: evolve reporting platform → **intelligent decision-support system** toward 100,000 bopd.

---

## 5. Assumptions / Risks
**Assumptions:** client reps available; required information available; training is instructor-led.

**Risk profile (as listed):**

| # | Risk | Impact | Probability | Rating | Owner | Mitigation |
|---|---|---|---|---|---|---|
| 2 | NewCross involved in other projects | 4 | TBD | TBD | Wragby | Prioritize assigned NewCross resources |
| 3 | Wragby project resource unavailable | 5 | 1 | 5 | Wragby | Assign replacement resource |
| 4 | Delay due to client unavailability | 5 | 1 | 1 | Newcross | Time & Materials for extra days |

*Table starts at row 2; one probability cell is "TBD".*

---

## 6. Project Scoping and Methodology

Projects selected via a **weighted scoring model** against confirmed `lh_silver` contents.

### Part 1 — Advanced Analytics

**a) Deferment Root-Cause & Production Loss Prediction**
- Built on production + deferment-cause data in `lh_silver`.
- Root-cause **Pareto analysis** to identify the 2–3 causes behind most production loss; predictive flagging of emerging loss patterns.
- Deliverables: Pareto by cause/field/flow station; trend & pattern detection; early-warning flags; field-by-field and flow-station comparison.

**b) Supply Chain Spend & Cycle-Time / Bottleneck Analytics**
- Spend by supplier/cost centre/category; cycle-time requisition→fulfilment; bottleneck identification; supplier performance & lead-time scoring.

**c) Production Performance Forecasting & Target Variance Analytics** *(named in narrative; not separately detailed in the commercial sheet)*

Logic: **Forecasting** identifies underperformance → **Deferment analytics** explains why production is lost → **Supply Chain analytics** reveals whether procurement delays block recovery.

### Part 2 — Report Redesign, Automation and Executive View
- **Executive View:** leading indicators, trend inflections, drivers, exceptions across financial/operational/asset/ESG, drill-through, **AI-generated narratives**
- **HoD View:** role-based departmental navigation (Overview, Performance Drivers, Exceptions, Trends, Actions Required, Drill-through)
- **Asset Manager / OPM View:** asset performance, production delivery, deferment exposure, facility utilisation, intervention priorities; daily/weekly/monthly reviews; asset performance comparison
- **Production & Deferment Report Redesign (Business Excellence):** interactive, insight-led, aligned to Business Excellence templates/themes
- **Enterprise Application Reports:** direct from the enterprise application
- **Departmental Risk Report (Extended Coverage):** cross-department risk view, trends, mitigation prioritization, ownership

### Part 3 — MAF (Multi-Agentic AI Framework)
- Autonomous multi-agent system: continuous operational awareness, multi-agent reasoning (orchestrator + specialists in parallel), knowledge-grounded analysis, human-guided actions, autonomous scheduled execution.
- Flow: trigger → orchestrator coordinates specialists → structured output + findings + next steps → routed to reviewer for approval → distribution/action.
- Value: proactive, automated, intelligence-led; faster action, less repetitive work, consistency, reusable across scenarios.

---

## 7. General Engagement Approach
- Discovery sessions (representatives, data/process owners, report owners); per-department requirement gathering.
- Delivered by the **Data Management & Analytics** team using **SAFe**; phased, concurrent delivery.
- Stakeholder reviews added to backlog for next sprint.
- **UAT** against gathered requirements; **knowledge transfer** after UAT sign-off; transition to **managed services / annual support**.

**Work plan** (text states **45 working days**; table days total 88 → phases overlap):

| Stage | Key Deliverables | Days | Stakeholders |
|---|---|---|---|
| Discovery & Value Definition | Workshops, BRDs, requirement sessions, SOW | 5 | Data Analysts (2), Data Scientist |
| Advanced Use Case Development | Predictive models, anomaly detection, simulations, decision frameworks, executive views | 20 | Data Analyst |
| Report Redesign, Automation & Executive View | Production report redesign; HoD/AM-OPM/Executive views; enterprise app reporting; extended risk | 30 | Data Analysts (2), Data Engineer |
| MAF Multi-Agentic AI Framework | Autonomous multi-agent platform; specialist agents | 30 | Data Scientist, AI Engineer |
| Knowledge Transfer | Business-user sessions | 3 | Data Analysts, Data Scientist, AI Engineer |

---

## 8. Commercial Summary
Pricing embedded as an image (EMF) in the document; extracted contents:

**Subscription (recurring):**
- **Microsoft Fabric** — Analytics / AI + ML, Region **West Europe**; F16, **16 capacity units × 1 Year RI**, OneLake storage **1,000 GB**
- **Model:** GPT-5.2-chat, Standard (On-Demand), Global; 2,100 × 1,000 input tokens; 2,790 × 1,000 cached input; 940 × 1,000 output tokens
- Qty **1**, **12 months**, unit **$1,784.80** → **$21,417.60**

**Implementation:**
- Part 1: Advanced Analytics — *Use Case 1 – Supply Chain Spend & Cycle-Time / Bottleneck Analytics* (only this use case itemized)
- Part 2: Report Redesign and Automation — Executive View; HoD View; Production & Deferment Report Redesign; Enterprise Application Reports; Asset Manager/OPM View; Departmental Risk Report
- Part 3: MAF – Multi-Agentic AI Framework
- **Implementation total: $15,734.66**

| Item | Amount |
|---|---|
| Sub Total | **$37,152.26** |
| VAT (7.5%) | **$2,786.42** |
| **Total** | **$39,938.68** |

**Commercial Terms:** excludes travel unless stated; based on defined scope; platform enhancements/new requirements excluded.
**Payment Terms:** **80% on PO before kick-off**; **20% on completion/sign-off**; off-the-shoulder knowledge transfer during project.

---

## 9. Document Acceptance & Validity
- Acceptance page = mutual attestation of understanding; scope changes require Wragby **Change Management** (may affect cost/schedule).
- **Validity:** SOW expires **90 days after publication date** unless extended in writing.
- SOW is not a formal offer/contract; subject to Wragby's Service Agreement; Wragby takes exception to client RFP terms.
- Disclaimer: submitted in good faith; if selected, Wragby negotiates in good faith to finalize agreements.

---

## 10. Key Observations / Inconsistencies
1. **Part 1 scope mismatch:** narrative names **three** projects; commercial image itemizes only **one** (Supply Chain).
2. **Timeline math:** stated **45 working days** vs. table sum of **88** → reconcile via overlapping phases.
3. **Risk table** starts at row 2; one probability "TBD".
4. **Dates:** version control says Jul 2026 but metadata modified Oct 2026.
5. **Deferment redesign** and **Production Forecasting** appear in narrative but not in commercial breakdown (likely rolled into Part 2).
@