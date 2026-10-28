# data/ — local analysis extracts (git-ignored)

Drop data extracts here. Everything except this README and `.gitkeep` is ignored by git
(see the "NewCross EP analysis data" block in `.gitignore`), because production data must
never be pushed to the GitHub repo.

## Naming convention
`oml24_<table>_<YYYYMMDD_from>_<YYYYMMDD_to>.<ext>`
e.g. `oml24_deferment_fact_20231001_20261001.csv`

## Minimum-viable first pull (3 files)
1. `oml24_deferment_fact_<range>.csv`
2. `oml24_production_fact_<range>.csv`
3. `oml24_flowstations_dim_<range>.csv`

## Full pull (adds context + value-at-risk)
- `oml24_assets_dim_*.csv`
- `oml24_reservoirs_dim_*.csv`
- `oml24_deferment_category_dim_*.csv`
- `oml24_deferment_subcategory_dim_*.csv`
- `oml24_oil_prices_*.csv`

Queries: see `../deferment-data-extraction-pack.md` (§2), DQ checks (§3).
How to grant live access: see `../how-to-give-agent-data-access.md`.

## Generating test data for a new environment

If a new tenant has no source data, seed from these extracts:

```bash
python tools/generate_test_data.py --env sandbox --days 180 --anonymise
```

This writes an upload-ready set under `test_data/sandbox/` (git-ignored) with
`raw/` and `ref/` folders. See `docs/test-environment-setup.md`.
The generator can also run fully synthetic (`--source synthetic`) when the
extracts are not present.
