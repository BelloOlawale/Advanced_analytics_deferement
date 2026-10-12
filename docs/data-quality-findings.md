# Data-Quality Findings — NewCross EP `wh_gold` (real data, first look)

> Date: 2026-10-08 · Status: **first real read complete** (no longer schema-only)
> Source: Fabric Warehouse **`wh_gold`**, schema **`production`**, tenant `newcross.com`, via live read-only connection (`tools/fabric_query.py`).
> Local extracts (git-ignored): `data/oml24_*_20241001_20261007.csv`
> Companion docs: `deferment-data-extraction-pack.md`, `flow-station-early-risk-detection.md`, `how-to-give-agent-data-access.md`.

---

## 1. Access — established

- Warehouse reachable read-only via Entra device-code sign-in as `sharepoint.admin@Newcross.com` (NewCross tenant).
- Local read-only connector refuses any non-`SELECT` statement; every query logged to `logs/fabric_queries.log`.
- 5 tables pulled: `deferment_fact`, `production_fact`, `flowstations_dim`, `deferment_category_dim`, `deferment_subcategory_dim`.

## 2. What the data actually is

| Table | Rows | Grain | Range |
|---|---|---|---|
| `deferment_fact` | **40,290** | one row per **event** (`deferment_id` unique) | 2024-10-01 → 2026-10-07 |
| `production_fact` | **39,650** | one row per **string-day** | 2024-10-01 → 2026-10-07 |
| `flowstations_dim` | 5 | station | — |
| `deferment_category_dim` | 23 | cause category (L1) | — |
| `deferment_subcategory_dim` | 66 | cause sub-category (L2) | — |

- **History depth: ~24 months** (737 days, daily). Within the acceptable 24–36 target; below the preferred 36.
- **Scope is wider than OML 24.** Stations present: **Ekulama 1, Ekulama 2, Awoba** (OML 24) **plus OML 147 and EFE (OML 152)**. The proposal is OML 24 only — confirm whether OML 147/152 are in scope.
- 71 production strings across the 5 stations.

## 3. Headline numbers (24 months)

Totals: **actual oil 26,911,113 bbl**, deferred oil **2,742,969 bbl**, deferred gross 4,223,039.

| Flow station | Actual oil (bbl) | Target oil (bbl)* | Gap vs target | Deferred oil (bbl) | Deferment % of potential |
|---|---:|---:|---:|---:|---:|
| EFE (OML 152) | 796,745 | 949,873 | **16.1%** | 283,006 | **26.2%** |
| OML 147 | 2,537,915 | 2,831,822 | 10.4% | 412,467 | 14.0% |
| Ekulama 2 | 7,703,224 | 8,507,306 | 9.5% | 958,479 | 11.1% |
| Awoba | 4,596,118 | 4,894,415 | 6.1% | 371,838 | 7.5% |
| Ekulama 1 | 11,277,111 | 11,690,800 | 3.5% | 717,180 | 6.0% |

\* Target is a station-level daily figure (see §5.1); shown deduplicated. `deferment % = deferred / (actual + deferred)`.

**First real signal:** station risk ranking is already meaningful — **EFE is worst on both gap and deferment**, Ekulama 1 best. This is the cross-station comparison the engagement asked for.

## 4. THE BLOCKER — detailed cause codes are ~86% unusable

| Metric | Value |
|---|---|
| Events mapped to sub-category **`Mismatch`** (id 6) | **34,717 of 40,290 (86.2%)** |
| …their deferred oil | 1,229,994 bbl (**44.8%** of all deferred oil) |
| Events with blank sub-category (id 10) | 124 |
| **Usable coded events** | ~5,400 (13.5%) |

At **category (L1)** level the data is populated but coarse:

| Category | Events | Deferred oil |
|---|---:|---:|
| Unscheduled Deferment | 35,960 (89.3%) | 1,903,990 |
| Scheduled Deferment | 1,194 | 510,444 |
| Third-Party Deferment | 252 | 161,789 |
| Surveillance | 2,133 | 44,600 |
| (blank / others) | ~750 | ~120,000 |

**Consequence:** a true root-cause Pareto — the core deliverable — is **not possible** on current codes. 86% of events say only "Unscheduled" + "Mismatch".

**Usable coded causes (the ~13.5%)** — enough to start recurrence work on these:
Well No-Flow (1,420 events), Engine Failure (695), Facility Shutdown (435), Pressure Build Up (418), Flow Station Trip (352), Wellhead Leak (224), EPF Unavailability (158), Wellhead Fire Outbreak (141), Manual FS Shutdown (139), Power Trip (121), Flowline leak (111).

## 5. Other data-quality findings

1. **`target_oil` is a station-level value repeated on every string row** (confirmed: one distinct target per station-day). Must **deduplicate** (e.g. `max(target_oil)` per station-day) before any target-variance maths — otherwise it inflates ~15×.
2. **`status` is 100% blank** in `deferment_fact` (all 40,290 rows). Planned/unplanned can only be inferred from category (Scheduled/Unscheduled/Third-Party).
3. **`gross` ≠ `oil + water` on 13,928 rows (34.6%)** — often `gross < water` when `oil = 0`. So `gross` is a *different* measure (definition unknown). Do not assume `gross = oil + water`.
4. **Precursor coverage is partial:** `thp` NULL on 9,194 rows (23.2%), `bean` NULL on 10,500 (26.5%). `uptimeproduction` and `water_rf` are fully populated.
5. **`uptimeproduction` is hours/day (0–24)**, avg **19.83** → ~82.6% uptime. 79.5% of rows are a full 24 h; 843 rows show uptime>0 but oil=0.
6. **No duration / start-end** in `deferment_fact` — confirmed. Events can be counted, not timed → no frequency × duration decomposition or MTBF yet.
7. No negative volumes, no duplicate `deferment_id`.

## 6. What is now possible vs blocked

**Possible now**
- Cross-station risk ranking and deferment % (done, §3) — EFE vs peers.
- Daily deferment % / uptime / THP / bean / water-cut trends per station (with the missingness caveat).
- Recurrence of the ~13.5% coded causes (Well No-Flow, Engine Failure, Power Trip, Flowline leak, …).
- Rough early-warning prototypes on `uptimeproduction`, `thp`, `bean`, `water_rf`.

**Blocked**
- Root-cause Pareto (86% "Mismatch").
- Frequency × duration / MTBF (no duration).
- Trustworthy target-variance at string level until target grain is fixed (must dedupe).

## 7. Requests / actions

1. **Fix the cause codes** (highest value). Where does the real driver live — the upstream deferment log's free text, or a corrected mapping? The ~60 raw drivers from the earlier session must be joined to `deferment_subcategory_dim` upstream. Target ≥95% valid.
2. **Confirm the `gross` definition** (why it differs from oil+water).
3. **Confirm `status`** — is it intentionally empty, or a broken load?
4. **Confirm scope** — are OML 147 / OML 152 in scope, or only OML 24?
5. **Add event start/end (or duration)** to `deferment_fact` — the single highest-value schema change.
6. Optional: also pull `assets_dim`, `reservoirs_dim`, `oil_prices` (tiny) for value-at-risk and context.

---

*All numbers from the live extract of 2026-10-08. Re-run the DQ report after any data fix.*
