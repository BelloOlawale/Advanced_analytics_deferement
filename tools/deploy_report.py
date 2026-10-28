#!/usr/bin/env python3
"""Build and publish ``rpt_df_early_warning`` (PBIR).

USAGE
    python tools/deploy_report.py --env sandbox --dry-run
    python tools/deploy_report.py --env sandbox
    python tools/deploy_report.py --env sandbox --update

SAFETY
    Create-only by default. ``--update`` replaces an existing report
    definition.

The report is bound to ``sm_df_early_warning`` by its semantic model id.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "fabric" / "report"))

import env_config  # noqa: E402
import fabric_items  # noqa: E402
import report_spec  # noqa: E402

OUT_DIR = REPO / "fabric" / "report"


def write_local(parts: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Remove stale generated PBIR parts before writing the new set.
    for rel in ("definition",):
        target = OUT_DIR / rel
        if target.exists():
            for p in sorted(target.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink()
            for p in sorted(target.rglob("*"), reverse=True):
                if p.is_dir():
                    p.rmdir()
    for rel, text in parts.items():
        path = OUT_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"Wrote {len(parts)} PBIR parts to {OUT_DIR}")


def definition_payload(parts: dict[str, str]) -> dict:
    return {"parts": [
        {
            "path": rel,
            "payload": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "payloadType": "InlineBase64",
        }
        for rel, text in sorted(parts.items())
    ]}


def verify(ws: str, report_id: str, model_id: str, fabric_token: str,
           pbi_token: str) -> None:
    # The definition round-trip proves Fabric stored every PBIR part.
    data = fabric_items.get_item_definition(ws, report_id, fabric_token)
    stored = [p.get("path") for p in data.get("definition", {}).get("parts", [])]
    expected = [p for p in report_spec.build_parts(model_id)]
    missing = sorted(set(expected) - set(stored))
    print(f"\nStored PBIR parts: {len(stored)}")
    if missing:
        raise SystemExit(f"Report definition is missing parts: {missing}")

    # Power BI pages API is a lightweight check that the report is queryable.
    try:
        url = f"{fabric_items.POWERBI_API}/groups/{ws}/reports/{report_id}/pages"
        resp = fabric_items._request("GET", url, pbi_token)
        pages = json.loads(resp.read() or b"{}").get("value", [])
        print("Report pages:", [(p.get("name"), p.get("displayName")) for p in pages])
    except Exception as exc:  # noqa: BLE001 - non-fatal verification
        print(f"Pages API check skipped: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and publish rpt_df_early_warning.")
    ap.add_argument("--env", default="sandbox")
    ap.add_argument("--name", default=report_spec.REPORT_NAME)
    ap.add_argument("--model-name", default="sm_df_early_warning")
    ap.add_argument("--update", action="store_true",
                    help="replace the definition if the report already exists")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate the PBIR locally and exit")
    args = ap.parse_args()

    env_config.load(args.env)
    ws = os.environ.get("FABRIC_WORKSPACE_ID")
    if not ws:
        raise SystemExit("Missing FABRIC_WORKSPACE_ID in the profile.")

    fabric_token = fabric_items.az_token(fabric_items.FABRIC_RESOURCE)
    pbi_token = fabric_items.az_token(fabric_items.POWERBI_RESOURCE)

    model = fabric_items.find_item(ws, args.model_name, "SemanticModel", fabric_token)
    if not model:
        raise SystemExit(f"Semantic model '{args.model_name}' not found.")
    if not model.get("id"):
        raise SystemExit(f"Semantic model '{args.model_name}' has no id.")
    model_id = model["id"]
    print(f"Binding report to {args.model_name} ({model_id})")

    parts = report_spec.build_parts(model_id)
    write_local(parts)
    if args.dry_run:
        print("Dry run: PBIR generated, nothing published.")
        return 0

    defn = definition_payload(parts)
    existing = fabric_items.find_item(ws, args.name, "Report", fabric_token)

    if existing:
        if not args.update:
            print(f"Report '{args.name}' already exists ({existing['id']}). "
                  "Leaving it untouched. Use --update to replace its definition.")
            report_id = existing["id"]
        else:
            print(f"Updating report '{args.name}' ({existing['id']}) ...",
                  flush=True)
            try:
                fabric_items.update_item_definition(ws, existing["id"], defn,
                                                    fabric_token)
            except RuntimeError:
                fabric_items.call(
                    "POST",
                    f"/workspaces/{ws}/reports/{existing['id']}/updateDefinition",
                    fabric_token,
                    {"definition": defn},
                )
            report_id = existing["id"]
            print("  definition updated")
    else:
        print(f"Creating report '{args.name}' ...", flush=True)
        result = fabric_items.create_item(ws, {
            "displayName": args.name,
            "description": report_spec.REPORT_DESCRIPTION,
            "type": "Report",
            "definition": defn,
        }, fabric_token)
        report_id = result.get("id")
        if not report_id:
            item = fabric_items.find_item(ws, args.name, "Report", fabric_token)
            report_id = item["id"] if item else None
        if not report_id:
            raise SystemExit(f"Report created but id could not be resolved: {result}")
        print(f"  id: {report_id}")

    print(f"\nReport id: {report_id}")
    print(f"Workspace: {ws}")
    verify(ws, report_id, model_id, fabric_token, pbi_token)
    print("\nReport build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
