# Slice 8 — Fabric vs local parity check

**Run:** 2026-10-26 12:40 UTC  
**Environment:** `sandbox`  
**Input window:** `test_data\sandbox`  
**Fabric snapshot:** `test_data\parity\fabric`  
**Verdict:** **PASS**

## What this checks

The same seed CSVs were run through two independent implementations:

1. **Fabric** — `nb_01 → nb_07` in `lh_bronze` / `lh_silver` / `lh_gold`.
2. **Local reference** — a clean-room pandas implementation of the documented
   notebook rules (`tools/parity_reference.py`), reading `raw/` and `ref/` directly.

The historical prototype code is not in this repository, so this is a
clean-room parity check against the same input, not a replay of the original
prototype. The timestamps and batch ids are intentionally excluded, as are
the bronze audit columns (`_batch_id`, `_ingested_at_utc`, `_source_file`).

Tolerances: numeric `atol=1e-6`, `rtol=1e-9`; empty/NA are equivalent;
JSON payloads are compared semantically (metric, direction, z, value, expected).

## Table results

| Table | Local rows | Fabric rows | Keys | Compared cols | Result |
|---|---:|---:|---|---:|---|
| `silver_dim_station` | 5 | 5 | flowstation_id | 4 | PASS |
| `silver_dim_date` | 90 | 90 | date | 7 | PASS |
| `silver_oil_prices` | 90 | 90 | date | 2 | PASS |
| `silver_owner_map` | 5 | 5 | station_id | 5 | PASS |
| `silver_station_day` | 399 | 399 | station_id, date | 22 | PASS |
| `silver_deferment_event` | 5,225 | 5,225 | deferment_id | 19 | PASS |
| `silver_deferment_episode` | 1,004 | 1,004 | station_id, productionstring, cause_code, cause_group, episode_start, episode_end | 11 | PASS |
| `gold_entity_baseline` | 40 | 40 | entity_id, metric | 28 | PASS |
| `gold_entity_day_features` | 450 | 450 | station_id, date | 171 | PASS; 8 benign tie flip(s) |
| `gold_deviation_daily` | 3,111 | 3,111 | entity_id, date, metric | 17 | PASS |
| `gold_risk_daily` | 450 | 450 | station_id, date | 41 | PASS |
| `gold_alert` | 17 | 17 | alert_id | 26 | PASS |
| `gold_alert_outcome` | 17 | 17 | alert_id | 12 | PASS |
| `gold_df_dim_date` | 90 | 90 | date | 13 | PASS |
| `gold_df_dim_station` | 5 | 5 | station_id | 5 | PASS |

## KPI parity

| KPI | Local reference | Fabric | Match |
|---|---:|---:|---|
| feature_rows | 450 | 450 | yes |
| observed_rows | 399 | 399 | yes |
| scored_rows | 273 | 273 | yes |
| risk_rows | 450 | 450 | yes |
| red_days | 25 | 25 | yes |
| amber_days | 22 | 22 | yes |
| green_days | 226 | 226 | yes |
| deviation_rows | 3,111 | 3,111 | yes |
| outlier_rows | 266 | 266 | yes |
| alerts_fired | 17 | 17 | yes |
| alerts_red | 9 | 9 | yes |
| alerts_amber | 8 | 8 | yes |
| excess_value_at_risk_usd | 20,584,946.592555 | 20,584,946.592555 | yes |
| excess_usd_at_alert | 1,316,716.738804 | 1,316,716.738804 | yes |
| outcome_rows | 17 | 17 | yes |
| evaluated | 17 | 17 | yes |
| confirmed | 14 | 14 | yes |
| false_alarms | 3 | 3 | yes |
| pending | 0 | 0 | yes |
| median_lead_days | 2.000000 | 2.000000 | yes |
| mean_lead_days | 2.500000 | 2.500000 | yes |
| precision_pct | 82.352941 | 82.352941 | yes |
| false_alarm_rate_pct | 17.647059 | 17.647059 | yes |
| dim_date_rows | 90 | 90 | yes |
| dim_station_rows | 5 | 5 | yes |

## Known differences

1. **Top-signal tie flips (8 feature rows).** `oil` and `target_gap_pct`
   have mathematically equal `|z|` on these rows (target gap is the
   complement of oil against the same target). Sub-1e-15 differences in the
   two runtimes decide which one is labelled as `top_signal`. This changes
   the label and the sign of `top_signal_z`, but not the risk score, tier or
   any alert. `top_signal` is display/explanation data only.
2. **`uptime_roll_std_7` (11 feature rows) differs by at most `7.6e-7`.**
   The true value is zero for constant windows; both runtimes produce
   floating-point dust around zero. It is far below any operational tolerance.

## Defect found during parity

`silver_deferment_episode.episode_id` is **not unique**: 70 duplicate rows in the local reference and 70 in Fabric (identical in both). The id is built as `station_id|productionstring|cause_code|episode_seq`, but `cause_group` can be `Unknown` for one continuation of the same cause code and `Unscheduled Deferment` for another. The id therefore collides across
two different episodes.

Impact: the outcome job matches episodes by station + episode_start +
cause_code, so the 17 alert outcomes still match exactly. The id should
not be used as a join key until it includes `cause_group` or a surrogate.

## Acceptance

- Row counts, keys, numeric values, risk tiers, alerts and outcomes match
  within the stated tolerances.
- The only text differences are the 8 documented tie flips in a
  display-only feature field.
- No pipeline output is changed by this check: it is read-only.

## Reproduce

```bash
python tools/parity_check.py --env sandbox --input test_data\sandbox \
    --fabric-dir test_data\parity\fabric
```

Cached Fabric CSVs live under the `--fabric-dir` (git-ignored). Re-run
without `--fetch` to compare against the cached snapshot.
