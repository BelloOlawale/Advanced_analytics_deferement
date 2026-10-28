# The Alert Log & Feedback Loop — How Alerts Work and How They Improve

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Question answered here: **How does the alert logic work, who records whether an alert was false or acted on, and how is that record used?**
> Status: design · Version 0.1 · 2026-10-12
> Companion: `technology-stack-and-fabric-implementation.md` (how this is built in Fabric), `automation-and-human-in-the-loop.md` (who does what, and platform alternatives), `pipeline-in-plain-language.md` (the surrounding pipeline).

---

## 1. Why this matters

A warning that fires and is never reviewed is worse than no warning: it teaches nothing, burns the operator's trust, and cannot improve. The **alert log** is where every warning is recorded, judged, and turned into learning. It is the memory of the system and the engine of its improvement.

There are **two different questions** an alert has to answer, and they are answered by **different people**:

| Question | Plain meaning | Answered by |
|---|---|---|
| **Was it right?** | Did the predicted event actually happen, and how early were we? | **The system** (automatically) |
| **Was it useful?** | Did someone see it, did they act, and was it real or noise? | **The person who received it** (in one click) |

Confusing the two is the classic mistake. A model can be *correct* about an event that nobody acted on, or *wrong* about an event that a precautionary check prevented. The alert log keeps both facts separate so each can be improved.

---

## 2. The alert lifecycle

Every alert moves through a small set of states:

```
  New ──▶ Delivered ──▶ Acknowledged ──▶ Actioned ──┐
   │          │              │               │       │
   │          │              └──▶ Dismissed ─┘       │
   │          └──(delivery failed)──▶ Retry          │
   └──▶ Suppressed (duplicate while the condition persists)
                                                    ▼
                                       Outcome confirmed (auto)
                                                    │
                                                    ▼
                                                 Closed
```

- **New** — the rule fired; the row exists.
- **Delivered** — the message reached the owner (or **Retry** on failure).
- **Suppressed** — a repeat while the same condition is still active; counted, not re-sent.
- **Acknowledged** — the owner saw it.
- **Actioned** / **Dismissed** — the owner acted, or judged it noise/not applicable.
- **Outcome confirmed** — the system later determines whether the event actually happened and how early.
- **Closed** — the alert is resolved and included in the metrics.

---

## 3. How the alert logic works

The logic runs on top of the daily risk table (one row per station per day, with a well-level drill-down). Nothing here is hidden: the rules are **config-as-data**, so business users can tune them without a code release.

**Step 1 — Read the risks.** Every day after scoring, take the day's rows from the daily risk table (risk probability, tier, reasons, expected barrels, expected value, likely cause, owner).

**Step 2 — Apply the fire rule.** A rule decides which rows deserve a message. A typical rule set:

- Fire **Red** when `risk_prob ≥ red_threshold` **or** `exp_usd ≥ red_value_threshold`.
- Fire **Amber** when `risk_prob ≥ amber_threshold` **or** `exp_usd ≥ amber_value_threshold`.
- Do **not** fire Green.
- Thresholds are per station class if needed (a big station justifies a lower percentage).

**Step 3 — Fire on change, not every day.** An alert only fires when the entity **moves into** Red or Amber from a calmer state — not once per day while it stays there. This is the single most important anti-fatigue measure.

**Step 4 — Suppress and rate-limit.**
- **Duplicate suppression:** while a station/cause is still in the same state, further days are counted as `suppressed_count` and not re-sent.
- **Cooldown:** if the same entity fires again within a short window, hold it.
- **Alert budget:** cap messages per station per week (for example, no more than 5). When the cap is hit, the additional risks still appear on the dashboard but are not pushed.

**Step 5 — Route to the owner.** Each station maps to a named engineer (an owner map, itself a small table). Third-party or safety-related causes route to their own owners.

**Step 6 — Send with context.** The message always carries: which station/well, tier, likely cause, how soon, expected barrels and money at risk, the plain reason, and a dashboard link. **No reason, no alert.**

**Step 7 — Write the alert log row** (Section 4) and start the outcome clock.

