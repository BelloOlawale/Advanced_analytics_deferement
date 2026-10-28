#!/usr/bin/env python3
"""
provision_sandbox.py - create a clean build area in an existing Fabric workspace.

SAFETY
    This tool only CREATES new items. It never edits, deletes or uploads into an
    item that already existed. If a name is already taken, it is skipped and
    reported, so existing work in the workspace is left untouched.

WHAT IT DOES
    1. Resolves the workspace from the active env profile (FABRIC_WORKSPACE_ID).
    2. Creates any missing lakehouses (default: lh_bronze, lh_silver, lh_gold).
    3. Optionally uploads test_data/<env>/{raw,ref}/*.csv into lh_bronze/Files.
    4. Writes test_data/<env>/_fabric_items.json with IDs and endpoints.

USAGE
    python tools/provision_sandbox.py --env sandbox --dry-run
    python tools/provision_sandbox.py --env sandbox
    python tools/provision_sandbox.py --env sandbox --upload
    python tools/provision_sandbox.py --env sandbox --upload --overwrite

AUTH
    Uses the Azure CLI login (`az account get-access-token`). Sign in to the
    target tenant first: `az login --tenant <domain-or-id>`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FABRIC_API = "https://api.fabric.microsoft.com/v1"
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
STORAGE_RESOURCE = "https://storage.azure.com/"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"

DEFAULT_LAKEHOUSES = ["lh_bronze", "lh_silver", "lh_gold"]


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------

def az_token(resource: str) -> str:
    args = ["account", "get-access-token", "--resource", resource,
            "--query", "accessToken", "-o", "tsv"]
    if os.name == "nt":
        # `az` is a .cmd shim on Windows; shell=True resolves it reliably.
        out = subprocess.check_output("az " + " ".join(args), shell=True, text=True)
    else:
        out = subprocess.check_output(["az", *args], text=True)
    token = out.strip()
    if not token:
        raise SystemExit(f"Could not get a token for {resource}. Run `az login` first.")
    return token


# ---------------------------------------------------------------------------
# Fabric REST
# ---------------------------------------------------------------------------

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
        raise SystemExit(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def _poll(location: str, token: str, timeout_s: int = 180) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = _request("GET", location, token)
        if resp.status == 200:
            payload = json.loads(resp.read() or b"{}")
            status = payload.get("status")
            if status in (None, "Succeeded"):
                return payload
            if status in ("Failed", "Cancelled"):
                raise SystemExit(f"Fabric operation failed: {json.dumps(payload)}")
        time.sleep(2)
    raise SystemExit(f"Timed out waiting for Fabric operation: {location}")


def fabric_call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    resp = _request(method, f"{FABRIC_API}{path}", token, body)
    if resp.status == 202:
        location = resp.headers.get("Location")
        if not location:
            return {}
        return _poll(location, token)
    raw = resp.read()
    return json.loads(raw) if raw else {}


def list_lakehouses(ws: str, token: str) -> dict[str, dict]:
    data = fabric_call("GET", f"/workspaces/{ws}/lakehouses", token)
    return {lh["displayName"]: lh for lh in data.get("value", [])}


def create_lakehouse(ws: str, name: str, token: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would create lakehouse '{name}'")
        return
    print(f"  creating lakehouse '{name}' ...", end=" ", flush=True)
    fabric_call("POST", f"/workspaces/{ws}/lakehouses", token,
                {"displayName": name, "description": ""})
    print("done")


# ---------------------------------------------------------------------------
# OneLake (DFS) upload
# ---------------------------------------------------------------------------

def _storage_headers(token: str, length: int | None = None,
                     content_type: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "x-ms-version": "2022-11-02"}
    if length is not None:
        h["Content-Length"] = str(length)
    if content_type:
        h["Content-Type"] = content_type
    return h


def ensure_dir(url: str, token: str) -> None:
    req = urllib.request.Request(url + "?resource=directory", data=b"",
                                 method="PUT", headers=_storage_headers(token, 0))
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        if exc.code != 409:  # 409 = already exists
            raise SystemExit(f"mkdir {url} -> HTTP {exc.code}: "
                             f"{exc.read().decode('utf-8', 'replace')}") from exc


def delete_file(url: str, token: str) -> None:
    req = urllib.request.Request(url + "?recursive=false", method="DELETE",
                                 headers=_storage_headers(token, 0))
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise


def upload_file(url: str, local: Path, token: str, overwrite: bool) -> None:
    data = local.read_bytes()
    size = len(data)

    create = urllib.request.Request(url + "?resource=file", data=b"", method="PUT",
                                    headers=_storage_headers(token, 0))
    try:
        urllib.request.urlopen(create)
    except urllib.error.HTTPError as exc:
        if exc.code == 409 and overwrite:
            delete_file(url, token)
            create = urllib.request.Request(url + "?resource=file", data=b"",
                                            method="PUT", headers=_storage_headers(token, 0))
            urllib.request.urlopen(create)
        elif exc.code == 409:
            print(f"    skip (exists): {local.name}")
            return
        else:
            raise SystemExit(f"create {url} -> HTTP {exc.code}: "
                             f"{exc.read().decode('utf-8', 'replace')}") from exc

    append = urllib.request.Request(
        url + "?action=append&position=0", data=data, method="PATCH",
        headers=_storage_headers(token, size, "application/octet-stream"))
    urllib.request.urlopen(append)

    flush = urllib.request.Request(
        url + f"?action=flush&position={size}", data=b"", method="PATCH",
        headers=_storage_headers(token, 0))
    urllib.request.urlopen(flush)
    print(f"    uploaded {local.name} ({size:,} bytes)")


def upload_seed(ws: str, lh_id: str, data_dir: Path, token: str,
                overwrite: bool, dry_run: bool) -> list[str]:
    base = f"{ONELAKE}/{ws}/{lh_id}/Files"
    uploaded: list[str] = []
    for sub in ("raw", "ref"):
        local_dir = data_dir / sub
        if not local_dir.is_dir():
            continue
        if dry_run:
            for f in sorted(local_dir.glob("*.csv")):
                print(f"  [dry-run] would upload {sub}/{f.name} -> lh_bronze/Files/{sub}/")
            continue
        ensure_dir(f"{base}/{sub}", token)
        for f in sorted(local_dir.glob("*.csv")):
            print(f"  uploading {sub}/{f.name} ...")
            upload_file(f"{base}/{sub}/{f.name}", f, token, overwrite)
            uploaded.append(f"Files/{sub}/{f.name}")
    return uploaded


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Create a clean build area in Fabric.")
    ap.add_argument("--env", default="sandbox", help="environment profile (default: sandbox)")
    ap.add_argument("--workspace-id", help="override FABRIC_WORKSPACE_ID")
    ap.add_argument("--lakehouses", nargs="+", default=DEFAULT_LAKEHOUSES,
                    help="lakehouse names to create (default: lh_bronze lh_silver lh_gold)")
    ap.add_argument("--data-dir", help="seed data folder (default: test_data/<env>)")
    ap.add_argument("--upload", action="store_true", help="upload raw/ and ref/ into lh_bronze")
    ap.add_argument("--overwrite", action="store_true", help="overwrite files if they already exist")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, make no changes")
    args = ap.parse_args()

    # Load the profile so AZURE_CONFIG_DIR / tenant match the target.
    try:
        import env_config
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import env_config
    env_config.load(args.env)

    ws = args.workspace_id or os.environ.get("FABRIC_WORKSPACE_ID")
    if not ws:
        raise SystemExit("Missing workspace ID: set FABRIC_WORKSPACE_ID in the profile "
                         "or pass --workspace-id.")

    data_dir = Path(args.data_dir) if args.data_dir else REPO / "test_data" / args.env
    fabric_token = az_token(FABRIC_RESOURCE)

    print(f"Profile     : {os.environ.get('FABRIC_ENV', args.env)}")
    print(f"Workspace   : {ws}")
    print(f"Seed data   : {data_dir}")
    print(f"Mode        : {'DRY RUN' if args.dry_run else 'APPLY'}")
    print()

    existing = list_lakehouses(ws, fabric_token)
    print(f"Existing lakehouses ({len(existing)}): {', '.join(sorted(existing)) or '(none)'}")
    print()

    created: dict[str, str] = {}
    skipped: list[str] = []
    for name in args.lakehouses:
        if name in existing:
            skipped.append(name)
            print(f"  '{name}' already exists - leaving it untouched")
            continue
        create_lakehouse(ws, name, fabric_token, args.dry_run)
        created[name] = "pending"

    if args.dry_run:
        if args.upload:
            print("\nUpload plan:")
            upload_seed(ws, "<lh_bronze-id>", data_dir, "<token>", args.overwrite, True)
        print("\nDry run complete. No changes made.")
        return 0

    # Refresh so we have IDs for everything we need, including just-created items.
    after = list_lakehouses(ws, fabric_token)
    for name in args.lakehouses:
        if name in after:
            created.setdefault(name, after[name]["id"])

    uploaded: list[str] = []
    if args.upload:
        if "lh_bronze" not in after:
            raise SystemExit("Cannot upload: 'lh_bronze' does not exist.")
        if "lh_bronze" in skipped and not args.overwrite:
            raise SystemExit(
                "Refusing to upload into pre-existing 'lh_bronze'. "
                "This tool must not modify existing items. Use a new name or "
                "pass --overwrite deliberately."
            )
        storage_token = az_token(STORAGE_RESOURCE)
        print(f"\nUploading seed data into lh_bronze ({after['lh_bronze']['id']}) ...")
        uploaded = upload_seed(ws, after["lh_bronze"]["id"], data_dir,
                               storage_token, args.overwrite, False)

    # Save the IDs/endpoints for the next step.
    record = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "workspace_id": ws,
        "lakehouses": {
            name: {
                "id": lh["id"],
                "sql_endpoint": lh.get("properties", {}).get("sqlEndpointProperties", {}).get("connectionString"),
            }
            for name, lh in after.items()
            if name in args.lakehouses
        },
        "uploaded": uploaded,
    }
    if data_dir.is_dir():
        out = data_dir / "_fabric_items.json"
        out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {out}")
    else:
        print(f"\nNote: {data_dir} does not exist; skipped writing _fabric_items.json")

    print("\nLakehouses:")
    for name, info in record["lakehouses"].items():
        print(f"  {name:<12} {info['id']}  {info['sql_endpoint'] or ''}")
    print(f"\nCreated {len(created)} new item(s); skipped {len(skipped)} existing item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
