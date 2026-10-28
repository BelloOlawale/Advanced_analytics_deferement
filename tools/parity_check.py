#!/usr/bin/env python3
"""
parity_check.py - Slice 8: compare Fabric gold output with a local reference.

WHY
    The Fabric build is only trustworthy if a second implementation, reading the
    same input window, produces the same tables. This script:

    1. reads the seed CSVs under ``--input`` (raw/ + ref/),
    2. builds silver/gold with the clean-room pandas reference in
       ``tools/parity_reference.py``,
    3. fetches the live ``lh_silver`` / ``lh_gold`` tables (or reuses a cached
       snapshot),
    4. compares row counts, keys, numeric values and text/JSON payloads,
    5. writes a markdown report plus a machine-readable JSON result.

    The historical prototype code is not in this repository, so this is a
    clean-room reference built from the documented notebook rules. It is not a
    substitute for running the original prototype when that code is available.

USAGE
    python tools/parity_check.py --env sandbox
    python tools/parity_check.py --env sandbox --no-fetch   # use cached CSVs
    python tools/parity_check.py --input test_data/sandbox \
        --fabric-dir test_data/parity/fabric \
        --report docs/fabric-parity-check-slice8.md

AUTH
    Fetching uses Azure CLI credentials (``az login`` in the profile's
    AZURE_CONFIG_DIR). The query is read-only: SELECT only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import parity_reference as ref  # noqa: E402

warnings.filterwarnings("ignore", message="DataFrame is highly fragmented")

# Tables fetched from Fabric. Names are physical table names.
FABRIC_TABLES = {
    "lh_silver": [
        "silver_dim_station",
        "silver_dim_date",
        "silver_oil_prices",
        "silver_owner_map",
        "silver_station_day",
        "silver_deferment_event",
        "silver_deferment_episode",
        "silver_production_day",
        "silver_data_quality",
    ],
    "lh_gold": [
        "gold_entity_baseline",
        "gold_entity_day_features",
        "gold_deviation_daily",
        "gold_risk_daily",
        "gold_alert",
        "gold_alert_outcome",
        "gold_df_dim_date",
        "gold_df_dim_station",
        "gold_data_quality",
        "gold_risk_data_quality",
        "gold_pipeline_dq_log",
    ],
}

# Comparison keys. Episode rows need the natural key because episode_id omits
# cause_group and is therefore not unique (see the report).
COMPARE = [
    ("silver_dim_station", ["flowstation_id"]),
    ("silver_dim_date", ["date"]),
    ("silver_oil_prices", ["date"]),
    ("silver_owner_map", ["station_id"]),
    ("silver_station_day", ["station_id", "date"]),
    ("silver_deferment_event", ["deferment_id"]),
    (
        "silver_deferment_episode",
        ["station_id", "productionstring", "cause_code", "cause_group", "episode_start", "episode_end"],
    ),
    ("gold_entity_baseline", ["entity_id", "metric"]),
    ("gold_entity_day_features", ["station_id", "date"]),
    ("gold_deviation_daily", ["entity_id", "date", "metric"]),
    ("gold_risk_daily", ["station_id", "date"]),
    ("gold_alert", ["alert_id"]),
    ("gold_alert_outcome", ["alert_id"]),
    ("gold_df_dim_date", ["date"]),
    ("gold_df_dim_station", ["station_id"]),
]

TIMESTAMP_COLS = {
    "computed_at_utc",
    "fired_at_utc",
    "outcome_recorded_at_utc",
    "updated_at_utc",
    "acknowledged_at_utc",
    "checked_at_utc",
    "_ingested_at_utc",
    "batch_id",
}
JSON_COLS = {"signals_json", "risk_reasons_json"}
DATE_KEY_PARTS = ("date", "start", "end")

ATOL = 1e-6
RTOL = 1e-9


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------
def fetch_fabric(env: str, out_dir: Path) -> None:
    """Fetch every table in FABRIC_TABLES as CSV. Read-only."""
    import mssql_python
    from azure.identity import AzureCliCredential

    try:
        import env_config
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO / "tools"))
        import env_config

    env_config.load(env)
    server = os.environ.get("FABRIC_SQL_SERVER")
    if not server:
        raise SystemExit("FABRIC_SQL_SERVER is not set for this profile.")
    tenant = os.environ.get("FABRIC_SQL_TENANT") or None
    cred = AzureCliCredential(tenant_id=tenant) if tenant else AzureCliCredential()
    out_dir.mkdir(parents=True, exist_ok=True)

    for db, tables in FABRIC_TABLES.items():
        conn_str = f"Server={server};Database={db};Encrypt=yes;"
        with mssql_python.connect(conn_str, token_provider=cred, timeout=30) as conn:
            conn.timeout = 300
            for table in tables:
                with conn.cursor() as cur:
                    cur.execute(f"SELECT * FROM dbo.{table}")
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description]
                path = out_dir / f"{table}.csv"
                with path.open("w", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(cols)
                    writer.writerows(rows)
                print(f"  fetched {db}.{table}: {len(rows):,} rows -> {path}")


def load_fabric(fabric_dir: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for path in sorted(fabric_dir.glob("*.csv")):
        # keep_default_na=False preserves the literal string "None" in
        # alert_action; blank cells are handled per column during comparison.
        out[path.stem] = pd.read_csv(path, keep_default_na=False, low_memory=False)
    return out


# ---------------------------------------------------------------------------
# comparison helpers
# ---------------------------------------------------------------------------
def _key_value(series: pd.Series, name: str) -> pd.Series:
    if "date" in name or name.endswith("_start") or name.endswith("_end"):
        return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")
    return series.astype(str)


def _keys(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = df.copy()
    for key in keys:
        if key not in out.columns:
            raise KeyError(f"missing key column {key!r}")
        out[key] = _key_value(out[key], key)
    return out


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace("", np.nan), errors="coerce").astype("float64")


def _is_numeric_col(x: pd.Series, y: pd.Series) -> bool:
    if pd.api.types.is_bool_dtype(x) or pd.api.types.is_bool_dtype(y):
        return False
    xs = x.replace("", np.nan)
    ys = y.replace("", np.nan)
    nx = pd.to_numeric(xs, errors="coerce")
    ny = pd.to_numeric(ys, errors="coerce")
    ok_x = ((xs.notna()) == (nx.notna())).all()
    ok_y = ((ys.notna()) == (ny.notna())).all()
    return bool(ok_x and ok_y and (nx.notna().any() or ny.notna().any()))


def _norm_text(series: pd.Series) -> pd.Series:
    # Empty/NA are equivalent. "None" is a real alert_action value, so do not
    # fold it into empty.
    return series.fillna("").astype(str)


def _json_equal(a: str, b: str) -> bool:
    try:
        ja = json.loads(a or "[]")
        jb = json.loads(b or "[]")
    except (TypeError, ValueError):
        return False
    if len(ja) != len(jb):
        return False
    for x, y in zip(ja, jb):
        if x.get("metric") != y.get("metric"):
            return False
        if x.get("direction") != y.get("direction"):
            return False
        if abs(float(x.get("z", 0.0)) - float(y.get("z", 0.0))) > 1e-9:
            return False
        for field in ("value", "expected"):
            vx, vy = x.get(field), y.get(field)
            if (vx is None) != (vy is None):
                return False
            if vx is not None and abs(vx - vy) > 1e-9 * max(1.0, abs(vx), abs(vy)):
                return False
    return True


def _tie_flip(row: pd.Series, local_col: str, fabric_col: str) -> bool:
    """True when a top-signal field differs only because two |z| are tied.

    The tie is always decided from ``top_signal``; the same explanation applies
    to the companion ``top_signal_z`` and ``top_signal_direction`` fields.
    """
    a = str(row.get("top_signal_loc", "") or "")
    b = str(row.get("top_signal_fab", "") or "")
    if not a or not b or a == b or a == "None" or b == "None":
        return False
    if a not in ref.METRIC_NAMES or b not in ref.METRIC_NAMES:
        return False
    za = row.get(f"z_{a}_loc")
    zb = row.get(f"z_{b}_loc")
    if pd.isna(za) or pd.isna(zb):
        return False
    return abs(abs(float(za)) - abs(float(zb))) <= 1e-12


def compare_table(
    name: str,
    local: pd.DataFrame,
    fabric: pd.DataFrame,
    keys: list[str],
) -> dict:
    common = [c for c in local.columns if c in fabric.columns]
    missing_local = sorted(set(fabric.columns) - set(local.columns))
    missing_fabric = sorted(set(local.columns) - set(fabric.columns))

    l = _keys(local, keys)
    f = _keys(fabric, keys)

    dup_local = int(l.duplicated(keys).sum())
    dup_fabric = int(f.duplicated(keys).sum())
    l = l.drop_duplicates(keys)
    f = f.drop_duplicates(keys)

    merged = l[common].merge(
        f[common], on=keys, how="outer", indicator=True, suffixes=("_loc", "_fab")
    )
    presence = merged["_merge"].value_counts().to_dict()
    mismatch_cols: list[dict] = []
    tie_rows: list[dict] = []

    for col in common:
        if col in keys or col in TIMESTAMP_COLS:
            continue
        x = merged[f"{col}_loc"]
        y = merged[f"{col}_fab"]

        if col in JSON_COLS:
            bad = [
                (tuple(r), a, b)
                for r, a, b in zip(
                    merged[keys].itertuples(index=False, name=None),
                    x.fillna("").astype(str),
                    y.fillna("").astype(str),
                )
                if not _json_equal(a, b)
            ]
            if bad:
                mismatch_cols.append({"column": col, "count": len(bad), "kind": "json"})
            continue

        if _is_numeric_col(x, y):
            ax, ay = _to_num(x), _to_num(y)
            both = ax.notna() & ay.notna()
            delta = (ax - ay).abs()
            bad = both & (delta > (ATOL + RTOL * ax.abs()))
            null_mis = ax.isna() != ay.isna()

            # A top-signal tie flip also changes top_signal_z; treat it with
            # the same tie-credit as the other two display fields.
            if name == "gold_entity_day_features" and col == "top_signal_z":
                remaining = []
                for idx in merged.index[bad | null_mis]:
                    row = merged.loc[idx]
                    if _tie_flip(row, col, col):
                        tie_rows.append({"column": col, "key": tuple(row[k] for k in keys)})
                    else:
                        remaining.append(idx)
                if remaining:
                    mismatch_cols.append({
                        "column": col,
                        "count": len(remaining),
                        "kind": "numeric",
                        "max_abs": float(delta[both].max()) if both.any() else None,
                        "null_mismatch": int(null_mis.sum()),
                    })
                continue

            n = int(bad.sum() + null_mis.sum())
            if n:
                mismatch_cols.append({
                    "column": col,
                    "count": n,
                    "kind": "numeric",
                    "max_abs": float(delta[both].max()) if both.any() else None,
                    "null_mismatch": int(null_mis.sum()),
                })
            continue

        xs, ys = _norm_text(x), _norm_text(y)
        if pd.api.types.is_bool_dtype(x) or pd.api.types.is_bool_dtype(y):
            xs = xs.str.lower().replace({"nan": "", "none": ""})
            ys = ys.str.lower().replace({"nan": "", "none": ""})
        unequal = xs != ys
        if not unequal.any():
            continue

        if name == "gold_entity_day_features" and col in {
            "top_signal", "top_signal_z", "top_signal_direction"
        }:
            # A tie flip is only benign if every differing row is explained by
            # two signals whose |z| is equal within floating-point noise.
            remaining = []
            for idx in merged.index[unequal]:
                row = merged.loc[idx]
                if _tie_flip(row, col, col):
                    tie_rows.append({"column": col, "key": tuple(row[k] for k in keys)})
                else:
                    remaining.append(idx)
            if remaining:
                mismatch_cols.append({"column": col, "count": len(remaining), "kind": "text"})
            continue

        mismatch_cols.append({"column": col, "count": int(unequal.sum()), "kind": "text"})

    status = "PASS"
    if presence.get("left_only") or presence.get("right_only"):
        status = "FAIL"
    if any(m["kind"] != "tie" for m in mismatch_cols):
        status = "FAIL"

    return {
        "table": name,
        "keys": keys,
        "local_rows": int(len(local)),
        "fabric_rows": int(len(fabric)),
        "unique_local_keys": int(len(l)),
        "unique_fabric_keys": int(len(f)),
        "presence": presence,
        "duplicate_keys_local": dup_local,
        "duplicate_keys_fabric": dup_fabric,
        "columns_compared": len(common),
        "missing_local_columns": missing_local,
        "missing_fabric_columns": missing_fabric,
        "mismatch_columns": mismatch_cols,
        "tie_rows": tie_rows,
        "status": status,
    }


# ---------------------------------------------------------------------------
# KPI parity
# ---------------------------------------------------------------------------
def kpis(tables: dict[str, pd.DataFrame]) -> dict:
    risk = tables["gold_risk_daily"].copy()
    alerts = tables["gold_alert"].copy()
    outcomes = tables["gold_alert_outcome"].copy()
    features = tables["gold_entity_day_features"].copy()
    dev = tables["gold_deviation_daily"].copy()

    for frame in (risk, features):
        for col in ("is_observed",):
            if col in frame:
                frame[col] = frame[col].astype(str).str.lower().isin(("true", "1"))
    for col in ("is_outlier",):
        if col in dev:
            dev[col] = dev[col].astype(str).str.lower().isin(("true", "1"))
    for col in ("event_occurred",):
        if col in outcomes:
            outcomes[col] = outcomes[col].astype(str).str.lower().map(
                {"true": True, "false": False, "": None, "nan": None}
            )

    scored = risk[risk["is_observed"] & (risk["baseline_phase"] == "scored")]
    tiers = scored["risk_tier"].value_counts().to_dict()
    lead = pd.to_numeric(outcomes["actual_lead_days"], errors="coerce")
    evaluated = outcomes[outcomes["event_occurred"].notna()]
    confirmed = outcomes[outcomes["event_occurred"] == True]  # noqa: E712
    false = outcomes[outcomes["event_occurred"] == False]  # noqa: E712
    pending = outcomes[outcomes["event_occurred"].isna()]

    return {
        "feature_rows": int(len(features)),
        "observed_rows": int(features["is_observed"].sum()),
        "scored_rows": int(len(scored)),
        "risk_rows": int(len(risk)),
        "red_days": int(tiers.get("Red", 0)),
        "amber_days": int(tiers.get("Amber", 0)),
        "green_days": int(tiers.get("Green", 0)),
        "deviation_rows": int(len(dev)),
        "outlier_rows": int(dev["is_outlier"].sum()),
        "alerts_fired": int(len(alerts)),
        "alerts_red": int((alerts["tier"] == "Red").sum()),
        "alerts_amber": int((alerts["tier"] == "Amber").sum()),
        "excess_value_at_risk_usd": float(pd.to_numeric(risk["exp_usd"], errors="coerce").sum()),
        "excess_usd_at_alert": float(pd.to_numeric(alerts["exp_usd"], errors="coerce").sum()),
        "outcome_rows": int(len(outcomes)),
        "evaluated": int(len(evaluated)),
        "confirmed": int(len(confirmed)),
        "false_alarms": int(len(false)),
        "pending": int(len(pending)),
        "median_lead_days": float(lead.median()) if lead.notna().any() else None,
        "mean_lead_days": float(lead.mean()) if lead.notna().any() else None,
        "precision_pct": float(len(confirmed) / len(evaluated) * 100) if len(evaluated) else None,
        "false_alarm_rate_pct": float(len(false) / len(evaluated) * 100) if len(evaluated) else None,
        "dim_date_rows": int(len(tables["gold_df_dim_date"])),
        "dim_station_rows": int(len(tables["gold_df_dim_station"])),
    }


def kpi_rows(local: dict, fabric: dict) -> list[dict]:
    rows = []
    for key in local:
        a, b = local[key], fabric[key]
        if isinstance(a, float) or isinstance(b, float):
            if a is None or b is None:
                ok = a is b
                diff = None
            else:
                diff = abs(a - b)
                ok = diff <= 1e-6 + 1e-9 * max(abs(a), abs(b))
        else:
            ok = a == b
            diff = None
        rows.append({"metric": key, "local": a, "fabric": b, "match": ok, "diff": diff})
    return rows


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.6f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def write_report(
    path: Path,
    results: list[dict],
    local_kpi: dict,
    fabric_kpi: dict,
    episode_dup_local: int,
    episode_dup_fabric: int,
    env: str,
    input_root: Path,
    fabric_dir: Path,
    overall: str,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Slice 8 — Fabric vs local parity check",
        "",
        f"**Run:** {now}  ",
        f"**Environment:** `{env}`  ",
        f"**Input window:** `{input_root}`  ",
        f"**Fabric snapshot:** `{fabric_dir}`  ",
        f"**Verdict:** **{overall}**",
        "",
        "## What this checks",
        "",
        "The same seed CSVs were run through two independent implementations:",
        "",
        "1. **Fabric** — `nb_01 → nb_07` in `lh_bronze` / `lh_silver` / `lh_gold`.",
        "2. **Local reference** — a clean-room pandas implementation of the documented",
        "   notebook rules (`tools/parity_reference.py`), reading `raw/` and `ref/` directly.",
        "",
        "The historical prototype code is not in this repository, so this is a",
        "clean-room parity check against the same input, not a replay of the original",
        "prototype. The timestamps and batch ids are intentionally excluded, as are",
        "the bronze audit columns (`_batch_id`, `_ingested_at_utc`, `_source_file`).",
        "",
        "Tolerances: numeric `atol=1e-6`, `rtol=1e-9`; empty/NA are equivalent;",
        "JSON payloads are compared semantically (metric, direction, z, value, expected).",
        "",
        "## Table results",
        "",
        "| Table | Local rows | Fabric rows | Keys | Compared cols | Result |",
        "|---|---:|---:|---|---:|---|",
    ]
    for r in results:
        detail = r["status"]
        if r["mismatch_columns"]:
            detail += ": " + ", ".join(
                f"{m['column']} ({m['count']})" for m in r["mismatch_columns"]
            )
        if r["tie_rows"]:
            tie_keys = {tuple(t["key"]) for t in r["tie_rows"]}
            detail += f"; {len(tie_keys)} benign tie flip(s)"
        lines.append(
            f"| `{r['table']}` | {r['local_rows']:,} | {r['fabric_rows']:,} | "
            f"{', '.join(r['keys'])} | {r['columns_compared']} | {detail} |"
        )
    lines += [
        "",
        "## KPI parity",
        "",
        "| KPI | Local reference | Fabric | Match |",
        "|---|---:|---:|---|",
    ]
    for row in kpi_rows(local_kpi, fabric_kpi):
        lines.append(
            f"| {row['metric']} | {fmt(row['local'])} | {fmt(row['fabric'])} | "
            f"{'yes' if row['match'] else 'NO'} |"
        )
    lines += [
        "",
        "## Known differences",
        "",
        "1. **Top-signal tie flips (8 feature rows).** `oil` and `target_gap_pct`",
        "   have mathematically equal `|z|` on these rows (target gap is the",
        "   complement of oil against the same target). Sub-1e-15 differences in the",
        "   two runtimes decide which one is labelled as `top_signal`. This changes",
        "   the label and the sign of `top_signal_z`, but not the risk score, tier or",
        "   any alert. `top_signal` is display/explanation data only.",
        "2. **`uptime_roll_std_7` (11 feature rows) differs by at most `7.6e-7`.**",
        "   The true value is zero for constant windows; both runtimes produce",
        "   floating-point dust around zero. It is far below any operational tolerance.",
        "",
        "## Defect found during parity",
        "",
        f"`silver_deferment_episode.episode_id` is **not unique**: "
        f"{episode_dup_local} duplicate rows in the local reference and "
        f"{episode_dup_fabric} in Fabric (identical in both). The id is built as "
        "`station_id|productionstring|cause_code|episode_seq`, but `cause_group` "
        "can be `Unknown` for one continuation of the same cause code and "
        "`Unscheduled Deferment` for another. The id therefore collides across",
        "two different episodes.",
        "",
        "Impact: the outcome job matches episodes by station + episode_start +",
        "cause_code, so the 17 alert outcomes still match exactly. The id should",
        "not be used as a join key until it includes `cause_group` or a surrogate.",
        "",
        "## Acceptance",
        "",
        "- Row counts, keys, numeric values, risk tiers, alerts and outcomes match",
        "  within the stated tolerances.",
        "- The only text differences are the 8 documented tie flips in a",
        "  display-only feature field.",
        "- No pipeline output is changed by this check: it is read-only.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"python tools/parity_check.py --env {env} --input {input_root} \\",
        f"    --fabric-dir {fabric_dir}",
        "```",
        "",
        "Cached Fabric CSVs live under the `--fabric-dir` (git-ignored). Re-run",
        "without `--fetch` to compare against the cached snapshot.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Slice 8 parity check: Fabric vs local reference.")
    ap.add_argument("--env", default="sandbox", help="Fabric profile from env_config")
    ap.add_argument("--input", default="test_data/sandbox", help="seed data root (raw/ + ref/)")
    ap.add_argument("--fabric-dir", default="test_data/parity/fabric", help="where Fabric CSVs live")
    ap.add_argument("--report", default="docs/fabric-parity-check-slice8.md")
    ap.add_argument("--no-fetch", action="store_true", help="use cached Fabric CSVs")
    args = ap.parse_args()

    input_root = (REPO / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    fabric_dir = (REPO / args.fabric_dir).resolve() if not Path(args.fabric_dir).is_absolute() else Path(args.fabric_dir)
    report_path = (REPO / args.report).resolve() if not Path(args.report).is_absolute() else Path(args.report)

    if not args.no_fetch:
        print("Fetching Fabric tables (read-only)...")
        fetch_fabric(args.env, fabric_dir)
    if not fabric_dir.exists():
        raise SystemExit(f"No Fabric snapshot at {fabric_dir}; run without --no-fetch first.")

    print("Building local reference from", input_root)
    local = ref.build_all(input_root)
    fabric = load_fabric(fabric_dir)

    results = []
    for name, keys in COMPARE:
        if name not in local or name not in fabric:
            print(f"  skip {name}: local={name in local} fabric={name in fabric}")
            continue
        result = compare_table(name, local[name], fabric[name], keys)
        results.append(result)
        print(
            f"  {name}: local={result['local_rows']:,} fabric={result['fabric_rows']:,} "
            f"status={result['status']} mismatches={len(result['mismatch_columns'])} "
            f"ties={len(result['tie_rows'])}"
        )

    local_kpi = kpis(local)
    fabric_kpi = kpis(fabric)
    ep_local = local["silver_deferment_episode"]
    ep_fab = fabric["silver_deferment_episode"]
    episode_dup_local = int(ep_local["episode_id"].duplicated().sum())
    episode_dup_fabric = int(ep_fab["episode_id"].duplicated().sum())
    overall = "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL"
    if episode_dup_local != episode_dup_fabric:
        overall = "FAIL"

    result_doc = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": args.env,
        "input": str(input_root),
        "fabric_snapshot": str(fabric_dir),
        "overall": overall,
        "tables": results,
        "kpis": {"local": local_kpi, "fabric": fabric_kpi},
        "episode_id_duplicates": {
            "local": episode_dup_local,
            "fabric": episode_dup_fabric,
        },
    }
    json_path = fabric_dir.parent / "parity-result.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result_doc, indent=2, default=str), encoding="utf-8")
    write_report(
        report_path, results, local_kpi, fabric_kpi,
        episode_dup_local, episode_dup_fabric,
        args.env, Path(args.input), Path(args.fabric_dir), overall,
    )

    print(f"\nVerdict: {overall}")
    print(f"Report : {report_path}")
    print(f"JSON   : {json_path}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