> In Fabric these rules run in **Data Activator** (the platform's built-in alerting), reading the risk data through a Power BI visual or an event stream. The rule, thresholds and owner map are all configuration. See the companion technology document for the mechanics.

---

## 4. The alert log — what a row contains

Two linked tables. Both live in the gold layer as Delta tables.

### Table 1 — `alert` (one row per alert raised)

| Column | Meaning |
|---|---|
| `alert_id` | Unique id for the alert |
| `fired_at` | When the rule fired (timestamp) |
| `entity_type` | Station or well |
| `station_id` / `string` | Which entity and where |
| `tier` | Red or Amber |
| `risk_prob` | The probability at the moment of firing |
| `horizon_days` | 1 / 3 / 7 — the window the risk refers to |
| `cause_group` | Likely cause group |
| `top_reasons` | Plain-language reason(s) |
| `exp_deferred_bbl` | Expected barrels at risk |
| `exp_usd` | Money at risk |
| `model_version` | Which model produced it (auditability) |
| `ruleset_version` | Which thresholds/rule were in force |
| `owner_id` | Who it was routed to |
| `delivery_channel` | Teams / email |
| `delivery_status` | Sent / failed / retried |
| `status` | Lifecycle state (Section 2) |
| `dedup_key` | Entity + cause, used to suppress repeats |
| `suppressed_count` | How many repeat days were suppressed for this situation |

### Table 2 — `alert_outcome` (one row per alert, keyed by `alert_id`)

| Column | Meaning | Set by |
|---|---|---|
| `event_occurred` | Did a matching event actually happen? | **System** |
| `event_date` | The date the event started | **System** |
| `actual_lead_days` | Days between the alert and the event | **System** |
| `detection_type` | How it was confirmed: coded onset / large-loss day / not confirmed | **System** |
| `acknowledged_at` / `acknowledged_by` | Who saw it, and when | **Recipient** |
| `disposition` | Actioned / Investigating / False / Known-planned / No action | **Recipient** |
| `false_reason` | Why it was noise (data issue / threshold too tight / already known / other) | **Recipient + analyst** |
| `action_note` | What was actually done | **Recipient** |
| `reviewed_by` / `review_note` | Weekly reconciliation note | **Analyst / PE** |
| `resolved_at` | When the alert was closed | System or analyst |
| `updated_at` | Last change | All |

**No alert is ever silently dropped:** every alert row always has an outcome slot, even if the slot is empty and shows as "open".

---

## 5. Who records what — the three capture arms

This is the part most alerting systems get wrong. We use **three complementary capture paths**, so the feedback does not depend on any single person remembering to fill something in.

### Arm A — The system (automatic, no human)

**It records: did the event actually happen, and how early?**

A scheduled job, running a few days after each alert, looks forward in the loss history and asks:

- Did a coded event for the likely cause group **start** within the horizon after the alert? → `event_occurred = true`, `detection_type = coded onset`.
- If cause codes are unusable (a large share of them are), did the station instead register a **large loss day** — deferred volume above its own high threshold following quiet days? → `event_occurred = true`, `detection_type = large-loss day`.
- If neither happened within a grace period → `event_occurred = false` (candidate false alarm).

It then computes `event_date` and `actual_lead_days`. This arm needs **no human at all** and produces the correctness metrics (precision, lead time, recall). It is deliberately conservative: because the loss log itself is incomplete, "not confirmed" is distinguished from "confirmed false".

### Arm B — The recipient (human, one click)

**It records: did I see it, and did I act?**

The alert is delivered with **action buttons inside the message the person already uses** (a Teams card). One click records the response:

- ✅ **Acknowledge** — "I've seen it"
- 🔧 **Acted** — "I've taken action" (optional short note)
- 🔍 **Investigating**
- ✖ **Not real** — with a quick reason from a dropdown (false positive / under maintenance / already known / data issue / other)
- ⏰ **Snooze** — hide for a set period

The button press is captured by an automation flow and written straight back into `alert_outcome`. This is the key adoption decision: capture happens **in the notification**, not in a separate portal, so it costs the operator seconds.

*Fallbacks:* the message can instead link to a one-click form, or a lightweight app can be used for richer notes. The principle is the same — the person who received the alert is the one who records the human judgement, at the moment of contact.

### Arm C — The analyst / PE (human, weekly)

**It records: the curated truth.**

Once a week, an analyst reviews the previous week's alerts in one view:

- Corrects automatic labels where the event log is ambiguous (for example, confirming a "large-loss day" as the real event).
- Fills gaps where no one acknowledged an alert (the "no alert is silently dropped" guard).
- Adds a root-cause note and tags systematic false alarms (for example, "this cluster was a planned shutdown the model didn't know about").
- Signs off the week so the metrics are trustworthy.

This arm is the quality control that keeps the automatic and operator inputs honest.

### Summary — field ownership

| Question | Field(s) | Owner | Timing | Mechanism | Reliability |
|---|---|---|---|---|---|
| Did it happen? | `event_occurred`, `event_date`, `actual_lead_days`, `detection_type` | **System** | days after the alert | scheduled comparison to the loss history | high, but limited by loss-log quality |
| Did anyone see it? | `acknowledged_at`, `acknowledged_by`, `status` | **Recipient** | at/after delivery | one click in the Teams card | high once adopted |
| Did anyone act / was it noise? | `disposition`, `action_note`, `false_reason` | **Recipient** | at/after delivery | one click + short dropdown | human judgement |
| Is the record trustworthy? | `reviewed_by`, `review_note`, `resolved_at` | **Analyst / PE** | weekly | reconciliation view | high (curated) |

---

## 6. How the write-back works (the loop in Fabric)

```
 daily scoring ─▶ risk table (Delta, gold)
        │
        ▼
 Data Activator rule (tier / value thresholds, on change)
        │  fires
        ▼
 Teams / email alert ──▶ (recipient clicks a button)
        │  (write alert row)        │
        ▼                           ▼
   alert log (Delta)  ◀──── Power Automate / app  (writes outcome)
        ▲                           ▲
        │                           │
 outcome job (System, Arm A) ───────┘
        │
        ▼
 weekly analyst review (Arm C) ─▶ corrected outcomes
        │
        ▼
 monthly re-tune thresholds + retrain model ──▶ better alerts tomorrow
```

The alert log is an ordinary Delta table in the gold layer, so the same engine that scores risks can read the outcomes; no separate database is required.

---

## 7. How the alert log is leveraged

The log is not an audit trail that sits idle — it is the control panel for improving the system. It drives eight things.

| # | Leverage | What it uses | What it changes |
|---|---|---|---|
| 1 | **Prove "earlier"** | median `actual_lead_days` | the headline KPI — how many days of warning we give |
| 2 | **Measure correctness** | precision (real alerts ÷ all alerts) and recall (alerted events ÷ all events) | model and threshold quality |
| 3 | **Control noise** | false-alarm rate per station per week | thresholds, suppression, cooldowns |
| 4 | **Enforce the alert budget** | alerts/station/week vs the agreed cap | tier cut-offs, budget config |
| 5 | **Fix systemic false alarms** | `false_reason` patterns (e.g. planned shutdowns) | new suppression rules and features (e.g. a "planned maintenance" flag) |
| 6 | **Find blind spots** | events with **no** alert (missed detections) | new features, new signals, model retraining |
| 7 | **Track adoption** | % acknowledged and % actioned | owner routing, messaging, training, escalation |
| 8 | **Quantify value** | sum of `exp_usd` for confirmed-and-acted alerts | the business case / ROI reporting, and prioritisation of the next asset |

**The monthly tuning loop.** On a monthly cadence the outcomes are rolled up and the thresholds are re-tuned to hit two targets at once: **maximise lead time** while **staying inside the alert budget and false-alarm ceiling**. Because the thresholds live in configuration tables, this is a data change, not a code redeploy.

**The retraining loop.** The confirmed outcomes also feed the model's improvement in three ways:

- **New labels where cause codes are weak** — a curated "this was the event that mattered" record lets the model learn from events the coded log would have missed.
- **New features** — recurring `false_reason` patterns (planned shutdowns, third-party outages, weather) become explanatory inputs so the model stops mis-flagging them.
- **Honest backtesting** — as outcomes accumulate, the model is re-validated on the newest period before any promotion, and only kept if it beats the incumbent.

**What "good" looks like**, expressed through the log:

> *"For this cause group, we warned a median of 5 days ahead, precision was 60% at 4 alerts per station per week, 85% of Red alerts were acknowledged and 70% actioned, and we flagged $X of value in losses early."*

---

## 8. Edge cases and design rules

- **Weak cause codes.** Because many events carry no usable reason, "confirmed" events are detected by EITHER a coded onset OR a large-loss day, and "not confirmed" is kept distinct from "confirmed false".
- **Multi-entity alerts.** A station-level alert can cover several wells; the log keeps the station as the alerting entity and the well as drill-down context so one warning is not counted several times.
- **Overlapping causes.** One alert can be matched to more than one possible cause; the log records the matched cause and the confidence so precision is not overstated.
- **Long-running problems.** Suppression means one persistent problem yields one alert (plus a suppressed count), not a daily flood.
- **Planned events.** A known maintenance calendar (once available) suppresses alerts for genuinely scheduled work, so they are not counted as false alarms.
- **No outcome yet.** Fresh alerts sit in an "open" state; they are excluded from precision/lead-time metrics until the grace period passes.
- **Auditability.** `model_version` and `ruleset_version` on every alert mean any decision can be reconstructed exactly.

**Governing principles**

1. **Two questions, two owners** — machine judges correctness, human judges usefulness.
2. **One-click capture** — feedback happens inside the notification, never in a separate chore.
3. **No silent drops** — every alert always has an outcome slot.
4. **Fire on change** — repeated conditions are suppressed, not repeated.
5. **Config-as-data** — thresholds, budgets and owner maps are tables, not code.
6. **Curated truth** — a weekly human review keeps the automatic and operator inputs trustworthy.

---

*Design note, 2026-10-12. Thresholds, budgets and capture mechanics to be confirmed with operations during Discovery.*
