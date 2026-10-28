#!/usr/bin/env python3
"""Build and publish ``pl_df_daily_build`` — the daily Gold pipeline.

WHAT IT DOES
    1. Finds the six notebooks by display name.
    2. Builds a Data Factory pipeline that runs them sequentially with retries.
    3. Adds a failure branch: optional Teams/webhook alert, then Fail.
    4. Creates a daily schedule at 06:00 UTC.
    5. Optionally runs the pipeline once and polls it.

USAGE
    python tools/deploy_pipeline.py --env sandbox --dry-run
    python tools/deploy_pipeline.py --env sandbox
    python tools/deploy_pipeline.py --env sandbox --update
    python tools/deploy_pipeline.py --env sandbox --run
    python tools/deploy_pipeline.py --env sandbox --no-schedule

SAFETY
    Create-only by default. ``--update`` replaces an existing pipeline
    definition. Existing schedules for this pipeline are replaced.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_config  # noqa: E402
import fabric_items  # noqa: E402

PIPELINE_NAME = "pl_df_daily_build"
PIPELINE_DESCRIPTION = (
    "Daily deferment early-warning build: bronze -> silver -> gold features -> "
    "risk/alerts -> dimensions -> DQ gate. Runs sequentially with retries."
)
OUT_DIR = REPO / "fabric" / "pipeline"

NOTEBOOKS = [
    "nb_01_bronze_ingest",
    "nb_02_silver_conform",
    "nb_03_gold_features",
    "nb_04_gold_risk_alerts",
    "nb_07_df_alert_outcomes",
    "nb_05_df_gold_dimensions",
    "nb_06_df_dq_gate",
]


def pipeline_content(workspace_id: str, notebook_ids: list[str]) -> dict:
    """The pipeline-content.json payload."""
    return {
        "properties": {
            "description": PIPELINE_DESCRIPTION,
            "parameters": {
                "notebook_ids": {
                    "type": "Array",
                    "defaultValue": notebook_ids,
                },
                "alert_webhook_url": {
                    "type": "String",
                    "defaultValue": "",
                },
            },
            "activities": [
                {
                    "name": "Run_notebooks",
                    "type": "ForEach",
                    "dependsOn": [],
                    "typeProperties": {
                        "items": {
                            "value": "@pipeline().parameters.notebook_ids",
                            "type": "Expression",
                        },
                        "isSequential": True,
                        "activities": [
                            {
                                "name": "Run_notebook",
                                "type": "TridentNotebook",
                                "dependsOn": [],
                                "policy": {
                                    "timeout": "0.02:00:00",
                                    "retry": 2,
                                    "retryIntervalInSeconds": 120,
                                    "secureOutput": False,
                                    "secureInput": False,
                                },
                                "typeProperties": {
                                    "notebookId": {
                                        "value": "@item()",
                                        "type": "Expression",
                                    },
                                    "workspaceId": workspace_id,
                                },
                            }
                        ],
                    },
                },
                {
                    "name": "Webhook_configured",
                    "type": "IfCondition",
                    "dependsOn": [
                        {
                            "activity": "Run_notebooks",
                            "dependencyConditions": ["Failed"],
                        }
                    ],
                    "typeProperties": {
                        "expression": {
                            "value": (
                                "@not(equals(pipeline().parameters.alert_webhook_url, ''))"
                            ),
                            "type": "Expression",
                        },
                        "ifTrueActivities": [
                            {
                                "name": "Send_failure_alert",
                                "type": "WebActivity",
                                "dependsOn": [],
                                "typeProperties": {
                                    "url": "@pipeline().parameters.alert_webhook_url",
                                    "method": "POST",
                                    "headers": {"Content-Type": "application/json"},
                                    "body": {
                                        "value": (
                                            "@json(concat('{\"pipeline\":\"', "
                                            "pipeline().Pipeline, "
                                            "'\",\"runId\":\"', pipeline().RunId, "
                                            "'\",\"status\":\"FAILED\",\"message\":\"One or more notebooks "
                                            "failed after retries. Check the Monitoring hub.\"}'))"
                                        ),
                                        "type": "Expression",
                                    },
                                },
                            }
                        ],
                        "ifFalseActivities": [
                            {
                                "name": "No_webhook_configured",
                                "type": "Wait",
                                "dependsOn": [],
                                "typeProperties": {"waitTimeInSeconds": 1},
                            }
                        ],
                    },
                },
                {
                    "name": "Fail_pipeline",
                    "type": "Fail",
                    "dependsOn": [
                        {
                            "activity": "Webhook_configured",
                            "dependencyConditions": ["Succeeded"],
                        }
                    ],
                    "typeProperties": {
                        "message": {
                            "value": (
                                "@concat('Daily build failed. Pipeline run: ', "
                                "pipeline().RunId, '. Check the Monitoring hub for "
                                "the failing notebook.')"
                            ),
                            "type": "Expression",
                        },
                        "errorCode": "DF_DAILY_BUILD_FAILED",
                    },
                },
            ],
        }
    }


def write_local(content: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "pipeline-content.json"
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def definition_payload(content: dict) -> dict:
    payload = base64.b64encode(
        json.dumps(content).encode("utf-8")
    ).decode("ascii")
    return {"parts": [{
        "path": "pipeline-content.json",
        "payload": payload,
        "payloadType": "InlineBase64",
    }]}


def replace_schedule(ws: str, pipeline_id: str, token: str,
                     hour_utc: int = 6) -> dict:
    base = f"/workspaces/{ws}/items/{pipeline_id}/jobs/Pipeline/schedules"
    existing = fabric_items.call("GET", base, token)
    for item in existing.get("value", []):
        sid = item.get("id")
        if sid:
            print(f"  removing existing schedule {sid}")
            fabric_items.call("DELETE", f"{base}/{sid}", token)

    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1)).replace(
        hour=hour_utc, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=365)
    body = {
        "enabled": True,
        "configuration": {
            "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "type": "Daily",
            "interval": 1,
            "localTimeZoneId": "UTC",
            "times": [f"{hour_utc:02d}:00"],
        },
    }
    print(f"  creating daily schedule from {body['configuration']['startDateTime']}")
    return fabric_items.call("POST", base, token, body)


def run_pipeline(ws: str, pipeline_id: str, token: str,
                 timeout_s: int = 1800) -> dict:
    resp = fabric_items._request(
        "POST",
        f"https://api.fabric.microsoft.com/v1/workspaces/{ws}/items/{pipeline_id}"
        f"/jobs/instances?jobType=Pipeline",
        token,
    )
    location = resp.headers.get("Location")
    if not location:
        raise SystemExit(f"Pipeline run accepted without a location (HTTP {resp.status})")
    print(f"  run job: {location}")
    deadline = time.time() + timeout_s
    last = "Unknown"
    while time.time() < deadline:
        payload = json.loads(
            fabric_items._request("GET", location, token).read() or b"{}"
        )
        last = payload.get("status", "Unknown")
        print(f"  {time.strftime('%H:%M:%S')} status={last}", flush=True)
        if last in ("Completed", "Failed", "Cancelled"):
            return payload
        time.sleep(10)
    raise SystemExit(f"Pipeline run timed out (last status={last})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish the daily Gold pipeline.")
    ap.add_argument("--env", default="sandbox")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true",
                    help="run the pipeline once after publishing")
    ap.add_argument("--no-schedule", action="store_true",
                    help="do not create or replace the daily schedule")
    ap.add_argument("--schedule-hour", type=int, default=6,
                    help="UTC hour for the daily schedule (default 6)")
    args = ap.parse_args()

    env_config.load(args.env)
    ws = os.environ.get("FABRIC_WORKSPACE_ID")
    if not ws:
        raise SystemExit("Missing FABRIC_WORKSPACE_ID in the profile.")
    token = fabric_items.az_token(fabric_items.FABRIC_RESOURCE)

    ids = []
    for name in NOTEBOOKS:
        item = fabric_items.find_item(ws, name, "Notebook", token)
        if not item:
            raise SystemExit(f"Notebook not found: {name}")
        ids.append(item["id"])
        print(f"{name}: {item['id']}")

    content = pipeline_content(ws, ids)
    write_local(content)
    if args.dry_run:
        print("Dry run: pipeline content generated, nothing published.")
        return 0

    defn = definition_payload(content)
    existing = fabric_items.find_item(ws, PIPELINE_NAME, "DataPipeline", token)

    if existing:
        if not args.update:
            print(f"Pipeline '{PIPELINE_NAME}' already exists ({existing['id']}). "
                  "Leaving it untouched. Use --update to replace its definition.")
            pipeline_id = existing["id"]
        else:
            print(f"Updating pipeline '{PIPELINE_NAME}' ({existing['id']}) ...",
                  flush=True)
            try:
                fabric_items.update_item_definition(
                    ws, existing["id"], defn, token
                )
            except RuntimeError:
                fabric_items.call(
                    "POST",
                    f"/workspaces/{ws}/dataPipelines/{existing['id']}/updateDefinition",
                    token,
                    {"definition": defn},
                )
            pipeline_id = existing["id"]
            print("  definition updated")
    else:
        print(f"Creating pipeline '{PIPELINE_NAME}' ...", flush=True)
        result = fabric_items.create_item(ws, {
            "displayName": PIPELINE_NAME,
            "description": PIPELINE_DESCRIPTION,
            "type": "DataPipeline",
            "definition": defn,
        }, token)
        pipeline_id = result.get("id")
        if not pipeline_id:
            item = fabric_items.find_item(ws, PIPELINE_NAME, "DataPipeline", token)
            pipeline_id = item["id"] if item else None
        if not pipeline_id:
            raise SystemExit(f"Pipeline created but id could not be resolved: {result}")
        print(f"  id: {pipeline_id}")

    print(f"\nPipeline id: {pipeline_id}")
    print(f"Workspace: {ws}")

    if not args.no_schedule:
        schedule = replace_schedule(ws, pipeline_id, token, args.schedule_hour)
        print(f"  schedule enabled: {schedule.get('enabled', 'unknown')}")

    if args.run:
        result = run_pipeline(ws, pipeline_id, token)
        print(json.dumps(result, indent=2))
        if result.get("status") != "Completed":
            return 1

    print("\nPipeline build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
