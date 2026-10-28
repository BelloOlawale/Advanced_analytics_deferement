# Automation vs Human-in-the-Loop — and Platform Alternatives

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Questions answered here: **Which tasks run themselves, and which need a person? What can replace Power Automate and Power Apps?**
> Status: design · Version 0.1 · 2026-10-12
> Companion: `alert-log-and-feedback-loop.md`, `technology-stack-and-fabric-implementation.md`.

---

## 1. Four kinds of human involvement (defined)

"Human-in-the-loop" is used loosely. We use four precise levels so every task can be placed unambiguously:

| Level | Name | Meaning | Does the human block progress? |
|---|---|---|---|
| 0 | **Automated** | The machine does it; no human involved | — |
| 1 | **Human-on-the-loop** | The machine runs on its own; a person watches and can intervene, but does not have to | No |
| 2 | **Human-in-the-loop** | The machine proposes; a person must approve before it takes effect | **Yes** |
| 3 | **Human-executes** | Only a person can perform the action (a physical act or a judgement) | Yes (it *is* the action) |

There is also a governance role — **the human sets the policy** (thresholds, budgets, owner maps) that governs how the automation behaves. That is level 2 applied to configuration.

---

## 2. Task-by-task map

Grouped by stage. "Who" is the machine or the human; the level is from Section 1.

### A. Ingestion and preparation

| Task | Who does it | Level |
|---|---|---|
| Copy data from sources into the raw layer (read-only) | Machine | Automated |
| Stamp batches and log every read | Machine | Automated |
| Clean, type, de-duplicate the target, group causes | Machine | Automated |
| Reconstruct event episodes | Machine | Automated |
| Run the daily data-quality check | Machine | Automated (warns; does not block) |

### B. Building clues and answers

| Task | Who does it | Level |
|---|---|---|
| Build entity-day clues (features) | Machine | Automated |
| Learn each entity's own normal (baselines) | Machine | Automated |
| Build the answer key (onset labels) | Machine | Automated |

### C. Learning

| Task | Who does it | Level |
|---|---|---|
| Split data by time | Machine | Automated |
| Train the model(s) | Machine | Automated |
| Log runs/metrics to the registry | Machine | Automated |
| Evaluate against the held-back period | Machine | Automated |
| **Promote a new model version** | Machine proposes; **person approves** | **Human-in-the-loop** |
| Decide the production thresholds / alert budget | **Person** (config tables) | **Human-sets-policy** |
| Retrain on schedule | Machine | Automated (promotion still gated) |

### D. Running every day

| Task | Who does it | Level |
|---|---|---|
| Score every station and well | Machine | Automated |
| Rank by money, assign tiers | Machine | Automated |
| Write the daily output tables | Machine | Automated |
| Fire alerts to owners | Machine (per policy) | Automated |
| Suppress duplicates / respect the budget | Machine | Automated |
| Refresh the dashboard | Machine | Automated |
| Watch the overnight run, step in on failure | Person | Human-on-the-loop |

### E. Responding

| Task | Who does it | Level |
|---|---|---|
| Receive the alert | Person | Human-executes (by nature) |
| **Decide and act** (inspect, adjust, dispatch) | **Person** | **Human-executes** |
| Record "acknowledged / acted / not real" | Person | Human-executes (one click) |
| Confirm whether the event happened | Machine | Automated |
| Compute realised lead time | Machine | Automated |
| Weekly reconciliation of the alert log | Person | Human-executes |
| Monthly re-tune of thresholds | Machine proposes; person approves | **Human-in-the-loop** |
| Continuous monitoring of drift and data quality | Machine | Automated |
| Consume the report and make operational/business decisions | Person | Human-executes |
| Govern access, RLS, classifications | Person | Human-sets-policy |

### The short version

**Fully automated (no human):** ingest → clean → build clues → build labels → train → score → rank → fire alerts → suppress → refresh → confirm outcomes → compute lead time → monitor drift.

**Human-in-the-loop (approval gate):** promoting a model version; approving monthly threshold re-tunes; changing alert policy.

**Human-executes (only a person can):** acting on an alert; the one-click acknowledgement; the weekly reconciliation; using the report to make decisions.

**Human-on-the-loop (supervise):** watching the overnight run and responding to a failure.

> **Design principle:** keep humans **out of the hot path** (alerts fire automatically, every day, without anyone pressing a button) and **in at the moments of judgement** (approve a model, approve a threshold, decide an intervention). Never ask a person to do something the machine can do reliably; never let the machine make an irreversible judgement call on its own.

---

## 3. Where the human touchpoints sit in the loop

```
 ingest ─▶ clean ─▶ clues ─▶ train ─▶ [★ human approves model] ─▶ score
   ▲                                                              │
   │                                                              ▼
 monitor (human-on-the-loop)                                   fire alerts (auto)
   ▲                                                              │
   │                                                              ▼
 [★ human approves re-tune] ◀── monthly re-tune ◀── learn ◀── [★ human acts + one-click ack]
                                                        ▲
                                                        └── outcome auto-confirmed ──┘
```

