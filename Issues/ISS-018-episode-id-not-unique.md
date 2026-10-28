---
id: ISS-018
title: Episode id is not unique (cause_group omitted)
type: enabler
slice: foundation
status: backlog
priority: P1
depends_on: [ISS-003]
runtime: fabric
---
# ISS-018 — Episode id is not unique

## Why
`silver_deferment_episode.episode_id` is built as:

```text
station_id | productionstring | cause_code | episode_seq
```

`cause_group` is not part of the key, but the source can assign different
cause groups to the same cause code (for example `Unknown` on one day and
`Unscheduled Deferment` on the previous days). The episode grouping includes
`cause_group`, so two distinct episodes receive the same `episode_id`.

Found during the Slice 8 parity check (2026-10-22):

- `silver_deferment_episode`: **1,004 rows, 934 unique episode ids**.
- **70 duplicate rows / 68 duplicated ids**, identical in Fabric and the local
  reference.
- Example: `1|TSTEK2002|Pressure Build Up|4` appears twice — one episode
  `2026-08-20 → 2026-08-22` (`Unscheduled Deferment`) and one
  `2026-08-23 → 2026-08-23` (`Unknown`).

The outcome job (`nb_07`) matches episodes by station + `episode_start` +
`cause_code`, so the 17 alert outcomes are unaffected. Any future join or
MERGE on `episode_id` would be wrong.

## Goal / demo
Every episode row has a stable unique id, and the id is safe to use as a join
key.

## In scope
- Add `cause_group` to the id **or** use a deterministic surrogate key
  (for example a hash of station, string, cause code, cause group and start).
- Update `nb_02_silver_conform` and any consumers that assume the old format.
- Add a uniqueness assertion in the notebook or DQ gate.
- Re-run the pipeline and the parity check.

## Out of scope
- Changing the episode definition or onset-labelling rules.

## Acceptance criteria
- [ ] `COUNT(*) = COUNT(DISTINCT episode_id)` on `silver_deferment_episode`.
- [ ] `episode_id` is unchanged for rows that were already unique, or the
      change is documented as a breaking id change.
- [ ] `nb_07` outcomes still reconcile to 14 confirmed / 3 false on the seed.
- [ ] Slice 8 parity still passes.

## Tasks
- [ ] Choose `cause_group` in the key vs a surrogate hash.
- [ ] Update `nb_02_silver_conform`.
- [ ] Add the uniqueness assertion and DQ check.
- [ ] Re-run `pl_df_daily_build` and `tools/parity_check.py`.
- [ ] Record the result in the build log.

## Data / dependencies
`silver_deferment_event` (category/subcategory joins), `nb_02`, `nb_07`,
`tools/parity_check.py`.

## Notes
Do not simply drop duplicate rows: they represent different episodes with
different start/end dates and deferred volumes.
