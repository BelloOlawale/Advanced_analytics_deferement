# Documentation Index

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Last updated: 2026-10-21

This index lists every document in the repository, what it is for, and the order to read them in.

---

## Start here (the core set)

| Document | What it is | Read when |
|---|---|---|
| `prd-deferment-early-warning.md` | **Product Requirements Document** — problem, goals/KPIs, requirements, deliverables & outputs, delivery approach, milestones, risks, open questions | First — the "what and why" |
| `wbs-deferment-early-warning.md` | **Work Breakdown Structure** — standalone, build-only plan: tree, dictionary, milestones, Gantt, effort, RACI, per-station coverage | To plan and cost the build |
| `early-warning-architecture.md` | **Architecture** — medallion layers, end-to-end flow, data contracts, serving & consumption, security, environments | To understand how it is built |
| `early-warning-model-design.md` | **Model design** — the three layers (deviation engine → onset model + survival → value ranking), labels, evaluation, build order | To understand the modelling approach |
| `how-the-model-works.md` | **Plain-language guide** — the whole pipeline from cleaning to feedback, with diagrams, a worked example and a glossary; includes "is this a time-series solution?" | For non-specialist readers |
| `end-to-end-in-plain-language.md` | **Self-contained end-to-end explainer** — build, outputs as concrete tables per flow station (daily risk, deviation, daily position, alert log), and how the customer uses it; no prior reading or other documents required | For anyone new to the solution |
| `pipeline-in-plain-language.md` | **Plain-language pipeline walkthrough** — the data's journey: sources → ingestion → raw/clean/ready layers → clues → answers → training → checking → daily scoring → output → delivery → feedback; includes a tracked example of one reading | To understand how the data flows and how the model is built |
| `alert-log-and-feedback-loop.md` | **Alert mechanism & feedback loop** — how the alert logic fires, the alert log schema, who records whether an alert was false or acted on (system / recipient / analyst), and how that record is leveraged to tune and retrain | To understand alerting and the learning loop |
| `technology-stack-and-fabric-implementation.md` | **Technology stack & Fabric implementation** — the full stack, how each stage maps to Fabric workloads, how training works (notebooks + MLflow), whether we work directly in Fabric, and where the output lives | To understand the platform and deployment |
| `automation-and-human-in-the-loop.md` | **Automation vs human-in-the-loop** — task-by-task view of what runs itself vs where a person is needed (approval gates, execution), and what can replace Power Automate / Power Apps | To understand who does what, and platform alternatives |
| `model-framing-time-series-vs-forecasting.md` | **Model framing** — why the data is time series but the model is event prediction, not forecasting; component-by-component classification; why not ARIMA/Prophet/LSTM | When the "is this time series? should we forecast?" question comes up |

## Findings (from the real operational data)

| Document | What it is |
|---|---|
| `data-quality-findings.md` | First real read: inventory, per-station numbers, the 86% unusable cause codes, target/missing-data issues |
| `early-warning-patterns.md` | First precursor analysis: the ~95% base-rate reframing, loss persistence, and per-cause precursor profiles (the signal leads the log by ≥7 days) |

## Supporting & background

| Document | What it is |
|---|---|
| `flow-station-early-risk-detection.md` | The flow-station early-risk process and historical-data requirements |
| `deferment-root-cause-deep-dive.md` | Broader deferment analytics blueprint (descriptive → prescriptive) |
| `deferment-ml-engineering-blueprint.md` | ML/AI engineering blueprint (framing, models, MLOps) |
| `how-fabric-delivers-results.md` | How results reach the customer |
| `context.md` | Proposal summary (Wragby → NewCross) |

## Working documents

| Document | What it is |
|---|---|
| `decisions-log.md` | Running log of the key decisions and their rationale |
| `NOTES.md` | Working scratchpad; top section holds the current focus |
| `handoff-newcross-deferment-2026-10-08.md` | Continuity document for a new agent/contributor |
| `handoff-maf-fabric-build-2026-10-21.md` | **Sandbox build handoff** — current state, next steps, traps and suggested skills for a fresh agent |
| `test-environment-setup.md` | **New tenant / sandbox setup** — multi-environment profiles, generating seed data, uploading into Fabric, and switching environments safely |
| `fabric-build-log-maf-sandbox.md` | **Live build log** — what exists in the `maf` sandbox today: environment IDs, seed data, bronze/silver/gold tables, row counts, risk rules, alerts, verification, known issues and next steps |
| `fabric-semantic-model-and-report-plan.md` | **Serving-layer plan** — `df` naming convention, Direct Lake findings, target model, measures and the vertical-slice sequence for the semantic model and report |
| `fabric-parity-check-slice8.md` | **Slice 8 parity report** — Fabric vs clean-room local reference for the same 90-day window; table/KPI results, tolerances, known floating-point ties and the `episode_id` defect |
| `fabric-build-summary-through-slice8.md` | **Complete build summary through Slice 8** — end-to-end narrative, layer details, slice history, Fabric item locations and UI navigation guide |
| `fabric-implementation-and-location-guide.md` | **Implementation and location guide** — how each layer was built in Fabric, item IDs, OneLake/SQL locations and step-by-step Fabric UI navigation |
| `slice9-onset-model-report.md` | **Slice 9 report** — Layer 2 onset labels, logistic-regression challenger, chronological backtest vs rules v1 and the decision to retain rules v1 |

---

## Repository layout

```
├── docs/                     all documents (this folder)
├── Issues/                   backlog of work items (see Issues/README.md)
│   └── Done/                 completed items
├── tools/                    query tool, seed generator, sandbox provisioning, notebook deploy/run
├── fabric/notebooks/         versioned Fabric notebook sources (bronze, silver, gold features, gold risk)
├── test_data/                generated seed data per environment (git-ignored)
├── data/                     local data extracts (git-ignored)
├── logs/                     query logs (git-ignored)
└── <proposal>.docx, Production_shema.xlsx   source inputs
```

## Suggested reading order

1. `end-to-end-in-plain-language.md` — the whole solution end to end, no jargon, no prior reading needed (start here if you are new).
2. `pipeline-in-plain-language.md` — how the data flows, from ingestion to model training to output.
3. `alert-log-and-feedback-loop.md` — how alerts fire, who records outcomes, and how the loop improves.
4. `technology-stack-and-fabric-implementation.md` — the stack, the Fabric build, training, and where output lives.
5. `automation-and-human-in-the-loop.md` — what is automated, where humans are needed, and platform alternatives.
6. `prd-deferment-early-warning.md` — the requirements.
7. `how-the-model-works.md` — the plain-language explanation.
8. `early-warning-model-design.md` — the modelling detail.
9. `early-warning-architecture.md` — the technical build.
10. `wbs-deferment-early-warning.md` — the plan and effort.
11. `data-quality-findings.md` + `early-warning-patterns.md` — what the data showed.
12. `decisions-log.md` — why things are the way they are.
