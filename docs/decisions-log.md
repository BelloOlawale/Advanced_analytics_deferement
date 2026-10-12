# Decisions Log

> Deferment Early-Warning Solution · Advanced Analytics & AI (Part 1, Project 1)
> Purpose: record the key decisions and their rationale so the reasoning is not lost.
> Format: each entry = decision, why, status, and where it is documented.

---

### D-01 — Focus the solution on detecting risk *earlier*
**Decision:** The workstream answers one question: *"How do we detect the risk earlier?"* — catch deferment before it occurs and raise an early-warning signal.
**Why:** This is the stated deliverable; root-cause explanation is limited by poor cause codes and is enabling work, not the aim.
**Status:** Agreed.
**Docs:** `prd-deferment-early-warning.md` §2, `NOTES.md`.

### D-02 — Predict onset/severity/change, not "deferment yes/no"
**Decision:** Because deferment occurs on ~95% of station-days, predict the **onset of a specific event**, a **large-loss day**, or a **regime shift** — not whether a deferment will happen.
**Why:** "Always yes" is 95% accurate and useless; the value is in the change.
**Status:** Agreed.
**Docs:** `early-warning-patterns.md` §1, `early-warning-model-design.md` §1–2.

### D-03 — Use a layered system (deviation → model → value)
**Decision:** Build an always-on **deviation engine** first, then a **supervised onset model** with a **survival** companion, then **value ranking**. Add the learned model only if it warns earlier than the rule.
**Why:** Transparent, works with current data, and avoids over-engineering on a small dataset.
**Status:** Agreed.
**Docs:** `early-warning-model-design.md` §3.

### D-04 — Model choice: gradient-boosted trees, not deep learning
**Decision:** Primary model = gradient-boosted trees (LightGBM/XGBoost) plus a survival/time-to-event model.
**Why:** Small tabular dataset (5 stations, ~2 years, daily), rare events, and the need for explainable reasons. Deep sequence models need more data and higher frequency.
**Status:** Agreed; revisit with hourly historian data.
**Docs:** `early-warning-model-design.md` §4.

### D-05 — Treat the problem as time series but deliver event prediction, not forecasting
**Decision:** The solution is built on time-series data, but the core is **event prediction + anomaly/survival analysis**, with only a small forecasting element (value at risk). It is not a classic value-forecasting model.
**Why:** Forecasting the loss series is accurate but late; the question is "earlier", not "how much next month".
**Status:** Agreed.
**Docs:** `model-framing-time-series-vs-forecasting.md`, `how-the-model-works.md` §6, `prd-deferment-early-warning.md` §12.4.

### D-06 — Output shape: probability + tier + reasons + value (not binary)
**Decision:** The raw output is a rich record — risk probability, tier, reason(s), expected barrels and value — from which a binary "alert fired" flag is derived.
**Why:** Enables ranking by money and explanation to operators; a binary alone would be untrustworthy and unrankable.
**Status:** Agreed.
**Docs:** `prd-deferment-early-warning.md` §12.3.

### D-07 — Serving path: gold Delta tables → DirectLake semantic model → Power BI + Data Activator
**Decision:** Write findings as Delta tables in the gold layer, model them with a DirectLake semantic model, and consume via Power BI reports and Data Activator alerts.
**Why:** Native Fabric path; fast, low-copy, governed; supports row-level security and auto-refresh.
**Status:** Proposed.
**Docs:** `early-warning-architecture.md` §8, `prd-deferment-early-warning.md` §12.6.

### D-08 — Per-entity baselines and normalised cross-station comparison
**Decision:** Every station and well gets its **own** baseline; stations are compared only after normalisation (share of potential, per well, per thousand barrels).
**Why:** Field-wide thresholds are unfair; a station that normally runs at 90% uptime dropping is a bigger warning than one that always sits at 90%.
**Status:** Agreed.
**Docs:** `flow-station-early-risk-detection.md`, `prd-deferment-early-warning.md` §7–8.

### D-09 — Rank and tier by money at stake
**Decision:** `Priority = risk probability × expected barrels × oil price`, tiered Red/Amber/Green.
**Why:** Operators need priorities, not probabilities alone.
**Status:** Agreed.
**Docs:** `early-warning-model-design.md` §3 (L3).

### D-10 — Cause-code correction is an enabler, not a blocker for early warning
**Decision:** Proceed with precursor-based early warning despite 86% unusable cause codes; pursue the taxonomy fix in parallel.
**Why:** Early warning can be built on process deviation without reliable cause codes; cause-specific modelling waits for the fix.
**Status:** Agreed.
**Docs:** `data-quality-findings.md` §4, `prd-deferment-early-warning.md` §3 (G6), §14.

### D-11 — Deliver in vertical slices
**Decision:** Every work item delivers a thin end-to-end increment (data → feature → score → surface), independently demoable.
**Why:** Faster proof of value; the lead-time number can be produced early.
**Status:** Agreed.
**Docs:** `prd-deferment-early-warning.md` §13, `Issues/`.

### D-12 — WBS kept standalone and build-only
**Decision:** The WBS does not reference environment/access steps or work-item identifiers; it is readable on its own and describes only the build.
**Why:** It is shared with a wider audience who need the plan without internal references.
**Status:** Agreed.
**Docs:** `wbs-deferment-early-warning.md`.

### D-13 — Data handling rulings from the real extract
**Decision:** De-duplicate the station-level `target_oil` before any target maths; treat `gross` as a measure distinct from `oil + water`; treat missing pressure/choke values as missing, never zero; reconstruct event episodes from consecutive days.
**Why:** Naive handling of each of these produces materially wrong results.
**Status:** Agreed.
**Docs:** `data-quality-findings.md` §5.

### D-14 — Feedback loop drives tuning and retraining
**Decision:** Capture outcomes for every alert (did the event occur, was it acted on, how early) and use them to re-tune thresholds monthly and retrain.
**Why:** Without this, warnings never get earlier or cleaner.
**Status:** Agreed.
**Docs:** `early-warning-model-design.md` §3, `prd-deferment-early-warning.md` §7 (FR12).

---

## Open decisions (not yet settled)

| Ref | Question | Impact |
|---|---|---|
| O-01 | Scope: OML 24 only, or include OML 147 / OML 152? | Coverage, effort, RLS design |
| O-02 | Who owns the cause-taxonomy correction, and when? | Enables cause-specific modelling |
| O-03 | Historian availability and frequency | Feasibility of real-time detection |
| O-04 | Horizons H (1 / 3 / 7 days) | Set after lead-time measurement |
| O-05 | Alert budget per station per week | Threshold and tier tuning |
| O-06 | Provision of a least-privilege data identity | Operating the solution safely |

---

*Decisions log, 2026-10-08. Add new entries as decisions are made; move settled items out of the open list.*
