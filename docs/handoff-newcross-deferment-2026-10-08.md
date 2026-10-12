# Handoff — NewCross EP Deferment Analytics

**Date:** 2026-10-08
**Workspace:** `C:/Users/OlawaleBello/workspace/Advanced_analytics_deferement`
**Repo:** `https://github.com/BelloOlawale/Advanced_analytics_deferement.git` (branch `main`, single commit)
**Purpose of this doc:** let a fresh agent continue work without re-reading the whole conversation.

> No arguments were passed to this handoff. Likely next focus (inferred): (a) give the agent access to real data, and/or (b) build the data contract / extraction-query pack. See "Where we stopped" below.

---

## 1. Mission in one paragraph

Wragby is proposing an **Advanced Analytics & AI** engagement to **NewCross Exploration & Production (NewCross EP)** for **OML 24** (Awoba, Awoba North West, Ekulama; western Niger Delta; >130,000 bbl/day; target 100,000 bopd), on **Microsoft Fabric**. The active thread is **Part 1, Project 1 — Deferment Root-Cause & Production Loss Prediction**, specifically the "trend and pattern detection for recurring loss drivers" and "early-warning flags for deferment risk" deliverables. This session narrowed the problem to **detecting deferment risk earlier at flow-station level, and comparing risk across flow stations**.

Full proposal context: see `context.md` in the workspace.

## 2. What happened this session

1. User supplied a **raw list of ~60 production-loss drivers** (free-text, with duplicates/spelling errors, plus `NULL` and `Mismatch`).
2. Agent explained, in plain language, (A) how to detect trends/patterns for recurring loss drivers and (B) how early-warning flags work.
3. Agent produced a **cause-taxonomy normalisation** (grouping the ~60 raw drivers into ~9 canonical L1 categories) and a Pareto / FTE-decomposition / recurrence / SPC / cascade-mining methodology.
4. User asked to narrow to: **"how to detect risk earlier across different flow stations."**
5. Agent defined a per-station process: give each station its own baseline → watch leading indicators → normalise before cross-station comparison → score daily → tier Red/Amber/Green → route → feedback loop.
6. User asked to document it + state **what historical data is needed**.
7. Agent **wrote a new artifact** (see §3).
8. User asked **"can you see the data?"** → Agent verified there is **no real data available** (see §4).

## 3. Artifacts (reference, do NOT duplicate)

> All documents now live in **`docs/`** (reorganised 2026-10-08). Paths below are relative to `docs/`.

- `flow-station-early-risk-detection.md` — the flow-station early-risk process, `lh_silver` mapping, full historical-data requirements.
- `data-quality-findings.md` — **first real data read:** access, inventory, per-station numbers, the 86% `Mismatch` blocker, DQ issues. **Read first.**
- `early-warning-patterns.md` — first precursor analysis: ~95% base-rate reframing, loss persistence, per-cause precursor profiles (Well No-Flow signal leads the log by ≥7 days).
- `early-warning-model-design.md` — the model: L1 deviation engine → L2 onset GBM + survival → L3 value ranking; labels, evaluation, build order.
- `early-warning-architecture.md` — **NEW.** End-to-end Fabric architecture: medallion layers, Mermaid + ASCII diagrams, data contracts, daily run, security, environments, tooling.
- `prd-deferment-early-warning.md` — **NEW.** PRD for the early-warning capability (problem, goals/KPIs, requirements, milestones, risks, open questions, and the vertical-slice delivery plan).
- `wbs-deferment-early-warning.md` — **NEW.** Deliverable-oriented WBS: tree, dictionary, milestones, Gantt, effort, RACI, per-station coverage.
- `how-the-model-works.md` — **NEW.** Plain-language explainer of the whole pipeline (clean → features → labels → split → train → tune → cross-validate → evaluate → alert → feedback), with end-to-end Mermaid + ASCII diagrams and a "is this a time-series solution?" section.
- `README.md` — **NEW.** Index of all documents, grouped, with a suggested reading order and the repository layout.
- `model-framing-time-series-vs-forecasting.md` — **NEW.** Standalone note: is this time series? why the model is event prediction not forecasting, component classification, what a real forecasting model would be, why not ARIMA/Prophet/LSTM.
- `decisions-log.md` — **NEW.** Running log of key decisions (D-01…D-14) with rationale and links, plus the open decisions (O-01…O-06).
- `Issues/` (repo root) — **NEW.** Backlog of 17 vertical-slice/enabler issues derived from the PRD (`Issues/ISS-0xx-*.md` + `Issues/README.md` index). `Issues/Done/` holds completed work. Serving slices: ISS-015 (output tables + semantic model), ISS-016 (Power BI report pages), ISS-017 (publish app/RLS/refresh).
- `deferment-root-cause-deep-dive.md` — broader deferment analytics blueprint.
- `deferment-ml-engineering-blueprint.md` — ML/AI engineering blueprint.
- `how-fabric-delivers-results.md` — how results reach the customer.
- `context.md` — proposal summary (Wragby → NewCross).
- `NOTES.md` — scratchpad; **top section = current focus ("detect risk earlier")**.
- Code/data (repo root): `tools/fabric_query.py` (read-only live connector), `.env` (git-ignored config), `data/` (git-ignored extracts), `logs/` (query log), `docs/` (this folder).
- **Removed during the reorg (superseded):** `deferment-data-extraction-pack.md`, `how-to-give-agent-data-access.md`, `fabric-extract-queries.sql`, `fabric-extract-simple.sql`, `EXPORT-GUIDE.md`, `deferment-fabric-build-spec.md`, `equipment-rul-deferment-build-wbs.md`.
- `Production_shema.xlsx` — **schema only** (see §4).
- `Advanced Analytics & AI Proposal_Newcross.docx` — source proposal (not yet parsed).

