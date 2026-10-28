#!/usr/bin/env python3
"""
generate_test_data.py - build seed data for a new Fabric environment.

The new tenant has no production data. This tool creates a small, consistent,
upload-ready dataset in one of two ways:

  seed       Take the last N days of the existing CSV extracts in `data/`
             and write them out cleanly (optionally anonymised). Best when the
             extracts are present; the results still look and behave like the
             real data.

  synthetic  Generate data from scratch with the same schema, realistic
             ranges, and injected precursor signals before coded failures.
             Used automatically when the extracts are missing.

Output layout (ready to upload into a lakehouse `Files/` area):

    test_data/<env>/
        raw/     production_fact, deferment_fact + the three dimensions
        ref/     dim_date, dim_asset, dim_station, dim_well,
                 oil_prices, owner_map
        _manifest.json
        README.md

Examples
--------
    # Seed from the existing extracts; last 180 days; anonymised station names
    python tools/generate_test_data.py --env sandbox --days 180 --anonymise

    # Force fully synthetic data (no extracts needed)
    python tools/generate_test_data.py --env sandbox --source synthetic --days 365

    # Bigger seed set, reproducible
    python tools/generate_test_data.py --env sandbox --days 365 --seed 7

Safety
------
The output may contain client-derived values, so `test_data/` is git-ignored.
Do not commit it. It is intended for a sandbox tenant/workspace only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

TABLES = {
    "deferment_fact": "*deferment_fact_*.csv",
    "production_fact": "*production_fact_*.csv",
    "flowstations_dim": "*flowstations_dim_*.csv",
    "deferment_category_dim": "*deferment_category_dim_*.csv",
    "deferment_subcategory_dim": "*deferment_subcategory_dim_*.csv",
}

PRODUCTION_FIELDS = [
    "production_id", "asset_id", "flowstation_id", "reservoir_id", "date_id",
    "productionstring", "status", "gas", "target_gas", "target_exportgas",
    "target_fuelgas", "target_gasflared", "gross", "target_gross", "oil",
    "target_oil", "uptimeproduction", "water", "water_rf", "thp", "bean",
    "production_date",
]

DEFERMENT_FIELDS = [
    "deferment_id", "asset_id", "flowstation_id", "reservoir_id", "date_id",
    "category_id", "subcategory_id", "productionstring", "status", "gross",
    "water", "oil", "gas", "date",
]

STATIONS = [
    # id, name, asset_id, asset
    (1, "Ekulama 2 Flowstation", 4, "OML 24"),
    (2, "Awoba Flowstation", 4, "OML 24"),
    (3, "OML 147 Flowstation", 1, "OML 147"),
    (6, "Ekulama 1 Flowstation", 4, "OML 24"),
    (8, "EFE Flowstation", 3, "OML 152"),
]

STATION_CODES = {1: "EK2", 2: "AWO", 3: "OML147", 6: "EK1", 8: "EFE"}

CATEGORIES = [
    (5, "Surveillance"),
    (10, "Unscheduled Deferment"),
    (11, "Well Intervention"),
    (12, "Flowline/ Manifold"),
    (18, "Scheduled Maintenance & Inspection"),
    (19, "Pump"),
    (22, "Instrumentation & Control"),
    (23, "Well Services"),
    (24, "Third Party"),
    (25, "Power"),
]

SUBCATEGORIES = [
    (6, "Mismatch"),
    (20, "Well No-Flow"),
    (21, "Engine Failure"),
    (22, "Facility Shutdown"),
    (23, "Flowline leak"),
    (24, "Power Trip"),
    (25, "Wellhead Leak"),
    (26, "Pressure Build Up"),
    (27, "Planned Maintenance"),
]

# Causes that are preceded by a detectable process decline.
PRECURSOR_CAUSES = {"Well No-Flow", "Engine Failure", "Flowline leak"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def find_source(key: str) -> Path | None:
    matches = sorted(DATA.glob(TABLES[key]))
    return matches[-1] if matches else None


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def write_table(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def date_id(day: dt.date) -> str:
    return day.strftime("%Y%m%d")


def fmt(value: float) -> str:
    return f"{value:.10f}"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# seed mode
# ---------------------------------------------------------------------------

def load_seed() -> dict[str, tuple[list[str], list[dict[str, str]]]]:
    loaded: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    missing = []
    for key in TABLES:
        path = find_source(key)
        if path is None:
            missing.append(key)
            continue
        loaded[key] = read_table(path)
    if missing:
        raise FileNotFoundError(
            "Missing extract(s) in data/: " + ", ".join(missing)
        )
    return loaded


def slice_dates(rows: list[dict], date_field: str, days: int, end: dt.date) -> set[str]:
    dates = sorted({
        row[date_field] for row in rows
        if row.get(date_field) and dt.date.fromisoformat(row[date_field]) <= end
    })
    if not dates:
        return set()
    return set(dates[-days:])


def anonymise_tables(
    tables: dict[str, tuple[list[str], list[dict[str, str]]]]
) -> dict[str, tuple[list[str], list[dict[str, str]]]]:
    station_map = {sid: f"Test Station {chr(64 + i)}" for i, (sid, *_rest) in enumerate(STATIONS, 1)}
    asset_map = {"OML 24": "TEST-ASSET-1", "OML 147": "TEST-ASSET-2", "OML 152": "TEST-ASSET-3"}
    well_map: dict[str, str] = {}

    def well_for(station_id: str, original: str) -> str:
        if original not in well_map:
            code = STATION_CODES.get(int(station_id), "TST") if str(station_id).isdigit() else "TST"
            well_map[original] = f"TST{code}{len(well_map) + 1:03d}"
        return well_map[original]

    fields, rows = tables["flowstations_dim"]
    for row in rows:
        row["flowstation"] = station_map.get(int(row["flowstation_id"]), row["flowstation"])
        row["asset"] = asset_map.get(row["asset"], row["asset"])

    fields, rows = tables["production_fact"]
    for row in rows:
        row["productionstring"] = well_for(row["flowstation_id"], row["productionstring"])

    fields, rows = tables["deferment_fact"]
    for row in rows:
        row["productionstring"] = well_for(row["flowstation_id"], row["productionstring"])

    return tables


def seed_dataset(
    days: int, end: dt.date, anonymise: bool
) -> tuple[dict[str, tuple[list[str], list[dict]]], dict]:
    tables = load_seed()
    prod_fields, prod_rows = tables["production_fact"]
    defer_fields, defer_rows = tables["deferment_fact"]

    keep_dates = slice_dates(prod_rows, "production_date", days, end)
    if not keep_dates:
        raise SystemExit("No production dates found; check the extracts and --end.")

    if anonymise:
        tables = anonymise_tables(tables)
        prod_fields, prod_rows = tables["production_fact"]
        defer_fields, defer_rows = tables["deferment_fact"]

    prod_rows = [r for r in prod_rows if r["production_date"] in keep_dates]
    defer_rows = [r for r in defer_rows if r["date"] in keep_dates]

    out: dict[str, tuple[list[str], list[dict]]] = {
        "production_fact": (prod_fields, prod_rows),
        "deferment_fact": (defer_fields, defer_rows),
        "flowstations_dim": tables["flowstations_dim"],
        "deferment_category_dim": tables["deferment_category_dim"],
        "deferment_subcategory_dim": tables["deferment_subcategory_dim"],
    }
    meta = {
        "source": "seed",
        "source_files": {
            key: str(find_source(key)) for key in TABLES
        },
        "anonymised": anonymise,
    }
    return out, meta


# ---------------------------------------------------------------------------
# synthetic mode
# ---------------------------------------------------------------------------

def synthetic_dataset(
    days: int, end: dt.date, seed: int
) -> tuple[dict[str, tuple[list[str], list[dict]]], dict]:
    rng = random.Random(seed)
    start = end - dt.timedelta(days=days - 1)

    # 14 wells per station -> 70 wells, close to the real 71.
    wells: dict[tuple[int, int], str] = {}
    for sid, _name, _asset_id, _asset in STATIONS:
        for i in range(14):
            code = STATION_CODES[sid]
            wells[(sid, i)] = f"{code}{i + 1:03d}S:B{1000 + i}Q"

    # stable per-well base rates
    base = {
        (sid, i): rng.uniform(180, 1400)
        for sid, _n, _a, _asset in STATIONS
        for i in range(14)
    }

    prod_rows: list[dict] = []
    defer_rows: list[dict] = []
    index: dict[tuple[str, str], dict] = {}
    prod_id = 1
    defer_id = 1
    day = start

    while day <= end:
        did = date_id(day)
        season = 1.0 + 0.08 * math.sin(2 * math.pi * day.timetuple().tm_yday / 365.0)
        for sid, _name, asset_id, _asset in STATIONS:
            for i in range(14):
                well = wells[(sid, i)]
                potential = base[(sid, i)] * season
                uptime = clamp(rng.gauss(21.0, 2.8), 0.0, 24.0)
                oil = max(0.0, potential * (uptime / 24.0) * rng.lognormvariate(0.0, 0.12))
                target = potential / 0.88
                water_rf = clamp(rng.gauss(0.09, 0.045), 0.004, 0.55)
                water = oil * water_rf
                thp = clamp(rng.gauss(870, 240) * (0.45 + 0.55 * uptime / 24.0), 30, 2600)
                bean = clamp(rng.gauss(27, 6), 5, 90)
                row = {
                    "production_id": prod_id,
                    "asset_id": asset_id,
                    "flowstation_id": sid,
                    "reservoir_id": 10 + (i % 25),
                    "date_id": did,
                    "productionstring": well,
                    "status": "",
                    "gas": fmt(oil * 0.12),
                    "target_gas": "",
                    "target_exportgas": "",
                    "target_fuelgas": "",
                    "target_gasflared": "",
                    "gross": fmt(oil + water),
                    "target_gross": "",
                    "oil": fmt(oil),
                    "target_oil": fmt(target),
                    "uptimeproduction": fmt(uptime),
                    "water": fmt(water),
                    "water_rf": fmt(water_rf),
                    "thp": fmt(thp),
                    "bean": fmt(bean),
                    "production_date": day.isoformat(),
                }
                prod_rows.append(row)
                index[(well, day.isoformat())] = row
                prod_id += 1

            # ~18% of station-days lose production
            if rng.random() < 0.18:
                i = rng.randrange(14)
                well = wells[(sid, i)]
                coded = rng.random() >= 0.86
                if coded:
                    sc_id, sc_name = rng.choice(
                        [s for s in SUBCATEGORIES if s[1] in PRECURSOR_CAUSES]
                    )
                    cat_id = 10 if sc_name != "Planned Maintenance" else 18
                else:
                    sc_id, sc_name = 6, "Mismatch"
                    cat_id = 10
                deferred = max(1.0, float(index[(well, day.isoformat())]["oil"]) * rng.uniform(0.25, 0.85))
                water_loss = deferred * rng.uniform(0.05, 0.3)
                defer_rows.append({
                    "deferment_id": defer_id,
                    "asset_id": asset_id,
                    "flowstation_id": sid,
                    "reservoir_id": 10 + (i % 25),
                    "date_id": did,
                    "category_id": cat_id,
                    "subcategory_id": sc_id,
                    "productionstring": well,
                    "status": "",
                    "gross": fmt(deferred + water_loss),
                    "water": fmt(water_loss),
                    "oil": fmt(deferred),
                    "gas": fmt(deferred * 0.1),
                    "date": day.isoformat(),
                })
                defer_id += 1

                # Inject a detectable deterioration in the 7 days before a
                # coded event, so the early-warning logic has something to find.
                if coded and sc_name in PRECURSOR_CAUSES:
                    for back in range(1, 8):
                        prior = (day - dt.timedelta(days=back)).isoformat()
                        row = index.get((well, prior))
                        if not row:
                            continue
                        factor = 0.30 + 0.07 * back  # worsens toward onset
                        row["oil"] = fmt(float(row["oil"]) * factor)
                        row["uptimeproduction"] = fmt(float(row["uptimeproduction"]) * factor)
                        row["thp"] = fmt(float(row["thp"]) * factor)
                        row["water"] = fmt(float(row["water"]) * (1.0 - factor * 0.4))
                        row["gross"] = fmt(float(row["oil"]) + float(row["water"]))
        day += dt.timedelta(days=1)

    out = {
        "production_fact": (PRODUCTION_FIELDS, prod_rows),
        "deferment_fact": (DEFERMENT_FIELDS, defer_rows),
        "flowstations_dim": (
            ["flowstation_id", "flowstation", "asset"],
            [{"flowstation_id": sid, "flowstation": name, "asset": asset}
             for sid, name, _aid, asset in STATIONS],
        ),
        "deferment_category_dim": (
            ["category_id", "category"],
            [{"category_id": cid, "category": name} for cid, name in CATEGORIES],
        ),
        "deferment_subcategory_dim": (
            ["subcategory_id", "sub_category"],
            [{"subcategory_id": sid, "sub_category": name} for sid, name in SUBCATEGORIES],
        ),
    }
    meta = {"source": "synthetic", "seed": seed, "anonymised": False}
    return out, meta


# ---------------------------------------------------------------------------
# reference tables
# ---------------------------------------------------------------------------

def build_reference(
    tables: dict[str, tuple[list[str], list[dict]]], days: int, end: dt.date, seed: int
) -> dict[str, tuple[list[str], list[dict]]]:
    rng = random.Random(seed)
    _pf, prod = tables["production_fact"]
    _ff, flow = tables["flowstations_dim"]

    station_asset: dict[str, int] = {}
    for row in prod:
        sid = row["flowstation_id"]
        station_asset.setdefault(sid, Counter())[row["asset_id"]] += 1
    station_asset = {sid: counter.most_common(1)[0][0] for sid, counter in station_asset.items()}

    station_name = {row["flowstation_id"]: row["flowstation"] for row in flow}
    asset_name = {row["asset_id"]: row["asset"] for row in flow} if flow and "asset_id" in flow[0] else {}
    if not asset_name:
        # flowstations_dim has no asset_id; derive via station -> asset_id
        by_asset = {}
        for row in flow:
            aid = station_asset.get(row["flowstation_id"])
            if aid is not None:
                by_asset[aid] = row["asset"]
        asset_name = by_asset

    dim_station = [{
        "flowstation_id": sid,
        "flowstation": station_name.get(sid, f"Station {sid}"),
        "asset_id": aid,
        "asset": asset_name.get(aid, ""),
    } for sid, aid in sorted(station_asset.items())]

    dim_asset = [{"asset_id": aid, "asset": name} for aid, name in sorted(asset_name.items())]

    well_seen = set()
    dim_well = []
    for row in prod:
        key = (row["productionstring"], row["flowstation_id"])
        if key in well_seen:
            continue
        well_seen.add(key)
        dim_well.append({
            "productionstring": row["productionstring"],
            "flowstation_id": row["flowstation_id"],
            "asset_id": row["asset_id"],
        })

    dates = sorted({row["production_date"] for row in prod})
    dim_date = [{
        "date_id": d.replace("-", ""),
        "date": d,
        "year": d[:4],
        "month": d[5:7],
        "day": d[8:10],
        "weekday": dt.date.fromisoformat(d).strftime("%A"),
        "is_weekend": "1" if dt.date.fromisoformat(d).weekday() >= 5 else "0",
    } for d in dates]

    price = 76.0
    oil_prices = []
    for d in dates:
        price = clamp(price + rng.gauss(0, 1.2), 45, 120)
        oil_prices.append({"date": d, "oil_price_usd": f"{price:.2f}"})

    owner_map = []
    for row in dim_station:
        owner_map.append({
            "flowstation_id": row["flowstation_id"],
            "flowstation": row["flowstation"],
            "asset": row["asset"],
            "owner_name": f"Test Owner {row['flowstation_id']}",
            "owner_upn": f"ops{row['flowstation_id']}@example.com",
        })

    return {
        "dim_date": (["date_id", "date", "year", "month", "day", "weekday", "is_weekend"], dim_date),
        "dim_asset": (["asset_id", "asset"], dim_asset),
        "dim_station": (["flowstation_id", "flowstation", "asset_id", "asset"], dim_station),
        "dim_well": (["productionstring", "flowstation_id", "asset_id"], dim_well),
        "oil_prices": (["date", "oil_price_usd"], oil_prices),
        "owner_map": (["flowstation_id", "flowstation", "asset", "owner_name", "owner_upn"], owner_map),
    }


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def validate(tables: dict[str, tuple[list[str], list[dict]]]) -> dict:
    """Cheap referential-integrity checks. Warnings do not block the write."""
    _pf, prod = tables["production_fact"]
    _df, defer = tables["deferment_fact"]
    _ff, flow = tables["flowstations_dim"]
    _cf, cats = tables["deferment_category_dim"]
    _sf, subs = tables["deferment_subcategory_dim"]

    stations = {r["flowstation_id"] for r in flow}
    prod_stations = {r["flowstation_id"] for r in prod}
    wells = {r["productionstring"] for r in prod}
    cat_ids = {r["category_id"] for r in cats}
    sub_ids = {r["subcategory_id"] for r in subs}

    blank_cat = sum(1 for r in defer if not r["category_id"])
    blank_sub = sum(1 for r in defer if not r["subcategory_id"])
    warnings = []
    if blank_cat:
        warnings.append(f"{blank_cat} deferment rows have a blank category_id (expected in the real extract)")
    if blank_sub:
        warnings.append(f"{blank_sub} deferment rows have a blank subcategory_id (expected in the real extract)")

    checks = {
        "deferment_unknown_station": len({r["flowstation_id"] for r in defer} - stations),
        "deferment_unknown_category": len({r["category_id"] for r in defer} - cat_ids - {""}),
        "deferment_unknown_subcategory": len({r["subcategory_id"] for r in defer} - sub_ids - {""}),
        "deferment_unknown_well": len({r["productionstring"] for r in defer} - wells),
        "production_unknown_station": len(prod_stations - stations),
        "blank_category_rows": blank_cat,
        "blank_subcategory_rows": blank_sub,
    }
    for key, count in checks.items():
        if count and key not in ("blank_category_rows", "blank_subcategory_rows"):
            warnings.append(f"{key}: {count}")
    return {"checks": checks, "warnings": warnings}


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def write_output(
    out_dir: Path,
    tables: dict[str, tuple[list[str], list[dict]]],
    ref: dict[str, tuple[list[str], list[dict]]],
    meta: dict,
    days: int,
    end: dt.date,
) -> None:
    raw_dir = out_dir / "raw"
    ref_dir = out_dir / "ref"

    validation = validate(tables)
    for warning in validation["warnings"]:
        print(f"WARNING: {warning}", file=sys.stderr)
    for name, (fields, rows) in tables.items():
        write_table(raw_dir / f"{name}.csv", fields, rows)
    for name, (fields, rows) in ref.items():
        write_table(ref_dir / f"{name}.csv", fields, rows)

    files = {}
    for path in sorted(out_dir.rglob("*.csv")):
        files[str(path.relative_to(out_dir))] = {
            "rows": sum(1 for _ in path.open(encoding="utf-8")) - 1,
            "sha256": sha256(path),
        }

    manifest = {
        "environment": out_dir.name,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "days": days,
        "end_date": end.isoformat(),
        **meta,
        "validation": validation,
        "files": files,
    }
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    readme = f"""# Test data for `{out_dir.name}`

