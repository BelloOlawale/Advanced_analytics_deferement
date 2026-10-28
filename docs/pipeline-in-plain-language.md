# From Data Ingestion to Output — The Pipeline in Plain Language

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Audience: anyone — business, operations, engineering, new joiners — **no data background assumed**.
> Purpose: document, end to end and in ordinary words, how data travels through the solution: **where it comes from → how it is ingested → how it is cleaned → how clues are built → how the model is trained → how it is checked → how it is scored → what comes out.**
> Status: explainer · Version 0.1 · 2026-10-12

This document follows the data itself, from the moment it leaves the source system to the moment a person receives a warning. It is written so that you can understand the machinery without seeing any code, any dashboard, or any other document.

> Companion: `end-to-end-in-plain-language.md` covers the same solution from the customer's point of view (what it is, what the tables contain, how people use it). This document covers the **plumbing** — how the data actually flows and how the model is built.

---

## 1. The pipeline at a glance

```
  WHERE IT COMES FROM     GET IT IN        PREPARE IT               LEARN FROM IT          USE IT
  ─────────────────       ─────────        ──────────               ────────────           ──────
  loss events      ─┐
  daily production  ├─▶  ingest      ─▶  raw dump  ─▶  cleaned  ─▶  clues   ─▶  train  ─▶  score daily ─▶ risk table
  reference data   ─┘    (read-only)      (bronze)     (silver)     (gold)      model       every day      + alerts
  physical readings                                    │                                                   + reports
                                                       └──────────────────────────────────────────────────┘
                                                                feedback: what really happened → retrain
```

In words:

1. **Ingest** — read the raw data from the source systems, without changing anything.
2. **Store raw** — keep a faithful copy exactly as received.
3. **Clean** — standardise, fix, de-duplicate, and handle missing values honestly.
4. **Build clues** — turn each station's daily readings into numbers that describe what is happening.
5. **Build answers** — mark, for each day, whether a loss started soon afterwards.
6. **Train** — show the model many past days of clues and answers so it learns the pattern.
7. **Check** — test it on later data and measure how early and how accurately it warns.
8. **Score** — every day, apply the model to the newest data to produce a risk for each station and well.
9. **Output** — write the ranked risk, reasons, barrels and money into tables, then push alerts and reports.
10. **Learn** — record what actually happened and retrain, so it gets better.

Everything below explains each of those steps.

---

## 2. Where the data comes from (the sources)

The solution learns from a few kinds of data:

| Source | What it gives us | Role |
|---|---|---|
| **Loss-event records** | Every recorded deferment — what was lost, when, where, and (sometimes) why | The **answers** we want to predict |
| **Daily production readings** | Oil produced, target, uptime hours, wellhead pressure (THP), choke size (bean), water cut | The **clues** that move before a loss |
| **Reference data** | The list of flow stations, the wells inside them, the grouped causes, and the oil price | Context and labels |
| **Future feeds** (later) | Historian (hourly pressure/flow), maintenance work orders, power/trip logs, weather, security | Sharper, earlier clues — not in scope yet |

In plain terms: the **production readings are the smoke**, the **loss records are where the fire was reported**, and the **reference data is the map** that tells us which station and well we are talking about.

The history we start with is about **24 months** of daily data across **5 flow stations** and **71 wells/strings**.

---

## 3. Stage 1 — Getting the data in (ingestion)

Ingestion simply means **copying data out of the source systems into our own storage, on a schedule**.

How it works:

- **Today (prototype):** a small, strictly **read-only** tool pulls the tables out as files on a schedule. It is physically unable to change anything — it refuses to run anything except a "read" query, and every read is logged.
- **In production:** the same job becomes a scheduled pipeline inside the platform, writing directly into the storage layer.

Rules that always apply:

- **Read-only on the source.** We never write back to the operational systems. There is no risk of the analytics job altering live production data.
- **One copy.** All the data lands in one governed place, so the model and the reports read the *same* numbers. No exports, no stale spreadsheets, no "whose version is right?"
- **Stamped and audited.** Every batch is timestamped (when it arrived) and logged, so we can always tell what the model saw and when.
- **Stays in the client's tenant.** Data never leaves the client's environment.

> **Analogy:** ingestion is the delivery of fresh ingredients to the kitchen each morning. We take delivery; we never cook in the supplier's warehouse.

