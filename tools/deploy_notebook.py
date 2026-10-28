#!/usr/bin/env python3
"""
deploy_notebook.py - publish a local .ipynb into a Fabric workspace.

SAFETY
    Default behaviour is CREATE-ONLY. If a Notebook with the same display name
    already exists, the tool reports it and exits without modifying it. Pass
    --update explicitly to replace the definition of an existing notebook.

USAGE
    python tools/deploy_notebook.py --env sandbox \
        --file fabric/notebooks/nb_01_bronze_ingest.ipynb

    python tools/deploy_notebook.py --env sandbox \
        --file fabric/notebooks/nb_01_bronze_ingest.ipynb --update

AUTH
    Uses the Azure CLI login. Sign in to the target tenant first.
"""

from __future__ import annotations

import argparse
import base64
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


def request(method: str, url: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def poll(location: str, token: str, timeout_s: int = 180) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = request("GET", location, token)
        if resp.status == 200:
            payload = json.loads(resp.read() or b"{}")
            if payload.get("status") in (None, "Succeeded"):
                return payload
            if payload.get("status") in ("Failed", "Cancelled"):
                raise SystemExit(f"Fabric operation failed: {json.dumps(payload)}")
        time.sleep(2)
    raise SystemExit(f"Timed out waiting for {location}")


def call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    resp = request(method, f"{FABRIC_API}{path}", token, body)
    if resp.status == 202:
        location = resp.headers.get("Location")
        return poll(location, token) if location else {}
    raw = resp.read()
    return json.loads(raw) if raw else {}


def find_item(ws: str, name: str, item_type: str, token: str) -> dict | None:
    data = call("GET", f"/workspaces/{ws}/items?type={item_type}", token)
    for item in data.get("value", []):
        if item.get("displayName") == name:
            return item
    return None


def definition(file: Path) -> dict:
    payload = base64.b64encode(file.read_bytes()).decode("ascii")
    return {
        "format": "ipynb",
        "parts": [{
            "path": "notebook-content.ipynb",
            "payload": payload,
            "payloadType": "InlineBase64",
        }],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish a notebook into Fabric.")
    ap.add_argument("--env", default="sandbox", help="environment profile")
    ap.add_argument("--file", required=True, help="local .ipynb file")
    ap.add_argument("--name", help="Fabric display name (default: file stem)")
    ap.add_argument("--workspace-id", help="override FABRIC_WORKSPACE_ID")
    ap.add_argument("--update", action="store_true",
                    help="replace the definition if the notebook already exists")
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

    file = Path(args.file)
    if not file.is_absolute():
        file = REPO / file
    if not file.exists():
        raise SystemExit(f"File not found: {file}")

    name = args.name or file.stem
    token = az_token(FABRIC_RESOURCE)
    existing = find_item(ws, name, "Notebook", token)
    defn = definition(file)

    if existing:
        if not args.update:
            print(f"Notebook '{name}' already exists ({existing['id']}). "
                  "Leaving it untouched. Use --update to replace its definition.")
            return 0
        print(f"Updating notebook '{name}' ({existing['id']}) ...", end=" ", flush=True)
        call("POST", f"/workspaces/{ws}/items/{existing['id']}/updateDefinition",
             token, {"definition": defn})
        print("done")
        return 0

    print(f"Creating notebook '{name}' ...", end=" ", flush=True)
    result = call("POST", f"/workspaces/{ws}/items", token, {
        "displayName": name,
        "type": "Notebook",
        "definition": defn,
    })
    print("done")
    if result.get("id"):
        print(f"  id: {result['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
