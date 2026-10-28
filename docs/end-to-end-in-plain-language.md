# The Solution End to End — In Plain Language

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Audience: anyone — business, operations, engineering — with **no data-science background and no need to read any other document**.
> Purpose: explain, from scratch, how the model is built, what it produces, and how the customer uses it.
> Status: explainer · Version 0.1 · 2026-10-12

This document is deliberately self-contained. Every idea is explained in ordinary words. If you have never seen the other project documents, you can read only this and still understand the whole solution.

---

## 1. The one-sentence version

We take two years of the plant's daily production history, learn what "normal" looks like for **each flow station**, watch the physical signals for a slow drift away from that normal, learn what the days *before* a loss usually look like, then every morning produce a **ranked to-do list of which flow stations are about to lose oil, why, and how much money is at stake** — pushed to the right engineer before the barrels are gone.

Think of it like a **smoke alarm for lost production** instead of a fire report written after the fire.

---

## 2. Why this exists

Today, when oil is "deferred" (lost production), it shows up in a log or a monthly report **after** it happened. The business learns from the rear-view mirror. By the time anyone sees *"Well 12 deferred 1,200 barrels,"* the barrels are already gone.

So the goal is **not** to predict *that* deferment will happen — deferment happens somewhere almost every day, so predicting "yes" would nearly always be right and completely useless. The goal is to catch **the start of a new problem at a specific flow station, days before it is recorded**, and to tell someone in time to act.

Two facts from the real data shape everything below:

- Loss events are **highly persistent** — yesterday's loss is a good guess for today's, but that guess always arrives **too late**.
- For many problems, the **physical signal moves a week or more before** the loss is written down. That gap is exactly where early warning lives.

---

## 3. How we build the model (step by step)

### Step 1 — Gather the history
We pull about **24 months of daily data**:

- how much each flow station **actually produced**;
- what it was **supposed to produce** (its target);
- every recorded **loss event** (what, when, where, and sometimes why);
- the **physical readings** each station produces — pressure, choke size, uptime hours, water cut, and so on.

Without history there is nothing to learn from. The physical readings are the leading clues; the loss events are the answers.

### Step 2 — Clean it up
Real data is messy, and everything later depends on this step:

- The same problem is often written five different ways — we standardise the reasons into tidy groups.
- Some loss events have **no reason recorded at all** (a large share, in fact) — we leave those blank rather than guessing.
- Some numbers are duplicated (the production target is repeated on every well row, so a careless sum inflates it many times over) — we de-duplicate before any maths.
- Some readings are simply missing — and **a missing reading is never treated as a zero**, because "no reading" and "zero" mean completely different things.
- Impossible values (like negative volumes) are rejected.

### Step 3 — Learn each station's own "normal"
This is the heart of it. **Awoba does not look like Ekulama, and it should not be judged against Ekulama.** So we teach the system what a *normal day at each individual station* looks like — its normal pressure, its normal uptime, its normal production, its normal water level — and how those normally move through the week and across the year.

> **Analogy:** a resting heart rate of 55 is fine for a runner and alarming for someone else. You compare each person to *their own* normal, not to a generic number. A station that usually runs at 90% uptime dropping is a bigger warning than a station that always sits at 90%.

### Step 4 — Build the "deviation engine" (the warning light)
Every day, the system compares each station's current readings to its own normal and asks: **how far off is this, and in which direction?** It uses a few complementary techniques so it can catch **slow drifts** (a pressure gently sliding down over a week) as well as **sudden jolts**.

This layer needs **no fancy AI at all** — it is transparent rules, and it always runs. Its output is simple and explainable by construction: *"This station's pressure is 40% below where it normally sits — flagged."*

### Step 5 — Teach the model what a run-up looks like (the real "prediction" model)
Now we add the learned part. We walk back through history to every time a loss happened and line up the days **before** it. What did pressure do? What did uptime do? How fast were they moving? A pattern-finder (a type of model called **gradient-boosted trees**, which is good at small, messy tables of numbers) learns the **fingerprint of the approach to a loss**.

