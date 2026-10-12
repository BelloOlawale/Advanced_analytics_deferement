# Early-Warning Pattern Analysis — first pass on real data

> Focus: **"How to detect the risk earlier?"** — catch deferment *before* it occurs.
> Data: `wh_gold` extract in `data/` (24 mo, 2024-10-01 → 2026-10-07). Queries via `tools/fabric_query.py` / duckdb.
> Method: define an event *onset* and profile the process signals in the days **before** it.
> Caveat up front: first pass compares pre-onset signals to a **global** baseline; the correct next step is a **per-string / per-station baseline** (string identity confounds these averages).

---

## 1. The reframing that matters most

**Deferment is present on ~95% of station-days.** Every station has a logged event on 675–709 of 737 days.

| Station | Days with ≥1 event (of 737) |
|---|---:|
| OML 147 | 709 |
| Ekulama 2 | 700 |
| Ekulama 1 | 700 |
| Awoba | 697 |
| EFE | 675 |

**Consequence:** you **cannot** predict "will there be a deferment?" — the base rate is ~95%, so a model that always says *yes* is 95% accurate and useless. "Earlier" cannot mean earlier detection of *occurrence*.

Early warning must instead target one of:
1. **Onset** — the first day of a *specific* failure episode (e.g. a compressor/engine/power event).
2. **Severity** — a day whose loss is far above that station's own normal (spike).
3. **Regime shift** — the station's loss level or pattern *changing* (worsening), not merely continuing.

## 2. Loss is highly persistent (so "today looks like yesterday")

Lag-1 autocorrelation of daily deferred oil per station:

| Station | lag-1 corr | reading |
|---|---:|---|
| OML 147 | **0.82** | loss is a chronic condition; yesterday predicts today almost perfectly |
| Ekulama 2 | **0.79** | chronic |
| EFE | 0.54 | more volatile |
| Ekulama 1 | 0.52 | volatile |
| Awoba | 0.45 | most volatile/spiky |

**Implication:** a model that just uses "yesterday's loss" will look accurate but will **warn too late** — it fires only *after* the loss has already started. The value is in detecting the **change**, which is why the precursor study below matters.

Daily deferred-oil scale (bbl): Ekulama 2 median 757 / p99 14,883 / max 16,478; Ekulama 1 median 375 / max 22,957; EFE smallest (median 366, max 1,490).

## 3. Precursor profiles — what the days before an onset look like

"Onset" = first day of a run of consecutive days carrying a given cause on a given string (k=0 is onset day; k=1..7 are the days before).

**Baseline across all string-days: oil 679, uptime 19.8, THP 871, bean 26.6, water_rf 0.086.**

### Well No-Flow (1,420 events) — *strongest early signal*
| k | oil | uptime | THP | bean | water_rf |
|---:|---:|---:|---:|---:|---:|
| 7 | 193 | 4.9 | 289 | 25.5 | 0.009 |
| 3 | 180 | 4.1 | 281 | 25.6 | 0.013 |
| 1 | 169 | 4.5 | 318 | 25.4 | 0.010 |
| 0 | 101 | 1.9 | 301 | 25.6 | 0.009 |

**The string is already collapsed a full week before the code appears** — oil ~1/4 of normal, uptime ~4 h vs 19.8, THP ~290 vs 871. The recorded "Well No-Flow" **lags the physical signal by ≥7 days**. This *is* the early-warning window.

### Engine Failure (695 events)
| k | oil | uptime | THP | bean | water_rf |
|---:|---:|---:|---:|---:|---:|
| 7 | 180 | 17.2 | 1,098 | 20.7 | 0.143 |
| 1 | 207 | 17.2 | 1,118 | 21.0 | 0.157 |
| 0 | 167 | 11.4 | 1,110 | 20.7 | 0.115 |

Days before: uptime **~17 vs 19.8 baseline** (modestly depressed), water cut **elevated (0.14+ vs 0.086)**, bean **smaller (20.7 vs 26.6)**. A weak but present drift; the drop sharpens at onset.

### Flowline leak (111 events)
| k | oil | uptime | THP |
|---:|---:|---:|---:|
| 7 | 464 | 16.0 | 1,274 |
| 3 | 368 | 12.5 | 1,291 |
| 0 | 235 | 6.6 | 1,243 |

**A visible multi-day decay** — uptime 16 → 12.5 → 6.6 and oil 464 → 368 → 235 in the week before the code.

### Power Trip (121 events) — *no usable precursor here*
| k | oil | uptime | THP |
|---:|---:|---:|---:|
| 7 | 827 | 24.0 | 976 |
| 1 | 739 | 21.4 | 958 |
| 0 | 686 | 19.7 | 959 |

Strings were producing **normally/above baseline right up to the trip**. Warning for this must come from **power/electrical logs or higher-frequency data**, which we do not have.

### Facility Shutdown (435 events) — *no usable precursor here*
Behaves the same way: output high (oil ~800–950, uptime ~18–23) until onset, then drops. Sudden.

## 4. What this tells us

1. **For "chronic + deterioration" causes (Well No-Flow, Flowline leak, and partly Engine Failure), the process signal leads the log by days** → real early warning is possible *now*, with current data.
2. **For abrupt causes (Power Trip, Facility Shutdown), daily process data gives no lead** → need power/equipment/event feeds, or higher-frequency (hourly) signals.
3. **The governing method is deviation from each entity's own baseline** — "THP fell below this string's normal", "uptime dropped vs this station's normal" — not comparison to a fleet-wide average (the confound in §3).
4. **The 86% `Mismatch` cause problem limits *why*, but not *when*** — early warning can be built on process deviation even while the cause taxonomy is fixed.

## 5. Recommended next step (directly answers "how early?")

Build the **per-entity baseline + deviation engine** and measure **lead time**:

1. For each **station** and each **string**, learn its own normal for `uptimeproduction`, `thp`, `bean`, `water_rf`, oil-vs-target.
2. Compute daily **deviation (z-score / EWMA / CUSUM)** per signal.
3. For each coded-cause onset, ask: **how many days before onset did a deviation cross threshold?** → gives **lead time**, per cause, per station.
4. Only then add a score (deviation magnitude × bbl at risk × price) and Red/Amber/Green tiers.

That converts "we think we can warn earlier" into a measured number: **"~N days of warning, for cause X, at station Y, with Z% false alarms."**

---

*First pass, 2026-10-08. Numbers are from the current extract and will be re-run after any taxonomy/data fix. All thresholds are proposals.*