---

## 4. Stage 2 — Storing it in layers (raw → clean → ready)

The data is kept in three progressive layers, like a kitchen's pantry, prep counter, and plated dish:

| Layer | Plain name | What it holds | Rule |
|---|---|---|---|
| **Bronze** | The raw dump | Exactly what arrived from the source, untouched, plus an arrival timestamp | Never edited — a permanent, faithful record |
| **Silver** | The prep counter | The same data, but cleaned, typed, standardised and de-duplicated | Ready to be used reliably |
| **Gold** | The plated dish | The finished daily tables and the model's output, ready for reports and alerts | What everything downstream reads |

Why bother with layers? Because if something is wrong later, we can always go back to the raw copy and see exactly what arrived. And by cleaning **once** in the middle layer, every report and every model gets the same corrected data.

---

## 5. Stage 3 — Cleaning and standardising

Real data is messy. This stage is about making it trustworthy, and it happens once, in the middle layer.

- **Dates.** The production table stores dates as numbers (for example `20241001`); these are converted into proper dates.
- **De-duplicating the target.** The production target is a *station-level* number repeated on every well row. A careless sum inflates it many times over, so it is de-duplicated before any maths.
- **Missing values handled honestly.** A missing reading is **never** turned into a zero. "No reading" and "zero" mean completely different things, and confusing them would create false alarms or hide real ones.
- **Grouping the reasons.** The same problem is often written many different ways; the reasons are standardised into a small set of tidy groups. (In the real data, a large share of events carry no usable reason at all — those are left blank rather than guessed.)
- **Rejecting the impossible.** Negative volumes and other impossible values are removed.
- **Reconstructing episodes.** Consecutive days of the same problem are stitched into a single event so it can be counted as one run, not many fragments.

> **Why this matters:** everything learned later inherits the quality of this step. Clean once, benefit everywhere.

---

## 6. Stage 4 — Building the clues (feature engineering)

A **clue** (also called a "feature") is a single number that describes a station or well on a given day. The cleaning stage produces tidy daily facts; this stage turns them into the kinds of numbers a model can learn from.

We build the same table of clues for two purposes: **training** (with the answers attached) and **scoring** (for today, before we know the answers).

The clues come in a few flavours:

| Kind of clue | Plain meaning | Example |
|---|---|---|
| **Level** | Today's reading itself | Uptime today = 6 hours |
| **Change** | How much it moved versus yesterday or a week ago | Pressure fell 60 since yesterday |
| **Own-normal gap** | How far today sits from *this station's own* usual | Pressure is 40% below this station's normal |
| **Smoothed drift** | A slow-moving average that exposes a gradual slide | Uptime trending down for 5 days |
| **History** | Recent activity | 3 events in the last 7 days; 12 days since the last one |

The finished result is **one row per station per day** (and one per well per day) holding every clue for that entity on that day. Crucially, each station is compared **only to its own normal**, never to a fleet-wide average — because a station that always runs at 90% is judged differently from one that normally runs at 99%.

> **Analogy:** these clues are the "vitals" on a hospital chart — heart rate, blood pressure, temperature — but measured against *this patient's* normal, not the population's.

---

## 7. Stage 5 — Building the answers (labels)

Training needs answers as well as clues. So we add one more column: **the answer key**.

The answer we ask the model to learn is:

> **"Did a loss event start within the next 1, 3, or 7 days? Yes or no."**

One important subtlety: because some loss happens on almost every day, asking "will there be *any* loss?" is trivially always "yes" and useless. So instead we ask about the **start of a specific problem** or a **particularly bad loss day** — the thing worth warning about. That is the change we care about, not the constant background.

Now each day has both **clues** (what we knew that day) and an **answer** (what happened next) — the raw material for learning.

---

## 8. Stage 6 — Splitting the data by time

Before training, the data is split into three consecutive periods:

- **Older** data → for the model to **learn** from.
- **Middle** data → for **fine-tuning** the settings.
- **Newest** data → for the **final exam**, kept completely unseen until the end.

The rule is simple and non-negotiable: **always train on the past and test on the future — never shuffle the days**. Mixing past and future would let the model peek at answers it could not have known at the time, producing a flattering but dishonest result.