Then, given today's readings, it estimates a **probability**: *"There is a 78% chance a new problem starts at this station within the next 3 days."*

A companion model answers *"how much time do we probably have?"* — so instead of a probability alone you also get *"roughly 2–3 days."*

We deliberately keep this simple. With only a handful of stations and two years of **daily** data, a deep-learning model would just memorise noise and could not explain itself. The boring, explainable model wins here. (We would revisit richer models only with hourly readings and more history.)

### Step 6 — Put a price on it (value ranking)
A 78% chance at a tiny station matters less than a 40% chance at a big one. So we multiply:

> **probability × expected barrels × oil price = money at risk**

That is what turns a probability into a **priority**. Stations are then tiered with a simple traffic light:

- **Red** — act now
- **Amber** — watch closely
- **Green** — fine

### Step 7 — Prove it honestly
We test the model the way reality works: **train on older history, test on newer history** — never by shuffling the data, which would let the model peek at the future and cheat. The two numbers we care about most are:

- **How many days early** does it warn us? (the headline)
- **How many false alarms per station per week?** (a system that cries wolf gets ignored, so this is measured and capped)

We never use plain "accuracy", because with rare events "always say no" would score above 90% and be useless.

**The loop closes here:** every alert is later checked against what actually happened — did the event occur, was it acted on, how early was it? Those outcomes feed back monthly to re-tune the alert thresholds and retrain the model, so warnings get **earlier without getting noisier**.

---

## 4. What comes out — yes, it's tables

The output is **not a single yes/no flag**. It is a **rich record** — probability, reason, money — from which a simple alert is derived. At the centre are a few **daily tables**, all keyed by date, and the most important one has **one row per flow station per day**.

> The example rows in the tables below are **illustrative** — they show the *shape and content* of the output using the real station names. Actual values will come from the live model.

### Table A — The Daily Risk Table (the main product)

**One row per flow station, per day.** This is the ranked to-do list.

| Flow station | Date | Risk % (next 3 days) | Tier | Likely cause | Est. lead time | Barrels at risk | Money at risk | Top reason | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Ekulama 1 | 2026-10-08 | 78% | **Red** | Well / artificial lift | ~2 days | 1,200 | $96,000 | Pressure 40% below its normal; uptime 6h vs 22h normal | J. Okoro | Sent |
| EFE (OML 152) | 2026-10-08 | 61% | **Amber** | Flowline / export | ~4 days | 800 | $64,000 | Choke setting falling for 5 straight days | A. Musa | Sent |
| Awoba | 2026-10-08 | 44% | Amber | Facility / utilities | ~5 days | 350 | $28,000 | Water cut creeping above own baseline | R. Eze | Watching |
| Ekulama 2 | 2026-10-08 | 22% | Green | — | — | 90 | $7,200 | Slightly low uptime — within normal range | — | No alert |
| OML 147 | 2026-10-08 | 12% | Green | — | — | 40 | $3,200 | All signals near normal | — | No alert |

Read it like a triage board: **Red = act now, Amber = watch closely, Green = fine.** Sort it by money and you instantly know where to send the engineer first.

**What each column means:**

| Column | Plain meaning |
|---|---|
| **Flow station** | Which facility this row is about (one row per station per day) |
| **Date** | The day the assessment was made |
| **Risk %** | The model's confidence that a **new** problem starts within the chosen window (here, 3 days) |
| **Tier** | The simple traffic-light version of the risk — Red / Amber / Green |
| **Likely cause** | Best guess at the kind of failure, even though the paper trail is often blank |
| **Est. lead time** | Roughly how many days until it bites |
| **Barrels at risk** | Expected volume that could be lost |
| **Money at risk** | The dollar value of that volume |
| **Top reason** | The plain-English *why* — no reason, no alert |
| **Owner** | The named person responsible for that station |
| **Status** | Sent / watching / acknowledged / acted / resolved |