Generated {manifest['generated_at_utc']} from **{meta.get('source')}** data.
Range: last **{days} days** ending **{end.isoformat()}**.
Anonymised: **{meta.get('anonymised', False)}**.

This folder is git-ignored. Do not commit it.

## Upload into Fabric

1. Create lakehouse `lh_bronze` (or use your existing one).
2. In the lakehouse, open **Files**, create `raw/` and `ref/`.
3. Upload everything in `raw/` to `Files/raw/` and everything in `ref/` to `Files/ref/`.
4. Point the bronze ingestion notebook at:
   - `Files/raw/production_fact.csv`
   - `Files/raw/deferment_fact.csv`
   - `Files/raw/flowstations_dim.csv`
   - `Files/raw/deferment_category_dim.csv`
   - `Files/raw/deferment_subcategory_dim.csv`
   - `Files/ref/` for the small dictionary and price tables.

## Notes

- `deferment_fact.oil` is the **deferred** volume, not produced oil.
- `production_fact.target_oil` is per **string** in synthetic mode and in the
  real extract it repeats at station level; deduplicate before target maths.
- Missing values are left empty on purpose. Treat them as missing, not zero.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"Wrote {len(tables)} raw + {len(ref)} reference tables to {out_dir}")
    for name, info in files.items():
        print(f"  {name:<42} {info['rows']:>8} rows")
    print(f"  {'_manifest.json':<42} written")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate upload-ready seed/test data for a new Fabric environment."
    )
    ap.add_argument("--env", default="sandbox", help="environment/profile name (default: sandbox)")
    ap.add_argument("--out", help="output folder (default: test_data/<env>)")
    ap.add_argument("--days", type=int, default=180, help="number of trailing days (default: 180)")
    ap.add_argument(
        "--source", choices=["auto", "seed", "synthetic"], default="auto",
        help="seed = slice existing extracts; synthetic = generate from scratch (default: auto)",
    )
    ap.add_argument("--end", help="last date YYYY-MM-DD (default: today)")
    ap.add_argument("--seed", type=int, default=42, help="random seed for synthetic/price data")
    ap.add_argument("--anonymise", action="store_true", help="replace station/well/asset names")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output folder")
    args = ap.parse_args()

    if args.days < 7:
        raise SystemExit("--days must be at least 7.")

    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    out_dir = Path(args.out) if args.out else REPO / "test_data" / args.env
    out_dir = out_dir.resolve()

    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise SystemExit(f"{out_dir} already exists. Use --force to overwrite.")

    source = args.source
    if source == "auto":
        source = "seed" if all(find_source(k) for k in TABLES) else "synthetic"
        if source == "synthetic":
            print("No complete extract set found in data/; using synthetic data.")

    if source == "seed":
        try:
            tables, meta = seed_dataset(args.days, end, args.anonymise)
        except FileNotFoundError as exc:
            print(f"{exc}\nFalling back to synthetic data.", file=sys.stderr)
            tables, meta = synthetic_dataset(args.days, end, args.seed)
            source = "synthetic"
    else:
        tables, meta = synthetic_dataset(args.days, end, args.seed)

    ref = build_reference(tables, args.days, end, args.seed)
    write_output(out_dir, tables, ref, meta, args.days, end)

    print(f"\nMode: {source}. Environment: {args.env}. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