## 4. Critical finding — real data now accessible (was: none available)

- **UPDATE 2026-10-08 (later same day): live read-only access ESTABLISHED.** Warehouse `wh_gold`, schema `production`, in NewCross's tenant (`newcross.com`), read via `tools/fabric_query.py` (Entra device-code sign-in, isolated `AZURE_CONFIG_DIR`). Read-only guard refuses all non-SELECT. 5 tables extracted to `data/` (git-ignored). See `data-quality-findings.md` — **read that first**.
- **~24 months of real data**: `deferment_fact` 40,290 events (2024-10-01→2026-10-07), `production_fact` 39,650 rows. 5 flow stations (OML 24's Ekulama 1/2 + Awoba, **plus OML 147 and EFE/OML 152**).
- **Top real finding:** deferment % of potential ranks **EFE 26.2% → OML147 14.0% → Ekulama2 11.1% → Awoba 7.5% → Ekulama1 6.0%**.
- **BLOCKER:** 86.2% of deferment events map to sub-category `Mismatch`; L1 categories are coarse (89% "Unscheduled"). Root-cause Pareto not yet possible. No duration in `deferment_fact`; `status` 100% blank; `gross` ≠ oil+water on 34.6% of rows; `target_oil` is station-level (repeated per string — must dedupe).

**Key schema observations (from the xlsx, not data):**
- `deferment_fact` has: `deferment_id, asset_id, flowstation_id, reservoir_id, date_id, category_id, subcategory_id, productionstring, status, gross, water, oil, gas, date`.
- `production_fact` has actuals vs `target_*`, plus `uptimeproduction, thp, bean, water_rf`.
- `oil_prices` has `date, oil_barrel_price_usd`.
- **Gap identified:** `deferment_fact` has **no `start_ts`/`end_ts`/duration** → can only trend daily volumes, cannot decompose frequency × duration, which is needed for true early warning. Adding duration is the highest-value schema change.

## 5. Key conclusions reached (concepts, not data findings)

- **Cause taxonomy must be normalised first** — the ~60 raw drivers merge into ~9 canonical categories (Well & Subsurface; Wellhead & Valves; Rotating/Artificial Lift; Flowline/Pipeline/Export; Processing & Facilities; Utilities & Power; Planned Operations; Shutdowns & Constraints; Third-Party/Community/HSE), with `NULL`/`Mismatch` excluded as data-quality flags.
- **Trend detection** = Pareto in 3 lenses (volume, frequency, duration) + frequency×duration×rate decomposition + seasonality + recurrence/MTBF + SPC control charts + cascade/association mining + change-point detection.
- **Early warning** = `Risk = P(event in next 24–72h) × expected deferred bbl × oil price`, tiered Red/Amber/Green, routed via Data Activator, with a feedback loop. Rule-based first, ML second.
- **Flow-station specificity**: each station needs its **own baseline**; compare stations only after **normalising** (deferment % of potential, events per well, per 1,000 bbl).
- **History rule of thumb**: **24–36 months** of clean, event-level, per-station data; under 12 months = only descriptive Pareto. `% unclassified` cause codes should be <5% (target ≥95% valid).

## 6. Where we stopped / immediate next step

- **UPDATE (same day):** step 1 below is **DONE** — `deferment-data-extraction-pack.md` was written (data contract + extract queries + DQ checks + derived views).
- Remaining next actions, in order:
  1. ~~Produce the data-extraction query pack / data contract~~ — **done.** User needs to review §7 open questions and run §2 extracts.
  2. Get real extracts into the workspace (CSV/Parquet per the §6 naming convention, or connection access).
  3. Then perform **real** per-station baseline / Pareto / recurrence analysis and prototype the station risk score on `flowstations_dim` + `deferment_fact` + `production_fact`.

## 7. Open questions for the user

- Which of the 9 `production` tables can be exported, and for what date range?
- Is deferred volume **measured** or **derived** (potential − actual)? Which formula?
- Is event **duration** available anywhere, or must it be reconstructed?
- Does the raw ~60-driver list correspond to `deferment_subcategory_dim` values, or to free-text notes? (Determines the taxonomy mapping work.)
- Is there a live historian feed (hourly THP/bean/pressure) for the precursor signals, or only daily data?

## 8. Suggested skills

- **`requirements-analysis`** — turn the proposal + deferment blueprint into a structured implementation blueprint once scope is firmed.
- **`domain-modeling`** — formalise the deferment cause taxonomy and the flow-station risk vocabulary into a governed ubiquitous language / `dim_cause` hierarchy.
- **`codebase-design`** — design the deep modules for the pattern-detection + scoring pipeline (data contract, feature table, risk scorer, flag router).
- **`grilling`** — stress-test the early-warning design (thresholds, precision/recall, alert fatigue) before build.
- **`tdd`** — when implementing the scorer/feature code, drive it test-first against sample fixtures (once extracts exist).
- **`diagnosing-bugs`** — for data-quality investigations (e.g. `NULL`/`Mismatch` cause codes, timing inconsistencies).
- **`find-skills`** — if a Fabric/Spark/analytics-specific skill is needed and not listed above.

## 9. Constraints / guardrails

- Do not claim data findings that aren't backed by real extracts — only a schema file exists.
- Prefer referencing the workspace `.md` artifacts over restating their content.
- All field/table names, KPIs and thresholds are **proposals to confirm in Discovery**.
- No secrets or credentials are present in this handoff; none were supplied during the session.