### Table B — The Deviation Table (the "what moved" detail)

**One row per flow station, per signal, per day.** This is the evidence behind the "Top reason" column. Every station is compared only to **its own** normal, so the comparison is always fair.

| Flow station | Date | Signal | Today's value | Station's normal | How far off | Flagged? |
|---|---|---|---|---|---|---|
| Ekulama 1 | 2026-10-08 | Pressure (THP) | 290 | 480 | −40% | Yes |
| Ekulama 1 | 2026-10-08 | Uptime | 6 hrs | 22 hrs | −73% | Yes |
| Ekulama 1 | 2026-10-08 | Water cut | 18% | 16% | +2 pts | No |
| Awoba | 2026-10-08 | Water cut | 31% | 24% | +7 pts | Yes |

**What each column means:**

| Column | Plain meaning |
|---|---|
| **Signal** | Which reading is being examined (pressure, uptime, choke, water cut, …) |
| **Today's value** | What the reading is right now |
| **Station's normal** | What that reading usually is *for this station* |
| **How far off** | The size and direction of the gap from its normal |
| **Flagged?** | Whether that gap crossed the station's own warning line |

### Table C — The Daily Position Table (the context)

**One row per flow station, per day.** The plain production scoreboard that everything else hangs off.

| Flow station | Date | Actual oil | Target | Potential (what it could make) | Deferred (lost) | Deferment % | Loss events |
|---|---|---|---|---|---|---|---|
| Ekulama 1 | 2026-10-08 | 18,400 bbl | 20,000 | 20,000 | 1,600 | 8.0% | 3 |
| EFE (OML 152) | 2026-10-08 | 5,900 bbl | 8,000 | 8,000 | 2,100 | 26.2% | 6 |
| Awoba | 2026-10-08 | 24,600 bbl | 26,000 | 26,000 | 1,400 | 5.4% | 2 |
| Ekulama 2 | 2026-10-08 | 13,200 bbl | 14,500 | 14,500 | 1,300 | 9.0% | 4 |
| OML 147 | 2026-10-08 | 9,100 bbl | 10,600 | 10,600 | 1,500 | 14.0% | 5 |

**Deferment %** is the fair way to compare stations of different sizes — it is the share of what the station *could* have made that it actually lost. It lets a small station and a large station be judged on the same scale.

### Table D — The Alert Log

**One row per alert ever sent.** This is how the team sees whether the system is improving over time.

| Alert ID | Date | Flow station | Tier | Reason sent | Money at risk | Sent to | Did the event happen? | Acted on? | Days early |
|---|---|---|---|---|---|---|---|---|---|
| A-1042 | 2026-10-06 | Ekulama 1 | Red | Pressure + uptime collapse | $88,000 | J. Okoro | Yes | Yes | 3 |
| A-1043 | 2026-10-07 | Awoba | Amber | Water cut above baseline | $21,000 | R. Eze | No | Yes (checked) | — (false alarm) |

This is the **learning loop**. Every alert is checked against reality. That is how false alarms get pushed down and lead time gets pushed up over time.

### Supporting reference tables
Alongside the four tables above there are small reference ("dictionary") tables that give the labels and hierarchies the reports rely on: the list of **flow stations**, the list of **wells/strings** (asset → station → well), the grouped **causes**, the **signals**, the **tiers**, and a **calendar**. These are not read on their own; they make the main tables sortable, drillable and filterable.

### So, per flow station, what is in the tables?
Put simply: for **each flow station, each day**, the output is:

