# Documentation Index

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Last updated: 2026-10-08

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

---

## Repository layout

```
├── docs/                     all documents (this folder)
├── Issues/                   backlog of work items (see Issues/README.md)
│   └── Done/                 completed items
├── tools/                    read-only data query tool for the warehouse
├── data/                     local data extracts (git-ignored)
├── logs/                     query logs (git-ignored)
└── <proposal>.docx, Production_shema.xlsx   source inputs
```

## Suggested reading order

1. `prd-deferment-early-warning.md` — the requirements.
2. `how-the-model-works.md` — the plain-language explanation.
3. `early-warning-model-design.md` — the modelling detail.
4. `early-warning-architecture.md` — the technical build.
5. `wbs-deferment-early-warning.md` — the plan and effort.
6. `data-quality-findings.md` + `early-warning-patterns.md` — what the data showed.
7. `decisions-log.md` — why things are the way they are.
