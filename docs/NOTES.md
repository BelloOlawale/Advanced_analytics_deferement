# Teaching Notes — Working Scratchpad

## CURRENT FOCUS (2026-10-08) — read this first
**Question to answer: "How to detect the risk earlier?"**

- Goal: **catch deferment BEFORE it occurs** and raise an **early-warning signal**.
- Method: use the historical `deferment_fact` + `production_fact` (24 mo, `wh_gold`, in `data/`) to learn the
  **patterns that precede a loss event** (precursors), and how far in advance they move.
- This is **leading-indicator** work, not post-hoc root-cause. The 86% `Mismatch` cause codes limit
  *why* analysis, but early warning can still be built from **process precursors**: `uptimeproduction`,
  `thp`, `bean`, `water_rf`, oil-vs-target drift, and per-station/string baselines.
- Deliverable shape: precursor → lead time → per-station early-warning score (Red/Amber/Green) → alert.
- Everything else (taxonomy fixes, duration, scope) is *enabling* work; keep this aim in view.

See `data-quality-findings.md` for what the data is and is not.

---

## Workspace context
This directory is also the working folder for the **NewCross EP / Wragby "Advanced Analytics & AI"** engagement. The user has already produced (via prior agent sessions) several non-teaching documents that are useful **raw material**, not trusted sources:

- `context.md` — proposal summary
- `deferment-root-cause-deep-dive.md` — analytics blueprint
- `deferment-fabric-build-spec.md` — customer offer + Fabric build
- `deferment-ml-engineering-blueprint.md` — ML/AI engineering blueprint
- `how-fabric-delivers-results.md` — how results reach the customer
- `Advanced Analytics & AI Proposal_Newcross.docx` — source proposal

> These are the user's own artifacts. Cite external high-trust sources in lessons; use these only as context/mission grounding.

## Teaching preferences (TBD — confirm with user)
- Preferred session length: unknown
- Preferred lesson format: unknown (assumed HTML per skill)
- Community participation: unknown
- Level of Python/ML/Fabric experience: unknown

## Open mission questions
Recorded in chat; awaiting user answers before writing `MISSION.md`.