Only three points require a human to **block or act**: approve a model, approve a re-tune, and act on the alert. Everything else runs itself or is watched.

---

## 4. What Power Automate and Power Apps are doing here — and what can replace them

### What they do in the current design

- **Power Automate** is the **glue**: it receives the button click from the Teams alert card and writes the outcome row back into the gold table.
- **Power Apps** is an **optional richer capture screen** — used *only* if the one-click Teams card is not enough (e.g. long notes, bulk review). **The baseline design does not require it.**

Two clarifications:

- The **alert itself** is sent by **Data Activator** (a Fabric item) — that is **not** Power Automate, and it does not need replacing.
- The **capture/acknowledgement write-back** is the only place Power Automate/Power Apps appear.

### Replacements for Power Automate (the write-back glue)

| Option | What it is | Notes / fit |
|---|---|---|
| **Fabric User Data Functions** | Serverless functions that live *inside* Fabric, callable by API, can write to the lakehouse | **Best fit** — runs on the existing Fabric capacity, no extra licence, keeps everything in Fabric |
| **Azure Functions** | Code (Python/C#/JS) triggered by an HTTP call | Strong, cheap, Azure-native; a little more engineering than a low-code flow |
| **Azure Logic Apps** | Low-code workflow, connector-based | Closest like-for-like to Power Automate; good if the team prefers low-code |
| **Teams bot** (Azure Bot Service) | A bot that handles the card buttons directly | Best UX for pure Teams interaction; more build effort |
| **Fabric data pipeline / notebook via REST** | Trigger a Fabric job from the callback | Works, but heavier than a function for a single write |
| **Dataverse + plug-in** | Store the outcome in Dataverse | Only if Dataverse is already in the estate |
| **Non-Microsoft** (n8n, Make, Zapier, Temporal) | Workflow tools | Generally not preferred in a Microsoft/Fabric estate |

### Replacements for Power Apps (the capture UI)

| Option | What it is | Notes / fit |
|---|---|---|
| **Teams Adaptive Cards** | Buttons/dropdowns inside the alert message | **Recommended default** — no app, no extra licence, capture where the operator already is |
| **Custom Teams tab / app** | A richer form hosted in Teams | Good if more fields are needed than a card |
| **Custom web app** (React/Vue) | A small site on Azure Static Web Apps / App Service, secured by Entra | Full control; most build effort |
| **Streamlit / Dash / Gradio** on App Service | A lightweight Python review console | **Great fit for the weekly analyst review** — fast to build |
| **Microsoft Forms** (or a SharePoint/Microsoft List) | A simple form or list | Very low effort; weak validation and UX |
| **Excel/CSV drop into a OneLake folder** | Manual file upload | Lowest-tech pilot fallback only |

### Recommended minimal stack (avoids extra licences)

```
 Alerting        : Data Activator                    (Fabric — already in scope)
 Capture (operator) : Teams Adaptive Cards           (no extra licence)
 Write-back      : Fabric User Data Functions        (runs on Fabric capacity)
 Optional (analyst) : Streamlit console on App Service
```

With this, **Power Apps is not needed at all**, and **Power Automate is optional** — replaced by a Fabric-native function. If the organisation prefers low-code and already licenses the connectors, **Logic Apps** is the drop-in substitute for Power Automate, and **Power Apps** can still be used without changing the underlying tables.

### Comparison at a glance

| Need | Lowest effort | Most Fabric-native | Full control | No extra licence |
|---|---|---|---|---|
| Receive a click and write a row | Logic Apps | **Fabric User Data Functions** | Azure Functions / bot | **Fabric User Data Functions** |
| Capture a short response | **Teams Adaptive Card** | Teams Adaptive Card | Custom web app | **Teams Adaptive Card** |
| Capture a long review | Microsoft Forms | — | Streamlit console | Streamlit on App Service (uses existing Azure, minimal cost) |

---

## 5. Summary

- **Automated:** everything from ingestion through scoring, alerting, outcome confirmation and monitoring.
- **Human-on-the-loop:** watching the overnight run and stepping in on failure.
- **Human-in-the-loop (approval gates):** promoting a model version, approving monthly threshold re-tunes, changing alert policy.
- **Human-executes:** acting on an alert, the one-click acknowledgement, the weekly reconciliation, and the business decisions the report informs.
- **Power Automate** can be replaced by **Fabric User Data Functions**, **Azure Functions**, **Azure Logic Apps** or a **Teams bot**; the alerting itself is Data Activator and needs no replacement.
- **Power Apps** is optional; the default is **Teams Adaptive Cards**, with an optional **Streamlit** console for the weekly analyst review.

---

*Design note, 2026-10-12. Mechanism choices to be confirmed with IT/operations during Discovery, subject to licensing and the client's platform standards.*