> **Analogy:** you would not let a student study with the exam paper already answered. The newest period is the sealed exam paper.

---

## 9. Stage 7 — Training the model

"Training" in plain words: **we show the model thousands of past days, each with its clues and its answer, over and over, until it can spot the pattern that links the clues to the answer.**

- The model slowly adjusts itself so that, given clues like *"pressure falling, uptime well below normal"*, it consistently lands on the right answer.
- Because real losses are rare, the rare "yes" days are given extra weight, so the model does not simply learn to always say "no".
- Crucially, during learning the model **never sees the newest period**, so the final exam is honest.

**Which model, and why:**

| Layer | What it does | Is it trained? |
|---|---|---|
| **Deviation engine** | Flags when a reading leaves its normal range — the always-on warning light | **No** — transparent rules, always runs, explains itself |
| **Onset model** | Estimates the chance of an event within the next 1/3/7 days | **Yes** — a pattern-finder (gradient-boosted trees) |
| **Survival model** | Estimates *how many days* until the event | **Yes** — a companion to the onset model |
| **Value ranking** | Turns probability into money: probability × barrels × price | **No** — simple arithmetic |

Two deliberate choices:

- We **start with the transparent rule layer and only add the learned model if it actually warns earlier** than the rule. If the simpler approach performs as well, we keep it.
- We use a **pattern-finder suited to small tables of numbers**, not a deep-learning model, because there are only a handful of stations and two years of daily history — a deep model would memorise noise and could not explain itself.

The trained model's output is a **probability from 0 to 1** — for example, *"70% chance of an event within 3 days."*

---

## 10. Stage 8 — Checking the model (evaluation)

We apply the finished model to the **unseen newest period** and measure what actually matters to an operator:

| Measure | Plain meaning |
|---|---|
| **Lead time** | On average, how many days early did the warning fire before the event? — **the headline number** |
| **How many warnings were real** | Of the flags raised, what share were genuine |
| **How many real events we caught** | Of the events that happened, what share we warned about |
| **False alarms per station per week** | Whether operators would trust it enough to act |
| **Head-to-head versus the simple rule** | If the learned model is not earlier, we keep the simple rule |

We **never** judge it on plain "accuracy", because with rare events "always say no" scores above 90% and is worthless. A model is only promoted once it demonstrably warns **earlier, without crying wolf**.

---

## 11. Stage 9 — Scoring every day (turning the model loose)

Once the model is trusted, it runs automatically **every day**:

1. The newest day's data arrives through the same ingestion path.
2. The **same clues** are built exactly as they were at training time (this consistency is essential).
3. The model scores **every station and every well**, producing a fresh probability.
4. The survival companion adds an estimated **lead time**.
5. Value ranking turns it into **money at risk**: probability × expected barrels × oil price.
6. Stations are tiered **Red / Amber / Green**.
7. The results are written to the gold output tables.

Nobody clicks "run" — it happens overnight, on a schedule, the same way every day.

---

## 12. Stage 10 — The output

The daily run writes a small set of **tables**. The main one has **one row per flow station per day**, and every row carries the probability, the reason, and the money.

| Output table | One row per… | What it holds |
|---|---|---|
| **Daily risk** (the main product) | flow station, per day (with a well-level drill-down) | risk %, tier, likely cause, estimated lead time, barrels and money at risk, top reason, owner, status |
| **Deviation detail** | station × signal × day | which reading moved, today's value, that station's normal, how far off, whether it was flagged |
| **Daily position** | flow station, per day | actual oil, target, potential, deferred, deferment %, number of events |
| **Alert log** | alert | every alert sent, to whom, the money at risk, and (later) whether the event happened and whether anyone acted |
| **Reference tables** | — | the station list, well list, cause groups, signal list, tiers, and a calendar |

A quick example of the **daily risk** row for one station:

| Flow station | Date | Risk % | Tier | Likely cause | Est. lead time | Barrels at risk | Money at risk | Top reason | Owner |
|---|---|---|---|---|---|---|---|---|---|
| Ekulama 1 | 2026-10-08 | 78% | Red | Well / artificial lift | ~2 days | 1,200 | $96,000 | Pressure 40% below its normal; uptime 6h vs 22h normal | J. Okoro |

There is **no data sitting in a table that a person reads raw** — the tables feed reports and alerts. The **full detail of every table, column by column, with examples per flow station**, is in the companion explainer.

