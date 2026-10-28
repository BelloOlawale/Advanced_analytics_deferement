#!/usr/bin/env python3
"""
run_notebook.py - trigger a Fabric notebook run and poll it to completion.

SAFETY
    Runs an existing notebook item only. It never changes a definition.
    The notebook itself may write tables; that is its job.

USAGE
    python tools/run_notebook.py --env sandbox --name nb_03_gold_features
    python tools/run_notebook.py --env sandbox --id <notebook-item-id> --timeout 1800

AUTH
    Uses the Azure CLI login. Sign in to the target tenant first.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"


def az_token(resource: str) -> str:
    args = ["account", "get-access-token", "--resource", resource,
            "--query", "accessToken", "-o", "tsv"]
    if os.name == "nt":
        out = subprocess.check_output("az " + " ".join(args), shell=True, text=True)
    else:
        out = subprocess.check_output(["az", *args], text=True)
    return out.strip()


def request(method: str, url: str, token: str):
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}, method=method
    )
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def find_item(ws: str, name: str, token: str) -> dict:
    resp = request("GET", f"{FABRIC_API}/workspaces/{ws}/items?type=Notebook", token)
    data = json.loads(resp.read() or b"{}")
    matches = [i for i in data.get("value", []) if i.get("displayName") == name]
    if not matches:
        raise SystemExit(f"Notebook '{name}' not found in workspace {ws}.")
    return matches[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a Fabric notebook and wait.")
    ap.add_argument("--env", default="sandbox", help="environment profile")
    ap.add_argument("--name", help="notebook display name")
    ap.add_argument("--id", help="notebook item id (skips name lookup)")
    ap.add_argument("--workspace-id", help="override FABRIC_WORKSPACE_ID")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds to wait")
    ap.add_argument("--interval", type=int, default=10, help="poll seconds")
    args = ap.parse_args()

    try:
        import env_config
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import env_config
    env_config.load(args.env)

    ws = args.workspace_id or os.environ.get("FABRIC_WORKSPACE_ID")
    if not ws:
        raise SystemExit("Missing FABRIC_WORKSPACE_ID in the profile or --workspace-id.")
    if not args.name and not args.id:
        raise SystemExit("Pass --name or --id.")

    token = az_token(FABRIC_RESOURCE)
    item = {"id": args.id, "displayName": args.name or args.id} if args.id else find_item(ws, args.name, token)
    item_id = item["id"]
    label = item.get("displayName", item_id)
    print(f"Starting '{label}' ({item_id}) ...", flush=True)

    start = request(
        "POST",
        f"{FABRIC_API}/workspaces/{ws}/items/{item_id}/jobs/instances?jobType=RunNotebook",
        token,
    )
    location = start.headers.get("Location")
    if not location:
        print(f"HTTP {start.status}: run accepted without a job location.")
        return 0
    print(f"  job: {location}")

    deadline = time.time() + args.timeout
    status = "Unknown"
    while time.time() < deadline:
        resp = request("GET", location, token)
        payload = json.loads(resp.read() or b"{}")
        status = payload.get("status", "Unknown")
        print(f"  {time.strftime('%H:%M:%S')} status={status}", flush=True)
        if status in ("Completed", "Succeeded"):
            print("Run completed.")
            return 0
        if status in ("Failed", "Cancelled", "Deduped"):
            print(json.dumps(payload, indent=2))
            return 1
        time.sleep(args.interval)

    print(f"Timed out after {args.timeout}s (last status={status}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
