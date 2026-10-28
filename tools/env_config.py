#!/usr/bin/env python3
"""
env_config.py - one environment profile per Fabric tenant/workspace.

WHY
    The repository used a single `.env` file. Switching to a customer or test
    tenant meant editing that file, which risks pointing the wrong environment
    at the wrong data. Profiles make the choice explicit and non-destructive.

HOW IT WORKS
    A profile is a plain env file in the repo root:

        .env            -> the "local" profile (backwards compatible)
        .env.sandbox    -> the "sandbox" profile (new/test tenant)
        .env.customer   -> the "customer" profile

    Select one with either:

        FABRIC_ENV=sandbox python tools/fabric_query.py --test
        python tools/fabric_query.py --env sandbox --test

    Exactly ONE env file is loaded per run. Profiles never layer on top of each
    other, so a sandbox run can never inherit the customer's server by accident.

PRECEDENCE
    Real OS environment variables always win over values in the file. That lets
    CI/Key Vault override a file without editing it.

SECRETS
    `.env*` files are git-ignored except `.env.example`. Never commit a real
    secret or paste one into chat.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = "local"

# Keys we never print in full.
_SENSITIVE = ("PWD", "SECRET", "KEY", "TOKEN", "CONN", "PASSWORD")


def profile_name(explicit: str | None = None) -> str:
    """Resolve the active profile: explicit arg > FABRIC_ENV > 'local'."""
    raw = explicit or os.environ.get("FABRIC_ENV") or DEFAULT_PROFILE
    name = raw.strip().lower()
    if not name:
        name = DEFAULT_PROFILE
    # keep filenames predictable and safe
    if not all(c.isalnum() or c in "-_." for c in name):
        raise SystemExit(
            f"Invalid environment name {raw!r}. Use letters, digits, '-' or '_'."
        )
    return name


def profile_file(explicit: str | None = None) -> Path:
    """The env file for a profile. 'local' keeps the old `.env` name."""
    name = profile_name(explicit)
    return REPO / (".env" if name == DEFAULT_PROFILE else f".env.{name}")


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load(explicit: str | None = None) -> dict[str, object]:
    """
    Load a single profile into os.environ (without overriding real env vars).

    Returns a small description dict so callers can show which profile is live.
    A missing file is not fatal: callers that need config will report it.
    """
    name = profile_name(explicit)
    path = profile_file(name)

    info: dict[str, object] = {
        "profile": name,
        "file": str(path),
        "found": path.exists(),
        "loaded_keys": [],
    }

    if not path.exists():
        # Still pin the profile and an isolated Azure login cache.
        os.environ["FABRIC_ENV"] = name
        os.environ.setdefault(
            "AZURE_CONFIG_DIR", str(Path.home() / ".azure-fabric" / name)
        )
        return info

    values = _parse_env_file(path)
    for key, value in values.items():
        # OS env wins; file fills the gaps.
        os.environ.setdefault(key, value)

    os.environ["FABRIC_ENV"] = name
    # A different tenant needs a different token cache. If the profile does not
    # set one, give each profile its own so `az login` for sandbox cannot be
    # reused for customer.
    os.environ.setdefault(
        "AZURE_CONFIG_DIR",
        str(Path.home() / ".azure-fabric" / name),
    )

    info["loaded_keys"] = sorted(values)
    return info


def redacted(key: str, value: str) -> str:
    """Hide secrets; show enough of everything else to confirm the target."""
    upper = key.upper()
    if any(marker in upper for marker in _SENSITIVE):
        return "***set***" if value else ""
    return value


def describe() -> list[tuple[str, str]]:
    """The active config as (key, display value) pairs, secrets redacted."""
    keys = [
        "FABRIC_ENV",
        "FABRIC_WORKSPACE_NAME",
        "FABRIC_WORKSPACE_ID",
        "FABRIC_CAPACITY_NAME",
        "FABRIC_CAPACITY_ID",
        "FABRIC_CAPACITY_SKU",
        "FABRIC_CAPACITY_REGION",
        "FABRIC_SQL_SERVER",
        "FABRIC_SQL_DATABASE",
        "FABRIC_SQL_AUTH",
        "FABRIC_SQL_UID",
        "FABRIC_SQL_PWD",
        "FABRIC_SQL_TENANT",
        "FABRIC_SQL_CONN",
        "AZURE_CONFIG_DIR",
    ]
    return [(k, redacted(k, os.environ.get(k, ""))) for k in keys]