---

## 13. Stage 11 — Delivering it (alerts and reports)

The tables are turned into things a person can act on:

- **Alerts.** When a station crosses Red or Amber, a **Teams message or email** goes to the named owner with the station, likely cause, how soon, barrels and money at risk, the reason, and a link. Repeats are suppressed so nobody is spammed.
- **Reports.** A **dashboard** shows stations ranked by money at risk, with drill-down from station to well, a chart of each reading against that station's own normal, a cause heatmap, an alert log, and an executive summary.
- **Always current.** The dashboard refreshes automatically after the daily run — Direct Lake in the platform means the reports read the freshly-written tables directly, with no separate copy step.

---

## 14. Stage 12 — Learning from what happened (feedback and retraining)

The last stage closes the loop:

- For every alert, we record what really happened: **did the event occur? Was it acted on? How early was the warning?**
- Those outcomes are used **monthly** to:
  - **re-tune the alert thresholds** (how high the risk must be before pinging someone), and
  - **retrain the model** as fresh outcomes accumulate.
- Over time this pushes warnings **earlier without making them noisier** — fewer false alarms, longer lead times.

> **Analogy:** a smoke alarm that gets its sensitivity adjusted based on real kitchen experience, not left at factory settings forever.

---

## 15. The whole journey of a single number

To see it all at once, here is the life of one reading — wellhead pressure at Ekulama 1, which has fallen to **290** while its normal is about **480**:

1. **Source** — the field system records the pressure for that well on that day.
2. **Ingestion** — the read-only job copies the day's data into the raw layer, timestamped.
3. **Cleaning** — the value is typed, de-duplicated and checked; it is present, so it is kept as 290.
4. **Clues** — the system compares it to *this station's own* normal and records a signal clue: *"pressure 40% below its normal, falling for several days."*
5. **Scoring** — the trained model reads the clue, together with uptime (6h versus a normal 22h), and outputs a probability: **0.78**.
6. **Value ranking** — probability × expected barrels × oil price = **$96,000 at risk**, tier **Red**.
7. **Output** — a row is written to the daily risk table for Ekulama 1 with the probability, reason, barrels, money, owner and status; a matching row is written to the deviation table as the evidence.
8. **Delivery** — a Teams alert lands with the owner, and the dashboard moves Ekulama 1 to the top of the ranked list.
9. **Feedback** — days later, the log records whether the loss actually happened and whether the engineer acted, and that result feeds the next monthly retrain.

---

## 16. Rules that never change (guardrails)

Whatever stage we are in, these hold:

- **Read-only on the source.** We never write back to operational systems.
- **Missing is not zero.** "No reading" is treated as missing, never as a real value of zero.
- **Per-station fairness.** Every station is judged against **its own** normal, not an average.
- **Explainable.** Every flag carries a plain reason; a flag without a reason is never shown.
- **Chronological honesty.** Train on the past, test on the future — never shuffle time.
- **Config as data.** Thresholds, horizons and alert budgets live in tables, so tuning needs no code change.
- **One copy, one governance.** The model and the reports read the same data; it all stays in the client's tenant.
- **Simple before clever.** The transparent rule runs first; the learned model must beat it to be used.

---

## 17. Glossary (plain meanings)

| Term | Plain meaning |
|---|---|
| **Ingestion** | Copying data out of source systems into our own storage |
| **Bronze / Silver / Gold** | Raw layer / cleaned layer / ready-to-use layer |
| **Feature (clue)** | One number describing a station or well on a day |
| **Label (answer)** | The thing we want the model to predict |
| **Training** | Showing the model many past days of clues and answers until it learns the pattern |
| **Onset** | The day a new loss event begins |
| **Lead time** | How many days early a warning fired |
| **Deviation** | How far a reading is from that station's own normal |
| **False alarm** | A warning where the event did not happen |
| **Survival model** | A companion model that estimates how long until the event |
| **Scoring / inference** | Applying the trained model to new data to get today's risk |
| **Value ranking** | Turning a probability into money at risk, to set priority |
| **Feedback loop** | Recording what happened and using it to retrain and re-tune |

---

*Plain-language pipeline explainer, 2026-10-12. Numbers are drawn from the current operational data and are indicative; example values are illustrative.*