- a **risk percentage** and a **traffic-light tier**;
- the **likely cause** and the **estimated lead time**;
- the **barrels and money at risk**;
- the **plain-English reason**;
- the **named owner** and the **status** of any alert;
- plus supporting rows showing **exactly which signals moved** (and by how much versus that station's own normal), and how the station's **daily production compared to its target**.

---

## 5. How the customer actually uses it

**Overnight, automatically** — new data flows in, the stations get scored, and the risk table is refreshed. Nobody clicks "run."

**Early morning** — a station crosses the Red or Amber line, and a **Microsoft Teams message or email** lands with the owner. In effect it says:

> *"Ekulama 1 — Red, likely well/lift issue, roughly 2 days out, 1,200 barrels / $96,000 at risk, pressure is 40% below normal. Open the dashboard."*

Repeat alerts are suppressed, so nobody is spammed while the same condition persists.

**Morning stand-up** — the operations and asset managers open a **dashboard** (in a browser or on a phone) and see the stations **ranked by money at risk**. They work down the list. They can click a station, drill into the specific well, and see a chart of the reading **against that station's own normal**, so the "why" is obvious. A reason is always present — a flag with no reason is not trusted, so it is not shown.

**Through the day** — an engineer inspects, adjusts, or dispatches to the well in question **before** the loss occurs. Because every alert carries a dollar figure, competing priorities resolve themselves.

**Weekly / monthly** — leadership sees the bigger picture: how much deferment there was, how much value was caught early, how early the warnings came, and what share were acted on. Meanwhile, in the background, the system quietly re-checks its own accuracy against what really happened and refreshes itself.

### Who sees what

| Person | What they get |
|---|---|
| **Field / operations engineer** | The early-morning alert and the well-level detail |
| **Asset manager** | The ranked list of stations by money at risk, and station-to-station comparison |
| **Executive** | The headline numbers, total value at risk, and trends |
| **Data / IT team** | The only group that looks "under the hood"; after go-live they mostly just confirm the overnight refresh ran |

Everyone except the data/IT team experiences the solution as **a report and a notification** — never by reading a table directly in the platform.

---

## 6. Putting it all together

- **Build:** collect two years of daily history → clean it → learn each station's own normal → flag deviations from that normal → learn the pattern of the days before a loss → attach money → test how early and how accurately it warns.
- **Output:** yes, it is tables. Chiefly one row **per flow station per day** holding its risk percentage, traffic-light tier, likely cause, expected lead time, barrels and dollars at risk, plain reason, and owner — supported by a "what signal moved" table, a daily production scoreboard, and an alert history.
- **Use:** the customer never opens the model. They get a push alert in the morning and a ranked dashboard they can drill into — so instead of reading about lost oil after the fact, they walk in each day already knowing **which station is about to hurt, why, and what it is worth.**

---

## 7. Glossary (plain meanings)

| Term | Plain meaning |
|---|---|
| **Deferment** | Oil production that was lost (could have been produced but wasn't) |
| **Flow station** | A facility that gathers and processes production from several wells |
| **Well / string** | An individual producing well (or production path) inside a station |
| **Potential** | What a station could have produced if nothing went wrong |
| **Deferment %** | Lost production as a share of potential — the fair way to compare stations |
| **Normal / baseline** | What is usual for *that* station, learned from its own history |
| **Deviation** | How far a reading is from that station's normal, and which way |
| **Lead time** | How many days early a warning fired before the event |
| **False alarm** | A warning where the event did not actually happen |
| **Tier** | Red / Amber / Green traffic light |
| **Owner** | The named person responsible for acting on an alert |

---

## 8. Notes and caveats

- The example rows in Section 4 are **illustrative**. They are drawn from the real station names to make the shape concrete, not to report actual findings.
- Some inputs are still incomplete in practice — notably that a large share of historical loss events carry **no usable cause code**, and pressure/choke readings are missing on a meaningful fraction of days. The design deliberately tolerates both: the deviation layer works without reliable cause codes, and missing readings are never faked as zeros.
- All thresholds, time windows (1 / 3 / 7 days) and alert budgets are **proposals**, to be confirmed with operations during Discovery.

---

*Plain-language end-to-end explainer, 2026-10-12. Self-contained by design; no prior reading required.*
