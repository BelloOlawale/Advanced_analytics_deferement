#!/usr/bin/env python3
"""Small shared client for the Fabric and Power BI REST APIs.

AUTH
    Uses the Azure CLI login. The Fabric API and the Power BI API use different
    token audiences, so both are exposed.

LRO
    Fabric item create/update calls return 202 with a ``Location`` that points
    at an operation. ``call`` polls the operation and then reads its
    ``/result`` payload, which is where the created item or definition lives.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"
POWERBI_RESOURCE = "https://analysis.windows.net/powerbi/api"


def az_token(resource: str) -> str:
    args = ["account", "get-access-token", "--resource", resource,
            "--query", "accessToken", "-o", "tsv"]
    if os.name == "nt":
        out = subprocess.check_output("az " + " ".join(args), shell=True, text=True)
    else:
        out = subprocess.check_output(["az", *args], text=True)
    return out.strip()


def _request(method: str, url: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def _poll(location: str, token: str, timeout_s: int = 300) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = _request("GET", location, token)
        payload = json.loads(resp.read() or b"{}")
        status = payload.get("status")
        if status in (None, "Succeeded"):
            # The operation result carries the item/definition payload.
            try:
                result = _request("GET", location.rstrip("/") + "/result", token)
                raw = result.read()
                return json.loads(raw) if raw else payload
            except RuntimeError:
                return payload
        if status in ("Failed", "Cancelled"):
            raise RuntimeError(f"Fabric operation failed: {json.dumps(payload)}")
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {location}")


def call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    """Call the Fabric API. ``path`` starts with ``/``."""
    resp = _request(method, f"{FABRIC_API}{path}", token, body)
    if resp.status == 202:
        location = resp.headers.get("Location")
        if not location:
            return {}
        return _poll(location, token)
    raw = resp.read()
    return json.loads(raw) if raw else {}


def find_item(ws: str, name: str, item_type: str, token: str) -> dict | None:
    data = call("GET", f"/workspaces/{ws}/items?type={item_type}", token)
    for item in data.get("value", []):
        if item.get("displayName") == name:
            return item
    return None


def list_items(ws: str, item_type: str, token: str) -> list[dict]:
    data = call("GET", f"/workspaces/{ws}/items?type={item_type}", token)
    return data.get("value", [])


def create_item(ws: str, body: dict, token: str) -> dict:
    return call("POST", f"/workspaces/{ws}/items", token, body)


def update_item_definition(ws: str, item_id: str, definition: dict, token: str) -> dict:
    return call("POST", f"/workspaces/{ws}/items/{item_id}/updateDefinition",
                token, {"definition": definition})


def get_item_definition(ws: str, item_id: str, token: str) -> dict:
    return call("POST", f"/workspaces/{ws}/items/{item_id}/getDefinition", token, {})


# --- Power BI -------------------------------------------------------------

def start_refresh(ws: str, model_id: str, token: str) -> None:
    resp = _request(
        "POST",
        f"{POWERBI_API}/groups/{ws}/datasets/{model_id}/refreshes",
        token,
        {"notifyOption": "NoNotification"},
    )
    if resp.status not in (200, 202):
        raise RuntimeError(f"Refresh start returned HTTP {resp.status}")


def refresh_history(ws: str, model_id: str, token: str, top: int = 1) -> list[dict]:
    resp = _request(
        "GET",
        f"{POWERBI_API}/groups/{ws}/datasets/{model_id}/refreshes?$top={top}",
        token,
    )
    return json.loads(resp.read() or b"{}").get("value", [])


def wait_for_refresh(ws: str, model_id: str, token: str,
                     timeout_s: int = 300, interval_s: int = 3) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        history = refresh_history(ws, model_id, token)
        if history:
            latest = history[0]
            status = latest.get("status")
            if status in ("Completed", "Failed"):
                return latest
        time.sleep(interval_s)
    raise RuntimeError("Timed out waiting for semantic model refresh")


def execute_dax(ws: str, model_id: str, query: str, token: str) -> dict:
    body = {
        "queries": [{"query": query}],
        "serializerSettings": {"includeNulls": True},
    }
    resp = _request(
        "POST",
        f"{POWERBI_API}/groups/{ws}/datasets/{model_id}/executeQueries",
        token,
        body,
    )
    return json.loads(resp.read())


def dax_rows(payload: dict) -> list[dict]:
    """Flatten the executeQueries response to a list of row dicts."""
    rows: list[dict] = []
    for table in payload.get("results", []):
        for row in table.get("tables", []):
            for r in row.get("rows", []):
                rows.append(r)
    return rows
