#!/usr/bin/env python3
"""
parity_reference.py - clean-room pandas reference for the Fabric medallion build.

This is deliberately independent of Spark: it reads the same seed CSVs that were
uploaded to ``lh_bronze`` and re-implements nb_01 -> nb_05/nb_07 using pandas.
It exists so Slice 8 can compare Fabric output with a second implementation on
the same input window.

It is not the historical local prototype (that code is not in this repository).
It is a parity harness that follows the documented notebook rules.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# configuration copied from the notebooks
# ---------------------------------------------------------------------------
BASELINE_DAYS = 28
MIN_BASELINE_OBS = 14
MAD_TO_SIGMA = 1.4826
IQR_TO_SIGMA = 1.349
OUTLIER_Z = 3.0
DEVIATED_Z = 2.0
FLAT_Z = 0.5
CUSUM_K = 0.5
Z_CLIP = 25.0
WEEKDAY_SHRINK = 0.75

METRICS = [
    # name, source column, group, higher_is_bad, relative floor, absolute floor, label
    ("oil", "actual_oil", "production", False, 0.01, 25.0, "oil"),
    ("deferred_oil", "deferred_oil", "loss", True, 0.01, 25.0, "deferred oil"),
    ("deferment_pct", "deferment_pct", "loss", True, 0.001, 0.01, "deferment %"),
    ("target_gap_pct", "target_gap_pct", "production", True, 0.001, 0.02, "gap to target"),
    ("uptime", "uptime_avg", "process", False, 0.01, 0.5, "uptime"),
    ("thp", "thp_avg", "process", False, 0.001, 5.0, "THP"),
    ("bean", "bean_avg", "process", False, 0.001, 1.0, "bean/choke"),
    ("water_cut", "water_rf_avg", "process", True, 0.001, 0.01, "water cut"),
]
METRIC_NAMES = [m[0] for m in METRICS]
METRIC_META = {
    m[0]: {
        "column": m[1],
        "group": m[2],
        "higher_is_bad": m[3],
        "floor_ratio": m[4],
        "min_scale": m[5],
        "label": m[6],
    }
    for m in METRICS
}
CORE_METRICS = ["oil", "uptime", "thp", "bean", "water_cut", "deferment_pct"]

# nb_04 rules
RULESET_VERSION = "risk-rules-v1"
WEIGHTS = {
    "deferment_pct": 0.25,
    "oil": 0.20,
    "uptime": 0.15,
    "deferred_oil": 0.10,
    "target_gap_pct": 0.10,
    "thp": 0.10,
    "water_cut": 0.05,
    "bean": 0.05,
}
BAD_Z_CAP = 6.0
RISK_FLOOR = 0.5
SCORE_SCALE = 2.0
# nb_04 iterates METRICS in this order, which decides ties when two signals have
# the same absolute z (e.g. both capped at 25). Keep it separate from nb_03's
# METRIC_NAMES order (oil first).
RISK_METRIC_ORDER = [
    "deferment_pct", "oil", "uptime", "deferred_oil",
    "target_gap_pct", "thp", "water_cut", "bean",
]
PRIMARY_SIGNALS = ["oil", "deferment_pct", "deferred_oil", "thp"]
PRIMARY_SIGNAL_MIN_Z = 1.5
AMBER_SCORE = 0.40
AMBER_PERSIST_SCORE = 0.30
AMBER_VALUE_USD = 50_000
AMBER_SIGNAL_Z = 1.4
AMBER_SIGNAL_RUN = 3
RED_SCORE = 0.70
RED_PERSIST_SCORE = 0.55
RED_VALUE_USD = 250_000
COOLDOWN_DAYS = 3

HORIZON_DAYS = 7
QUIET_DAYS = 3

# `sheet` constants
COMPUTED_AT = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, **kwargs)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _long(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _bool(series: pd.Series) -> pd.Series:
    # Spark casts "true"/"false"/1/0 strings; CSV values are 0/1 or True/False.
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(("true", "1", "1.0"))


def _write_silver(name: str, df: pd.DataFrame, silver: dict[str, pd.DataFrame]) -> None:
    silver[name] = df


# ---------------------------------------------------------------------------
# nb_01 / nb_02: silver
# ---------------------------------------------------------------------------
def build_silver(input_root: Path) -> dict[str, pd.DataFrame]:
    raw = input_root / "raw"
    ref = input_root / "ref"
    out: dict[str, pd.DataFrame] = {}

    # bronze tables ---------------------------------------------------------
    production = _read_csv(raw / "production_fact.csv")
    deferment = _read_csv(raw / "deferment_fact.csv")
    cat = _read_csv(raw / "deferment_category_dim.csv")
    sub = _read_csv(raw / "deferment_subcategory_dim.csv")

    dim_station = _read_csv(ref / "dim_station.csv")
    dim_date = _read_csv(ref / "dim_date.csv")
    dim_well = _read_csv(ref / "dim_well.csv")
    oil_prices = _read_csv(ref / "oil_prices.csv")
    owner_map = _read_csv(ref / "owner_map.csv")

    stations_all = pd.DataFrame(
        {
            "flowstation_id": _long(dim_station["flowstation_id"]),
            "station_name": dim_station["flowstation"].astype("string"),
            "asset_id": _long(dim_station["asset_id"]),
            "asset": dim_station["asset"].astype("string"),
        }
    )
    stations_join = stations_all[["flowstation_id", "station_name", "asset"]]
    _write_silver("dim_station", stations_all, out)

    # production_day --------------------------------------------------------
    p = production.copy()
    p["production_id"] = _long(p["production_id"])
    p["asset_id"] = _long(p["asset_id"])
    p["flowstation_id"] = _long(p["flowstation_id"])
    p["reservoir_id"] = _long(p["reservoir_id"])
    p["date_id"] = _long(p["date_id"])
    p["productionstring"] = p["productionstring"].astype("string").str.strip()
    p["status"] = p["status"].astype("string").str.strip()
    for c in ["gas", "gross", "oil", "target_oil", "uptimeproduction", "water", "water_rf", "thp", "bean"]:
        p[c] = _num(p[c])
    p["production_date"] = _date(p["production_date"])
    p = p.rename(columns={"uptimeproduction": "uptime_hrs"})
    p = p[["production_id", "asset_id", "flowstation_id", "reservoir_id", "date_id",
           "productionstring", "status", "gas", "gross", "oil", "target_oil",
           "uptime_hrs", "water", "water_rf", "thp", "bean", "production_date"]]

    # Spark Window.row_number over equal ingestion timestamps: no duplicate ids
    # exist in the seed, so dedupe is a no-op here but kept for fidelity.
    p = p.drop_duplicates("production_id", keep="last")

    # max target_oil over the station-day (Spark max ignores nulls)
    p["station_target_oil"] = p.groupby(["flowstation_id", "production_date"], dropna=False)["target_oil"].transform("max")
    p = p.merge(stations_join, on="flowstation_id", how="left")
    _write_silver("production_day", p, out)

    # deferment_event -------------------------------------------------------
    d = deferment.copy()
    d["deferment_id"] = _long(d["deferment_id"])
    d["asset_id"] = _long(d["asset_id"])
    d["flowstation_id"] = _long(d["flowstation_id"])
    d["reservoir_id"] = _long(d["reservoir_id"])
    d["date_id"] = _long(d["date_id"])
    d["category_id"] = _long(d["category_id"])
    d["subcategory_id"] = _long(d["subcategory_id"])
    d["productionstring"] = d["productionstring"].astype("string").str.strip()
    d["status"] = d["status"].astype("string").str.strip()
    for c, new in [("gross", "deferred_gross"), ("water", "deferred_water"),
                   ("oil", "deferred_oil"), ("gas", "deferred_gas")]:
        d[new] = _num(d[c])
    d["event_date"] = _date(d["date"])
    d = d[["deferment_id", "asset_id", "flowstation_id", "reservoir_id", "date_id",
           "category_id", "subcategory_id", "productionstring", "status",
           "deferred_gross", "deferred_water", "deferred_oil", "deferred_gas",
           "event_date"]]
    d = d.drop_duplicates("deferment_id", keep="last")

    c = pd.DataFrame({"category_id": _long(cat["category_id"]), "cause_group": cat["category"].astype("string")})
    s = pd.DataFrame({"subcategory_id": _long(sub["subcategory_id"]), "cause_code": sub["sub_category"].astype("string")})
    d = d.merge(c, on="category_id", how="left").merge(s, on="subcategory_id", how="left")
    d["cause_group"] = d["cause_group"].fillna("Unknown")
    d["cause_code"] = d["cause_code"].fillna("Unknown")
    d["is_coded"] = d["subcategory_id"].notna() & ~d["cause_code"].str.lower().isin(["mismatch", "unknown"])
    d = d.merge(stations_join, on="flowstation_id", how="left").rename(columns={"flowstation_id": "station_id"})
    _write_silver("deferment_event", d, out)

    # station_day -----------------------------------------------------------
    prod_agg = (
        p.groupby(["flowstation_id", "production_date"], dropna=False)
        .agg(
            actual_oil=("oil", "sum"),
            target_oil=("station_target_oil", "max"),
            actual_gas=("gas", "sum"),
            actual_water=("water", "sum"),
            actual_gross=("gross", "sum"),
            uptime_avg=("uptime_hrs", "mean"),
            thp_avg=("thp", "mean"),
            bean_avg=("bean", "mean"),
            water_rf_avg=("water_rf", "mean"),
            wells_total=("productionstring", "nunique"),
            wells_producing=("productionstring", lambda x: x[p.loc[x.index, "oil"] > 0].nunique()),
        )
        .reset_index()
        .rename(columns={"production_date": "date"})
    )

    defer_agg = (
        d.groupby(["station_id", "event_date"], dropna=False)
        .agg(
            deferred_oil=("deferred_oil", "sum"),
            event_count=("deferment_id", "size"),
            coded_event_count=("is_coded", "sum"),
        )
        .reset_index()
        .rename(columns={"station_id": "flowstation_id", "event_date": "date"})
    )
    # Spark `sum(bool)` is a count of true values; keep integer like Spark.
    defer_agg["coded_event_count"] = defer_agg["coded_event_count"].astype("Int64")

    sd = prod_agg.merge(defer_agg, on=["flowstation_id", "date"], how="outer")
    fill_zero = [
        "actual_oil", "deferred_oil", "actual_gas", "actual_water", "actual_gross",
        "uptime_avg", "thp_avg", "bean_avg", "water_rf_avg",
        "wells_total", "wells_producing", "event_count", "coded_event_count",
    ]
    for col in fill_zero:
        sd[col] = pd.to_numeric(sd[col], errors="coerce").fillna(0)

    sd["potential_oil"] = sd["actual_oil"] + sd["deferred_oil"]
    sd["deferment_pct"] = np.where(sd["potential_oil"] > 0, sd["deferred_oil"] / sd["potential_oil"], np.nan)
    sd["target_gap"] = np.where(sd["target_oil"].notna(), sd["target_oil"] - sd["actual_oil"], np.nan)
    sd["target_gap_pct"] = np.where(sd["target_oil"] > 0, sd["target_gap"] / sd["target_oil"], np.nan)
    sd = sd.merge(stations_join, on="flowstation_id", how="left").rename(columns={"flowstation_id": "station_id"})
    _write_silver("station_day", sd, out)

    # deferment_episode -----------------------------------------------------
    ev = d[["station_id", "productionstring", "cause_code", "cause_group",
            "event_date", "deferred_oil", "is_coded"]].copy()
    ev["station_id"] = ev["station_id"].astype("Int64")
    ev = ev.sort_values(["station_id", "productionstring", "cause_code", "event_date"], kind="mergesort").reset_index(drop=True)
    g = ev.groupby(["station_id", "productionstring", "cause_code"], dropna=False, sort=False)
    ev["prev_date"] = g["event_date"].shift(1)
    ev["is_new"] = (ev["prev_date"].isna() | ((ev["event_date"] - ev["prev_date"]).dt.days > 1)).astype(int)
    ev["episode_seq"] = ev.groupby(["station_id", "productionstring", "cause_code"], dropna=False, sort=False)["is_new"].cumsum()

    ep = (
        ev.groupby(["station_id", "productionstring", "cause_code", "cause_group", "episode_seq"], dropna=False)
        .agg(
            episode_start=("event_date", "min"),
            episode_end=("event_date", "max"),
            event_count=("deferment_id" if "deferment_id" in ev.columns else "event_date", "size"),
            deferred_oil=("deferred_oil", "sum"),
            has_coded_event=("is_coded", "max"),
        )
        .reset_index()
    )
    ep["duration_days"] = (ep["episode_end"] - ep["episode_start"]).dt.days + 1
    ep["has_coded_event"] = ep["has_coded_event"].astype(bool)
    ep["episode_id"] = (
        ep["station_id"].astype(str) + "|" + ep["productionstring"].astype(str) + "|"
        + ep["cause_code"].astype(str) + "|" + ep["episode_seq"].astype(str)
    )
    ep = ep.drop(columns=["episode_seq"])
    _write_silver("deferment_episode", ep, out)

    # reference dimensions --------------------------------------------------
    _write_silver("dim_date", pd.DataFrame({
        "date_id": _long(dim_date["date_id"]),
        "date": _date(dim_date["date"]),
        "year": _long(dim_date["year"]),
        "month": _long(dim_date["month"]),
        "day": _long(dim_date["day"]),
        "weekday": dim_date["weekday"].astype("string"),
        "is_weekend": _bool(dim_date["is_weekend"]),
    }), out)

    _write_silver("dim_well", pd.DataFrame({
        "productionstring": dim_well["productionstring"].astype("string"),
        "flowstation_id": _long(dim_well["flowstation_id"]),
        "asset_id": _long(dim_well["asset_id"]),
    }), out)
    _write_silver("dim_cause_group", pd.DataFrame({
        "cause_group_id": _long(cat["category_id"]),
        "cause_group": cat["category"].astype("string"),
    }), out)
    _write_silver("dim_cause_code", pd.DataFrame({
        "cause_code_id": _long(sub["subcategory_id"]),
        "cause_code": sub["sub_category"].astype("string"),
        "is_usable": ~sub["sub_category"].astype("string").str.lower().isin(["mismatch", "unknown"]),
    }), out)
    _write_silver("oil_prices", pd.DataFrame({
        "date": _date(oil_prices["date"]),
        "oil_price_usd": _num(oil_prices["oil_price_usd"]),
    }), out)
    _write_silver("owner_map", pd.DataFrame({
        "station_id": _long(owner_map["flowstation_id"]),
        "station_name": owner_map["flowstation"].astype("string"),
        "asset": owner_map["asset"].astype("string"),
        "owner_name": owner_map["owner_name"].astype("string"),
        "owner_upn": owner_map["owner_upn"].astype("string"),
    }), out)

    return out


# ---------------------------------------------------------------------------
# nb_03: baselines, features, deviations
# ---------------------------------------------------------------------------
def _robust_scale(vals: pd.Series, floor_ratio: float, min_scale: float) -> float:
    med = float(vals.median())
    mad = float((vals - med).abs().median())
    q25, q75 = float(vals.quantile(0.25)), float(vals.quantile(0.75))
    return max(
        MAD_TO_SIGMA * mad,
        (q75 - q25) / IQR_TO_SIGMA,
        abs(med) * floor_ratio,
        min_scale,
    )


def _slope_7(y) -> float:
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    if mask.sum() < 4:
        return np.nan
    return float(np.polyfit(np.arange(len(y))[mask], y[mask], 1)[0])


def _add_cusum(z: pd.Series, observed: pd.Series, k: float = CUSUM_K):
    pos, neg = [], []
    cp = cn = 0.0
    for zv, obs in zip(z.to_numpy(), observed.to_numpy()):
        if obs and pd.notna(zv):
            cp = max(0.0, cp + zv - k)
            cn = max(0.0, cn - zv - k)
        pos.append(cp if obs else np.nan)
        neg.append(cn if obs else np.nan)
    return pos, neg


def _reason_text(row, name: str) -> str:
    z = row[f"z_{name}"]
    direction = row[f"dir_{name}"]
    if pd.isna(z) or direction in ("", "flat"):
        return ""
    expected = row[f"expected_{name}"]
    value = row[METRIC_META[name]["column"]]
    change = ""
    if pd.notna(expected) and pd.notna(value):
        if name in {"deferment_pct", "water_cut", "target_gap_pct"} and abs(value - expected) >= 0.0005:
            change = f"{abs(value - expected) * 100:.0f}pp "
        elif abs(expected) > 1e-12:
            change = f"{abs(value - expected) / abs(expected) * 100:.0f}% "
    return f"{METRIC_META[name]['label']} {change}{direction} its normal (z={z:+.1f})"


def build_gold_features(silver: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    stations = silver["dim_station"][["flowstation_id", "station_name", "asset"]].rename(columns={"flowstation_id": "station_id"})
    dates = silver["dim_date"][["date", "weekday", "is_weekend"]]
    sd_cols = [
        "station_id", "date", "actual_oil", "target_oil", "actual_gas", "actual_water",
        "actual_gross", "uptime_avg", "thp_avg", "bean_avg", "water_rf_avg",
        "wells_total", "wells_producing", "deferred_oil", "event_count",
        "coded_event_count", "potential_oil", "deferment_pct", "target_gap", "target_gap_pct",
    ]
    sd = silver["station_day"][sd_cols].copy()
    sd["is_observed"] = True
    prices = silver["oil_prices"][["date", "oil_price_usd"]]
    owners = silver["owner_map"][["station_id", "owner_name", "owner_upn"]]

    grid = stations.merge(dates, how="cross").merge(sd, on=["station_id", "date"], how="left")
    grid = grid.merge(prices, on="date", how="left").merge(owners, on="station_id", how="left")
    grid["is_observed"] = grid["is_observed"].fillna(False).astype(bool)
    grid["weekday_num"] = ((grid["date"].dt.dayofweek) % 7).astype(int)  # Monday=0
    grid = grid.sort_values(["station_id", "date"]).reset_index(drop=True)

    date_values = np.sort(grid["date"].unique())
    est_start = pd.Timestamp(date_values[0])
    est_end = pd.Timestamp(date_values[min(BASELINE_DAYS, len(date_values)) - 1])
    baseline_version = f"gold-v1-{est_end:%Y%m%d}"

    baseline_rows = []
    for sid, sdf in grid[grid["is_observed"]].groupby("station_id"):
        est = sdf[(sdf["date"] >= est_start) & (sdf["date"] <= est_end)]
        station_name = sdf["station_name"].dropna().iloc[0] if sdf["station_name"].notna().any() else ""
        for name, meta in METRIC_META.items():
            col = meta["column"]
            usable = est[est[col].notna()]
            vals = usable[col]
            med = float(vals.median()) if len(vals) else np.nan
            scale = _robust_scale(vals, meta["floor_ratio"], meta["min_scale"]) if len(vals) else np.nan
            weekday_expected = {}
            for wd in range(7):
                wv = usable.loc[usable["weekday_num"] == wd, col]
                wm = float(wv.median()) if len(wv) else np.nan
                weekday_expected[wd] = (
                    WEEKDAY_SHRINK * wm + (1 - WEEKDAY_SHRINK) * med
                    if pd.notna(wm) and pd.notna(med) else med
                )
            finite_wd = [v for v in weekday_expected.values() if pd.notna(v)]
            spread = (max(finite_wd) / min(finite_wd)) if finite_wd and min(finite_wd) > 0 else np.nan
            row = {
                "entity_type": "station",
                "entity_id": int(sid),
                "entity_name": station_name,
                "metric": name,
                "metric_group": meta["group"],
                "higher_is_bad": bool(meta["higher_is_bad"]),
                "baseline_version": baseline_version,
                "estimation_start": est_start.date(),
                "estimation_end": est_end.date(),
                "n_obs": int(len(vals)),
                "median": med,
                "mad": float((vals - med).abs().median()) if len(vals) else np.nan,
                "robust_scale": scale,
                "mean": float(vals.mean()) if len(vals) else np.nan,
                "stddev": float(vals.std(ddof=0)) if len(vals) > 1 else np.nan,
                "p10": float(vals.quantile(0.10)) if len(vals) else np.nan,
                "p90": float(vals.quantile(0.90)) if len(vals) else np.nan,
                "min_value": float(vals.min()) if len(vals) else np.nan,
                "max_value": float(vals.max()) if len(vals) else np.nan,
                "seasonal_spread": spread,
                "computed_at_utc": COMPUTED_AT,
            }
            for wd in range(7):
                row[f"weekday_expected_{wd}"] = weekday_expected[wd]
            baseline_rows.append(row)
    baseline = pd.DataFrame(baseline_rows)
    out["gold_entity_baseline"] = baseline

    base = baseline.set_index(["entity_id", "metric"])
    feature_frames = []
    for sid, sdf in grid.groupby("station_id"):
        s = sdf.sort_values("date").copy().reset_index(drop=True)
        s["baseline_phase"] = np.where(s["date"] <= est_end, "estimation", "scored")
        for name, meta in METRIC_META.items():
            col = meta["column"]
            b = base.loc[(sid, name)]
            med, scale = b["median"], b["robust_scale"]
            s[f"expected_{name}"] = [
                b[f"weekday_expected_{int(wd)}"] if pd.notna(b[f"weekday_expected_{int(wd)}"]) else med
                for wd in s["weekday_num"]
            ]
            s[f"dev_{name}"] = s[col] - s[f"expected_{name}"]
            s[f"z_{name}"] = (s[f"dev_{name}"] / scale).clip(-Z_CLIP, Z_CLIP) if pd.notna(scale) and scale > 0 else np.nan
            s[f"pct_dev_{name}"] = s[f"dev_{name}"] / s[f"expected_{name}"].abs().replace(0, np.nan)
            s[f"dir_{name}"] = np.select(
                [s[f"z_{name}"].isna(), s[f"z_{name}"].abs() < FLAT_Z, s[f"z_{name}"] > 0],
                ["", "flat", "above"],
                default="below",
            )
            s[f"outlier_{name}"] = s[f"z_{name}"].abs() >= OUTLIER_Z
            s[f"missing_{name}"] = s[col].isna() & s["is_observed"]

        for name in CORE_METRICS:
            col = METRIC_META[name]["column"]
            v = s[col]
            s[f"{name}_lag_1"] = v.shift(1)
            s[f"{name}_lag_7"] = v.shift(7)
            s[f"{name}_delta_1"] = v - s[f"{name}_lag_1"]
            s[f"{name}_delta_7"] = v - s[f"{name}_lag_7"]
            s[f"{name}_roll_mean_7"] = v.shift(1).rolling(7, min_periods=3).mean()
            s[f"{name}_roll_std_7"] = v.shift(1).rolling(7, min_periods=3).std(ddof=0)
            s[f"{name}_roll_mean_28"] = v.shift(1).rolling(28, min_periods=7).mean()
            s[f"{name}_ewma_7_prev"] = v.ewm(span=7, adjust=False, min_periods=3).mean().shift(1)
            s[f"{name}_slope_7"] = v.rolling(7, min_periods=4).apply(_slope_7, raw=True)
            cpos, cneg = _add_cusum(s[f"z_{name}"], s["is_observed"])
            s[f"{name}_cusum_pos"] = cpos
            s[f"{name}_cusum_neg"] = cneg

        zcols = [f"z_{n}" for n in METRIC_NAMES]
        absz = s[zcols].abs()
        s["deviation_score"] = absz.max(axis=1)
        s["signals_deviated"] = (absz >= DEVIATED_Z).sum(axis=1).astype(int)

        def top_signal(row):
            pairs = [(row[f"z_{n}"], n) for n in METRIC_NAMES if pd.notna(row[f"z_{n}"])]
            if not pairs:
                return "", np.nan, ""
            z, n = max(pairs, key=lambda t: abs(t[0]))
            return n, z, row[f"dir_{n}"]

        tops = s.apply(top_signal, axis=1, result_type="expand")
        s["top_signal"] = tops[0]
        s["top_signal_z"] = tops[1]
        s["top_signal_direction"] = tops[2]

        def signals_json(row):
            items = []
            for n in METRIC_NAMES:
                z = row[f"z_{n}"]
                if pd.isna(z) or row[f"dir_{n}"] in ("", "flat"):
                    continue
                items.append({
                    "metric": n,
                    "label": METRIC_META[n]["label"],
                    "z": round(float(z), 2),
                    "direction": row[f"dir_{n}"],
                    "value": None if pd.isna(row[METRIC_META[n]["column"]]) else float(row[METRIC_META[n]["column"]]),
                    "expected": None if pd.isna(row[f"expected_{n}"]) else float(row[f"expected_{n}"]),
                })
            items.sort(key=lambda x: abs(x["z"]), reverse=True)
            return json.dumps(items[:5])

        def reasons_text(row):
            parts = []
            for n in METRIC_NAMES:
                z = row[f"z_{n}"]
                if pd.notna(z) and abs(z) >= 1.5:
                    txt = _reason_text(row, n)
                    if txt:
                        parts.append((abs(z), txt))
            parts.sort(reverse=True, key=lambda t: t[0])
            return "; ".join(t for _, t in parts[:3])

        s["signals_json"] = s.apply(signals_json, axis=1)
        s["top_reasons"] = s.apply(reasons_text, axis=1)

        price = s["oil_price_usd"]
        s["deferred_value_usd"] = s["deferred_oil"] * price
        s["potential_value_usd"] = s["potential_oil"] * price
        s["target_gap_value_usd"] = s["target_gap"] * price
        for c in ["deferred_oil", "deferred_value_usd"]:
            s[f"{c}_roll_mean_7"] = s[c].shift(1).rolling(7, min_periods=3).mean()
            s[f"{c}_roll_sum_7"] = s[c].shift(1).rolling(7, min_periods=3).sum()
        s["event_count_roll_sum_7"] = s["event_count"].shift(1).rolling(7, min_periods=3).sum()
        s["coded_event_count_roll_sum_7"] = s["coded_event_count"].shift(1).rolling(7, min_periods=3).sum()
        s["baseline_version"] = baseline_version
        s["feature_version"] = "gold-features-v1"
        s["computed_at_utc"] = COMPUTED_AT
        feature_frames.append(s)

    features = pd.concat(feature_frames, ignore_index=True)
    for c in ["top_signal", "top_signal_direction", "top_reasons", "weekday", "asset",
              "station_name", "owner_name", "owner_upn"]:
        if c in features.columns:
            features[c] = features[c].fillna("").astype(str)
    out["gold_entity_day_features"] = features

    dev_frames = []
    for name, meta in METRIC_META.items():
        col = meta["column"]
        tmp = features.loc[features["is_observed"]].copy()
        tmp = tmp.loc[tmp[col].notna()]
        tmp["metric"] = name
        tmp["value"] = tmp[col]
        tmp["metric_group"] = meta["group"]
        tmp["higher_is_bad"] = bool(meta["higher_is_bad"])
        dev_frames.append(tmp.loc[:, [
            "station_id", "station_name", "date", "metric", "metric_group",
            "higher_is_bad", "value", f"expected_{name}", f"dev_{name}",
            f"pct_dev_{name}", f"z_{name}", f"dir_{name}", f"outlier_{name}",
            "baseline_version", "baseline_phase",
        ]].rename(columns={
            f"expected_{name}": "expected",
            f"dev_{name}": "deviation",
            f"pct_dev_{name}": "pct_deviation",
            f"z_{name}": "robust_z",
            f"dir_{name}": "direction",
            f"outlier_{name}": "is_outlier",
        }))
    deviations = pd.concat(dev_frames, ignore_index=True)
    deviations["entity_type"] = "station"
    deviations["entity_id"] = deviations["station_id"]
    deviations["entity_name"] = deviations["station_name"]
    deviations["magnitude"] = deviations["robust_z"].abs()
    deviations = deviations[[
        "entity_type", "entity_id", "entity_name", "date", "metric", "metric_group",
        "higher_is_bad", "value", "expected", "deviation", "pct_deviation",
        "robust_z", "magnitude", "direction", "is_outlier",
        "baseline_version", "baseline_phase",
    ]]
    out["gold_deviation_daily"] = deviations
    return out


# ---------------------------------------------------------------------------
# nb_04: risk and alerts
# ---------------------------------------------------------------------------
def build_gold_risk(features: pd.DataFrame, baseline: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risk = features.copy()
    base = baseline.loc[baseline["metric"] == "deferment_pct", ["entity_id", "median", "p90"]].rename(
        columns={"entity_id": "station_id", "median": "baseline_defpct", "p90": "baseline_defpct_p90"}
    )
    risk = risk.merge(base, on="station_id", how="left")
    risk["baseline_defpct"] = risk["baseline_defpct"].fillna(0.0)
    risk["baseline_defpct_p90"] = risk["baseline_defpct_p90"].fillna(risk["baseline_defpct"])
    risk = risk.sort_values(["station_id", "date"]).reset_index(drop=True)

    eligible = risk["is_observed"] & (risk["baseline_phase"] == "scored")
    bad_matrix = {}
    for m, meta in METRIC_META.items():
        z = risk[f"z_{m}"].fillna(0.0)
        bad = np.maximum(0.0, z) if meta["higher_is_bad"] else np.maximum(0.0, -z)
        bad_matrix[m] = np.minimum(bad, BAD_Z_CAP)
    weighted = sum(WEIGHTS[m] * bad_matrix[m] for m in METRIC_META)
    max_bad = np.maximum.reduce([bad_matrix[m] for m in METRIC_META])
    primary_bad = np.maximum.reduce([bad_matrix[m] for m in PRIMARY_SIGNALS])

    risk["max_bad_z"] = np.where(eligible, max_bad, np.nan)
    risk["primary_bad_z"] = np.where(eligible, primary_bad, np.nan)
    risk["weighted_severity"] = np.where(eligible, weighted, np.nan)
    raw_score = 1.0 - np.exp(-np.maximum(0.0, weighted - RISK_FLOOR) / SCORE_SCALE)
    risk["risk_score"] = np.where(eligible, raw_score, np.nan)
    risk["risk_signals"] = np.where(eligible, sum((bad_matrix[m] >= 1.0).astype(int) for m in METRIC_META), 0)

    persistence_days, signal_run = [], []
    current_score_run, current_signal_run = {}, {}
    for _, row in risk.iterrows():
        sid = row["station_id"]
        if not row["is_observed"] or row["baseline_phase"] != "scored":
            current_score_run[sid] = 0
            current_signal_run[sid] = 0
            persistence_days.append(0)
            signal_run.append(0)
            continue
        current_score_run[sid] = current_score_run.get(sid, 0) + 1 if row["risk_score"] >= 0.35 else 0
        current_signal_run[sid] = current_signal_run.get(sid, 0) + 1 if row["max_bad_z"] >= AMBER_SIGNAL_Z else 0
        persistence_days.append(current_score_run[sid])
        signal_run.append(current_signal_run[sid])
    risk["persistence_days"] = persistence_days
    risk["signal_run"] = signal_run

    severity = np.clip((risk["weighted_severity"].fillna(0.0) - RISK_FLOOR) / (BAD_Z_CAP - RISK_FLOOR), 0.0, 1.0)
    expected_rate = risk["baseline_defpct"] + (
        np.maximum(risk["baseline_defpct_p90"], risk["baseline_defpct"]) - risk["baseline_defpct"]
    ) * severity
    expected_rate = np.maximum.reduce([
        expected_rate.to_numpy(),
        risk["deferment_pct"].fillna(0.0).to_numpy(),
        risk["deferment_pct_roll_mean_7"].fillna(0.0).to_numpy(),
    ])
    risk["predicted_deferment_pct"] = np.clip(expected_rate, 0.0, 1.0)
    risk["exp_deferred_bbl"] = risk["potential_oil"] * risk["predicted_deferment_pct"]
    risk["exp_excess_bbl"] = risk["potential_oil"] * np.maximum(0.0, risk["predicted_deferment_pct"] - risk["baseline_defpct"])
    risk["exp_usd"] = risk["exp_excess_bbl"] * risk["oil_price_usd"]
    cols = ["predicted_deferment_pct", "exp_deferred_bbl", "exp_excess_bbl", "exp_usd"]
    risk.loc[~risk["is_observed"], cols] = np.nan

    def reason_text(row, m: str) -> str:
        z = row[f"z_{m}"]
        if pd.isna(z):
            return ""
        meta = METRIC_META[m]
        if (z > 0) != meta["higher_is_bad"] or z == 0:
            return ""
        value = row[meta["column"]]
        expected = row[f"expected_{m}"]
        change = ""
        if pd.notna(value) and pd.notna(expected):
            delta = abs(value - expected)
            if m in {"deferment_pct", "water_cut", "target_gap_pct"} and delta >= 0.0005:
                change = f"{delta * 100:.0f}pp "
            elif abs(expected) > 1e-9:
                pct = delta / abs(expected) * 100
                change = f"{pct:.0f}% " if pct < 1000 else ">999% "
        direction = "above" if z > 0 else "below"
        return f"{meta['label']} {change}{direction} its normal (z={z:+.1f})"

    def reasons_for_row(row):
        items = []
        for m in RISK_METRIC_ORDER:
            z = row[f"z_{m}"]
            if pd.isna(z):
                continue
            meta = METRIC_META[m]
            is_bad = (z > 0) == meta["higher_is_bad"] and z != 0
            if not is_bad or abs(z) < 1.0:
                continue
            text = reason_text(row, m)
            if text:
                items.append({
                    "metric": m,
                    "label": meta["label"],
                    "z": round(float(z), 2),
                    "direction": "above" if z > 0 else "below",
                    "value": None if pd.isna(row[meta["column"]]) else float(row[meta["column"]]),
                    "expected": None if pd.isna(row[f"expected_{m}"]) else float(row[f"expected_{m}"]),
                    "text": text,
                })
        items.sort(key=lambda x: abs(x["z"]), reverse=True)
        return items

    reasons_json, reasons_text, top_risk_signal, top_risk_z = [], [], [], []
    for _, row in risk.iterrows():
        items = reasons_for_row(row) if row["is_observed"] and row["baseline_phase"] == "scored" else []
        reasons_json.append(json.dumps(items[:5]))
        reasons_text.append("; ".join(i["text"] for i in items[:3]))
        if items:
            top_risk_signal.append(items[0]["metric"])
            top_risk_z.append(items[0]["z"])
        else:
            top_risk_signal.append("")
            top_risk_z.append(np.nan)
    risk["risk_reasons_json"] = reasons_json
    risk["risk_reasons"] = reasons_text
    risk["top_risk_signal"] = top_risk_signal
    risk["top_risk_z"] = top_risk_z
    risk["risk_direction"] = np.select(
        [~eligible, risk["max_bad_z"] >= 1.0, risk["max_bad_z"].isna()],
        ["not_scored", "deteriorating", "unknown"],
        default="stable",
    )

    def assign_tier(row) -> str:
        if not row["is_observed"]:
            return "NoData"
        if row["baseline_phase"] != "scored":
            return "Unscored"
        score = row["risk_score"]
        if pd.isna(score):
            return "NoData"
        exp_usd = 0.0 if pd.isna(row["exp_usd"]) else row["exp_usd"]
        mbz = 0.0 if pd.isna(row["max_bad_z"]) else row["max_bad_z"]
        if (
            score >= RED_SCORE
            or (score >= RED_PERSIST_SCORE and row["persistence_days"] >= 2)
            or (mbz >= 6 and row["signal_run"] >= 3 and score >= 0.45)
            or (exp_usd >= RED_VALUE_USD and score >= 0.30)
        ):
            return "Red"
        if (
            score >= AMBER_SCORE
            or (score >= AMBER_PERSIST_SCORE and row["persistence_days"] >= 2)
            or (mbz >= AMBER_SIGNAL_Z and row["signal_run"] >= AMBER_SIGNAL_RUN and row["primary_bad_z"] >= PRIMARY_SIGNAL_MIN_Z)
            or (exp_usd >= AMBER_VALUE_USD and score >= 0.20)
        ):
            return "Amber"
        return "Green"

    risk["risk_tier"] = risk.apply(assign_tier, axis=1)

    tier_rank = {"Green": 0, "Amber": 1, "Red": 2}
    alerts = []
    alert_action, suppression_reason = [], []
    prev_tier, last_alert_date, last_alert_tier = {}, {}, {}
    for _, row in risk.iterrows():
        sid = row["station_id"]
        tier = row["risk_tier"]
        if tier not in tier_rank:
            alert_action.append("None")
            suppression_reason.append("not_eligible")
            continue
        current_rank = tier_rank[tier]
        previous = prev_tier.get(sid, "Green")
        previous_rank = tier_rank[previous]
        action, suppress = "None", ""
        if current_rank > previous_rank:
            fire = True
            if sid in last_alert_date:
                days_since = (row["date"] - last_alert_date[sid]).days
                escalation = tier == "Red" and last_alert_tier.get(sid) == "Amber"
                if days_since < COOLDOWN_DAYS and not escalation:
                    fire = False
                    suppress = "cooldown"
            if fire:
                alert_date = row["date"].date()
                alert_key = f"{sid}|{alert_date}|{tier}|{RULESET_VERSION}"
                alert_id = hashlib.md5(alert_key.encode("utf-8")).hexdigest()[:16]
                alert_type = "escalated_to_red" if previous == "Amber" else ("entered_red" if tier == "Red" else "entered_amber")
                alerts.append({
                    "alert_id": alert_id,
                    "alert_key": alert_key,
                    "station_id": sid,
                    "station_name": row["station_name"],
                    "asset": row["asset"],
                    "owner_name": row["owner_name"],
                    "owner_upn": row["owner_upn"],
                    "alert_date": alert_date,
                    "tier": tier,
                    "previous_tier": previous,
                    "alert_type": alert_type,
                    "risk_score": float(row["risk_score"]),
                    "risk_reasons": row["risk_reasons"],
                    "risk_reasons_json": row["risk_reasons_json"],
                    "top_signal": row["top_risk_signal"],
                    "top_signal_z": None if pd.isna(row["top_risk_z"]) else float(row["top_risk_z"]),
                    "persistence_days": int(row["persistence_days"]),
                    "signal_run": int(row["signal_run"]),
                    "exp_deferred_bbl": None if pd.isna(row["exp_deferred_bbl"]) else float(row["exp_deferred_bbl"]),
                    "exp_usd": None if pd.isna(row["exp_usd"]) else float(row["exp_usd"]),
                    "ruleset_version": RULESET_VERSION,
                    "baseline_version": row["baseline_version"],
                    "fired_at_utc": COMPUTED_AT,
                    "alert_status": "New",
                    "notification_channel": "Teams",
                    "notification_target": row["owner_upn"],
                })
                action = "Fired"
                last_alert_date[sid] = row["date"]
                last_alert_tier[sid] = tier
            else:
                action = "Suppressed"
        elif current_rank == previous_rank:
            if tier in ("Amber", "Red"):
                action, suppress = "Suppressed", "no_change"
        else:
            action, suppress = "Suppressed", "de_escalation"
        alert_action.append(action)
        suppression_reason.append(suppress)
        prev_tier[sid] = tier

    risk["alert_action"] = alert_action
    risk["suppression_reason"] = suppression_reason
    risk["alert_eligible"] = risk["risk_tier"].isin(["Amber", "Red"])
    risk["is_latest_date"] = risk["date"] == risk["date"].max()
    alerts_df = pd.DataFrame(alerts)
    if len(alerts_df):
        alerts_df = alerts_df.sort_values(["alert_date", "tier", "exp_usd"], ascending=[True, True, False]).reset_index(drop=True)
    return risk, alerts_df


# ---------------------------------------------------------------------------
# nb_07: outcomes
# ---------------------------------------------------------------------------
def build_outcomes(alerts: pd.DataFrame, episodes: pd.DataFrame, risk: pd.DataFrame,
                   baseline: pd.DataFrame) -> pd.DataFrame:
    # nb_07 only considers episodes that contain a usable coded event.
    episodes = episodes[episodes["has_coded_event"].astype(bool)]
    p90 = dict(zip(baseline.loc[baseline["metric"] == "deferred_oil", "entity_id"],
                   baseline.loc[baseline["metric"] == "deferred_oil", "p90"]))
    observed = risk[risk["is_observed"]][["station_id", "date", "deferred_oil"]].sort_values(["station_id", "date"]).reset_index(drop=True)
    loss_rows = []
    for station_id, group in observed.groupby("station_id"):
        group = group.sort_values("date").reset_index(drop=True)
        threshold = p90.get(station_id)
        if threshold is None or pd.isna(threshold):
            continue
        for _, row in group.iterrows():
            if pd.isna(row["deferred_oil"]) or row["deferred_oil"] < threshold:
                continue
            previous = group[group["date"] < row["date"]].tail(QUIET_DAYS)
            if len(previous) == QUIET_DAYS and (previous["deferred_oil"] < threshold).all():
                loss_rows.append({"station_id": station_id, "date": row["date"]})
    large_loss = pd.DataFrame(loss_rows)
    max_data_date = observed["date"].max()
    now = COMPUTED_AT
    rows = []
    for _, alert in alerts.iterrows():
        start = pd.Timestamp(alert["alert_date"]).normalize()
        end = start + pd.Timedelta(days=HORIZON_DAYS)
        coded = episodes[
            (episodes["station_id"] == alert["station_id"])
            & (episodes["episode_start"] > start)
            & (episodes["episode_start"] <= end)
        ]
        first_coded = coded["episode_start"].min() if len(coded) else pd.NaT
        loss = large_loss[
            (large_loss["station_id"] == alert["station_id"])
            & (large_loss["date"] > start)
            & (large_loss["date"] <= end)
        ] if len(large_loss) else large_loss
        first_loss = loss["date"].min() if len(loss) else pd.NaT
        candidates = []
        if pd.notna(first_coded):
            candidates.append((first_coded, "coded_onset"))
        if pd.notna(first_loss):
            candidates.append((first_loss, "large_loss"))
        if candidates:
            event_date, detection = sorted(candidates, key=lambda x: (x[0], 0 if x[1] == "coded_onset" else 1))[0]
            lead_days = (event_date - start).days
            event_occurred = True
            disposition = "confirmed"
        else:
            event_date = None
            lead_days = None
            if end > max_data_date:
                event_occurred = None
                detection = "pending_horizon"
                disposition = "pending"
            else:
                event_occurred = False
                detection = "none"
                disposition = "false_alarm"
        rows.append((alert["alert_id"], now, event_occurred,
                     event_date.date() if event_date is not None else None,
                     lead_days, detection, disposition, None, None, None, None, now))
    cols = ["alert_id", "outcome_recorded_at_utc", "event_occurred", "event_date",
            "actual_lead_days", "detection_type", "disposition", "acknowledged_by",
            "acknowledged_at_utc", "action_note", "false_reason", "updated_at_utc"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# dimensions (nb_05)
# ---------------------------------------------------------------------------
def build_dimensions(risk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.DataFrame({"date": pd.date_range(risk["date"].min(), risk["date"].max(), freq="D")})
    d = dates.copy()
    d["year"] = d["date"].dt.year.astype(int)
    d["quarter"] = d["date"].dt.quarter.astype(int)
    d["month"] = d["date"].dt.month.astype(int)
    d["month_name"] = d["date"].dt.strftime("%b")
    d["year_month"] = d["date"].dt.strftime("%Y-%m")
    d["week_start"] = d["date"] - pd.to_timedelta((d["date"].dt.dayofweek + 0) % 7, unit="D")
    # Spark weekofyear: ISO week number.
    d["week_of_year"] = d["date"].dt.isocalendar().week.astype(int)
    d["weekday"] = d["date"].dt.strftime("%A")
    d["weekday_num"] = d["date"].dt.dayofweek.astype(int)
    d["is_weekend"] = d["weekday_num"] >= 5
    d["day_of_month"] = d["date"].dt.day.astype(int)
    d["day_of_year"] = d["date"].dt.dayofyear.astype(int)
    stations = (risk[["station_id", "station_name", "asset", "owner_name", "owner_upn"]]
                .drop_duplicates(["station_id"]).sort_values("station_id").reset_index(drop=True))
    return d, stations


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def build_all(input_root: str | Path) -> dict[str, pd.DataFrame]:
    input_root = Path(input_root)
    silver = build_silver(input_root)
    gold_features = build_gold_features(silver)
    risk, alerts = build_gold_risk(gold_features["gold_entity_day_features"], gold_features["gold_entity_baseline"])
    outcomes = build_outcomes(alerts, silver["deferment_episode"], risk, gold_features["gold_entity_baseline"])
    dim_date, dim_station = build_dimensions(risk)
    return {
        **{f"silver_{k}": v for k, v in silver.items()},
        **gold_features,
        "gold_risk_daily": risk,
        "gold_alert": alerts,
        "gold_alert_outcome": outcomes,
        "gold_df_dim_date": dim_date,
        "gold_df_dim_station": dim_station,
    }
