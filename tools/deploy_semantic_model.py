#!/usr/bin/env python3
"""Build and publish ``sm_df_early_warning`` (Direct Lake over ``lh_gold``).

USAGE
    python tools/deploy_semantic_model.py --env sandbox --dry-run
    python tools/deploy_semantic_model.py --env sandbox
    python tools/deploy_semantic_model.py --env sandbox --update

SAFETY
    Create-only by default. Pass ``--update`` to replace an existing model
    definition.

WHAT IT DOES
    1. Generates TMDL from ``fabric/semantic_model/model_spec.py`` (physical
       schema) and ``model_logic.py`` (tables, measures, relationships).
    2. Writes the generated definition to ``fabric/semantic_model/`` so it is
       reviewable and versioned.
    3. Publishes it through the Fabric Items API.
    4. Refreshes the Direct Lake model and runs DAX smoke tests.

Direct Lake requires the model table name to equal the physical Delta table
name. The TMDL generator therefore never renames a table.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "fabric" / "semantic_model"))

import env_config  # noqa: E402
import fabric_items  # noqa: E402
import model_logic  # noqa: E402
import model_spec  # noqa: E402

NAMESPACE = uuid.UUID("6f1b6a4c-6b1e-4f6a-9b9b-1e7e6c5b8a10")
OUT_DIR = REPO / "fabric" / "semantic_model"

DATE_ONLY = {
    "date", "alert_date", "event_date", "estimation_start", "estimation_end",
    "week_start",
}
USD_NAMES = {
    "exp_usd", "oil_price_usd", "deferred_value_usd", "potential_value_usd",
    "target_gap_value_usd", "deferred_value_usd_roll_mean_7",
    "deferred_value_usd_roll_sum_7",
}
Z_NAMES = {
    "robust_z", "max_bad_z", "primary_bad_z", "top_signal_z", "top_risk_z",
    "deviation_score",
}
OIL_NAMES = {
    "actual_oil", "target_oil", "actual_gas", "actual_water", "actual_gross",
    "deferred_oil", "potential_oil", "exp_deferred_bbl", "exp_excess_bbl",
    "oil_lag_1", "oil_lag_7", "oil_delta_1", "oil_delta_7",
    "oil_roll_mean_7", "oil_roll_std_7", "oil_roll_mean_28", "oil_ewma_7_prev",
    "oil_slope_7", "oil_cusum_pos", "oil_cusum_neg",
    "deferred_oil_roll_mean_7", "deferred_oil_roll_sum_7",
}
COUNT_HINTS = (
    "count", "days", "signals", "persistence", "signal_run", "n_obs",
    "week_of_year", "day_of_month", "day_of_year", "quarter", "month",
    "year", "weekday_num", "wells",
)


def guid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def guess_format(name: str, data_type: str) -> str | None:
    if data_type == "string" or data_type == "boolean":
        return None
    if data_type == "dateTime":
        if name in DATE_ONLY or name.endswith("_date"):
            return "yyyy-mm-dd"
        return "yyyy-mm-dd hh:mm:ss"
    if name in USD_NAMES:
        return "$#,##0"
    if name.endswith("_usd"):
        return "$#,##0"
    if name in {"deferment_pct", "target_gap_pct", "pct_deviation"}:
        return "0.0%"
    if name.endswith("_pct") or name.startswith("pct_dev_"):
        return "0.0%"
    if name in Z_NAMES or name.startswith("z_"):
        return "0.00"
    if "score" in name:
        return "0.000"
    if name in OIL_NAMES:
        return "#,##0.0"
    if any(h in name for h in COUNT_HINTS):
        return "0"
    if data_type == "int64":
        return "0"
    return "0.0"


def column_tmdl(name: str, data_type: str, is_key: bool = False) -> list[str]:
    lines = [f"\tcolumn {name}"]
    if is_key or (data_type == "dateTime" and name == "date"):
        lines.append("\t\tisKey")
    lines.append(f"\t\tdataType: {data_type}")
    fmt = guess_format(name, data_type)
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines.append(f"\t\tlineageTag: {guid('column', name)}")
    lines.append("\t\tsummarizeBy: none")
    lines.append(f"\t\tsourceColumn: {name}")
    lines.append("")
    return lines


def measure_tmdl(name: str, expression: str, fmt: str | None) -> list[str]:
    # Collapse DAX to one line: TMDL multiline expressions are indentation
    # sensitive and unnecessary here.
    expr = " ".join(expression.split())
    lines = [f"\tmeasure '{name}' = {expr}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines.append(f"\t\tlineageTag: {guid('measure', name)}")
    lines.append("")
    return lines


def table_tmdl(table: str) -> str:
    columns = model_spec.TABLES[table]
    lines = [f"table {table}", f"\tlineageTag: {guid('table', table)}"]
    if table == "gold_df_dim_date":
        lines.append("\tdataCategory: Time")
    lines.append("")
    keys = {
        ("gold_df_dim_station", "station_id"),
        ("gold_alert", "alert_id"),
    }
    for name, data_type in columns:
        lines.extend(column_tmdl(name, data_type, (table, name) in keys))
    for m_table, name, expr, fmt in model_logic.MEASURES:
        if m_table == table:
            lines.extend(measure_tmdl(name, expr, fmt))
    lines.extend([
        f"\tpartition {table} = entity",
        "\t\tmode: directLake",
        "\t\tsource",
        f"\t\t\tentityName: {table}",
        "\t\t\texpressionSource: DatabaseQuery",
        "",
    ])
    return "\n".join(lines)


def build_definition(workspace_id: str, lakehouse_id: str) -> dict[str, str]:
    tables = model_logic.TABLES_IN_MODEL
    missing = [t for t in tables if t not in model_spec.TABLES]
    if missing:
        raise SystemExit(f"Tables missing from model_spec.TABLES: {missing}")

    files: dict[str, str] = {}
    files["definition.pbism"] = json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "5.0",
        "settings": {"qnaEnabled": False},
    }, indent=2)
    files["definition/database.tmdl"] = "database\n\tcompatibilityLevel: 1604\n"
    files["definition/expressions.tmdl"] = (
        "expression DatabaseQuery =\n"
        "\tlet\n"
        f"\t\tSource = AzureStorage.DataLake(\"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}\", [HierarchicalNavigation=true])\n"
        "\tin\n"
        "\t\tSource\n"
    )
    refs = "\n".join(f"ref table {t}" for t in tables)
    files["definition/model.tmdl"] = (
        "model Model\n"
        f"\tculture: {model_logic.MODEL_CULTURE}\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        f"\tsourceQueryCulture: {model_logic.MODEL_CULTURE}\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n"
        "\n"
        'annotation PBI_QueryOrder = ["DatabaseQuery"]\n'
        "\n"
        f"{refs}\n"
    )

    for table in tables:
        files[f"definition/tables/{table}.tmdl"] = table_tmdl(table)

    rel_lines = []
    for from_table, from_col, to_table, to_col in model_logic.RELATIONSHIPS:
        rel_lines.extend([
            f"relationship {guid('rel', from_table, from_col, to_table, to_col)}",
            f"\tfromColumn: {from_table}.{from_col}",
            f"\ttoColumn: {to_table}.{to_col}",
            "",
        ])
    files["definition/relationships.tmdl"] = "\n".join(rel_lines)
    return files


def write_local(files: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table_dir = OUT_DIR / "definition" / "tables"
    if table_dir.exists():
        for old in table_dir.glob("*.tmdl"):
            old.unlink()
    for rel, text in files.items():
        path = OUT_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"Wrote {len(files)} definition parts to {OUT_DIR}")


def definition_payload(files: dict[str, str]) -> dict:
    parts = []
    for rel, text in sorted(files.items()):
        parts.append({
            "path": rel,
            "payload": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "payloadType": "InlineBase64",
        })
    return {"parts": parts}


def pbi_tokens() -> tuple[str, str]:
    return (
        fabric_items.az_token(fabric_items.FABRIC_RESOURCE),
        fabric_items.az_token(fabric_items.POWERBI_RESOURCE),
    )


def refresh_and_check(ws: str, model_id: str, pbi_token: str) -> None:
    print("Refreshing Direct Lake model ...", flush=True)
    fabric_items.start_refresh(ws, model_id, pbi_token)
    latest = fabric_items.wait_for_refresh(ws, model_id, pbi_token)
    status = latest.get("status")
    print(f"  refresh: {status}")
    if status != "Completed":
        detail = latest.get("serviceExceptionJson") or json.dumps(latest, indent=2)
        raise SystemExit(f"Refresh failed: {detail}")

    checks = [
        ("stations", "EVALUATE ROW(\"stations\", COUNTROWS('gold_df_dim_station'))", 5),
        ("dates", "EVALUATE ROW(\"dates\", COUNTROWS('gold_df_dim_date'))", 90),
        ("scored_days", "EVALUATE ROW(\"scored_days\", [Scored Days])", 273),
        ("red_days", "EVALUATE ROW(\"red_days\", [Red Days])", 25),
        ("amber_days", "EVALUATE ROW(\"amber_days\", [Amber Days])", 22),
        ("green_days", "EVALUATE ROW(\"green_days\", [Green Days])", 226),
        ("alerts", "EVALUATE ROW(\"alerts\", [Alerts Fired])", 17),
    ]
    failures = []
    print("\nDAX smoke tests:")
    for label, query, expected in checks:
        try:
            rows = fabric_items.dax_rows(
                fabric_items.execute_dax(ws, model_id, query, pbi_token)
            )
            value = rows[0].get(f"[{label}]", rows[0].get(label)) if rows else None
            value = int(value) if isinstance(value, (int, float)) else value
            ok = value == expected
            print(f"  {label:14s} {value!r:>8} expected {expected:<8} {'OK' if ok else 'FAIL'}")
            if not ok:
                failures.append((label, value, expected))
        except Exception as exc:  # noqa: BLE001 - report all checks
            print(f"  {label:14s} ERROR {exc}")
            failures.append((label, "error", expected))

    if failures:
        raise SystemExit(f"Smoke-test failures: {failures}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and publish sm_df_early_warning.")
    ap.add_argument("--env", default="sandbox")
    ap.add_argument("--name", default=model_logic.MODEL_NAME)
    ap.add_argument("--update", action="store_true",
                    help="replace the definition if the model already exists")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate the definition locally and exit")
    ap.add_argument("--skip-refresh", action="store_true",
                    help="publish but do not refresh or run smoke tests")
    args = ap.parse_args()

    env_config.load(args.env)
    ws = os.environ.get("FABRIC_WORKSPACE_ID")
    if not ws:
        raise SystemExit("Missing FABRIC_WORKSPACE_ID in the profile.")

    fabric_token, pbi_token = pbi_tokens()
    lakehouse = fabric_items.find_item(ws, "lh_gold", "Lakehouse", fabric_token)
    if not lakehouse:
        raise SystemExit("lh_gold lakehouse not found in this workspace.")
    lakehouse_id = lakehouse["id"]

    files = build_definition(ws, lakehouse_id)
    write_local(files)
    if args.dry_run:
        print("Dry run: definition generated, nothing published.")
        return 0

    defn = definition_payload(files)
    existing = fabric_items.find_item(ws, args.name, "SemanticModel", fabric_token)

    if existing:
        if not args.update:
            print(f"Semantic model '{args.name}' already exists ({existing['id']}). "
                  "Leaving it untouched. Use --update to replace its definition.")
            model_id = existing["id"]
        else:
            print(f"Updating semantic model '{args.name}' ({existing['id']}) ...",
                  flush=True)
            try:
                fabric_items.update_item_definition(ws, existing["id"], defn,
                                                    fabric_token)
            except RuntimeError:
                fabric_items.call(
                    "POST",
                    f"/workspaces/{ws}/semanticModels/{existing['id']}/updateDefinition",
                    fabric_token,
                    {"definition": defn},
                )
            model_id = existing["id"]
            print("  definition updated")
    else:
        print(f"Creating semantic model '{args.name}' ...", flush=True)
        result = fabric_items.create_item(ws, {
            "displayName": args.name,
            "description": model_logic.MODEL_DESCRIPTION,
            "type": "SemanticModel",
            "definition": defn,
        }, fabric_token)
        model_id = result.get("id")
        if not model_id:
            # LRO results vary; look it up by name as a fallback.
            item = fabric_items.find_item(ws, args.name, "SemanticModel",
                                          fabric_token)
            model_id = item["id"] if item else None
        if not model_id:
            raise SystemExit(f"Model created but id could not be resolved: {result}")
        print(f"  id: {model_id}")

    print(f"\nModel id: {model_id}")
    print(f"Workspace: {ws}")
    if args.skip_refresh:
        return 0

    refresh_and_check(ws, model_id, pbi_token)
    print("\nSlice 1 acceptance checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
