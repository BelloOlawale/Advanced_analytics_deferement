#!/usr/bin/env python3
"""
fabric_query.py - read-only query tool for the NewCross EP Fabric Warehouse.

SAFETY: this tool refuses to send anything but a single SELECT / WITH statement.
It never issues DDL or DML. Combined with a read-only database role, the agent
cannot change data even if asked to.

CONFIG (from environment, or from a profile file in the repo root):
    FABRIC_ENV          profile to load: local | sandbox | customer | ...
                        (default: local, which reads `.env`)
                        sandbox reads `.env.sandbox`, etc.
    FABRIC_SQL_CONN     full connection string (takes precedence if set)
    FABRIC_SQL_SERVER   e.g. <warehouse>@<workspace>.datawarehouse.fabric.microsoft.com
    FABRIC_SQL_DATABASE warehouse / database name
    FABRIC_SQL_AUTH     default | sp | interactive | devicecode | msi   (default: default)
    FABRIC_SQL_UID      client id (sp) or UPN (interactive)
    FABRIC_SQL_PWD      client secret (sp only)
    FABRIC_SQL_TENANT   tenant id (optional)
    FABRIC_QUERY_TIMEOUT  per-statement seconds (default 300)

USAGE:
    python tools/fabric_query.py --env sandbox --show-env
    python tools/fabric_query.py --env sandbox --test
    python tools/fabric_query.py --info
    python tools/fabric_query.py "SELECT TOP 5 * FROM production.flowstations_dim"
    python tools/fabric_query.py --csv data/oml24_flowstations_dim.csv \
        "SELECT * FROM production.flowstations_dim"

Every query is appended to logs/fabric_queries.log.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import os
import re
import sys
from pathlib import Path

try:
    import env_config
except ModuleNotFoundError:  # e.g. `python -m tools.fabric_query`
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import env_config

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = REPO / "logs"
LOG_FILE = LOG_DIR / "fabric_queries.log"

# --- read-only guard -------------------------------------------------------

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|DENY|"
    r"EXEC|EXECUTE|CALL|BACKUP|RESTORE|BULK|INTO|WRITETEXT|UPDATETEXT|"
    r"sp_\w+|xp_\w+)\b",
    re.IGNORECASE,
)


def _strip_sql_literals(sql: str) -> str:
    """Remove string literals and comments so the guard can't be fooled."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)   # /* block */
    sql = re.sub(r"--[^\n]*", " ", sql)                      # -- line
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)               # 'strings'
    return sql


def assert_read_only(sql: str) -> None:
    body = _strip_sql_literals(sql).strip().rstrip(";").strip()
    if not body:
        raise SystemExit("Refused: empty statement.")
    first = body.split(None, 1)[0].upper()
    if first not in ("SELECT", "WITH"):
        raise SystemExit(
            f"Refused: only SELECT / WITH allowed (got '{first}'). "
            "This tool is read-only by design."
        )
    hit = _FORBIDDEN.search(body)
    if hit:
        raise SystemExit(
            f"Refused: statement contains forbidden keyword '{hit.group(0)}'. "
            "This tool is read-only by design."
        )


# --- config ----------------------------------------------------------------

def connection_string() -> str:
    full = os.environ.get("FABRIC_SQL_CONN")
    if full:
        return full
    server = os.environ.get("FABRIC_SQL_SERVER")
    database = os.environ.get("FABRIC_SQL_DATABASE")
    if not server or not database:
        profile = os.environ.get("FABRIC_ENV", "local")
        raise SystemExit(
            f"Missing config for profile '{profile}': set FABRIC_SQL_SERVER and "
            "FABRIC_SQL_DATABASE (or FABRIC_SQL_CONN) in the matching .env file "
            "or the environment. Run with --show-env to see what is loaded."
        )
    auth = os.environ.get("FABRIC_SQL_AUTH", "default").lower()
    auth_map = {
        "default": "ActiveDirectoryDefault",
        "sp": "ActiveDirectoryServicePrincipal",
        "serviceprincipal": "ActiveDirectoryServicePrincipal",
        "interactive": "ActiveDirectoryInteractive",
        "devicecode": "ActiveDirectoryDeviceCode",
        "msi": "ActiveDirectoryMSI",
    }
    if auth not in auth_map:
        raise SystemExit(f"Unknown FABRIC_SQL_AUTH='{auth}'.")
    parts = [
        f"Server={server}",
        f"Database={database}",
        f"Authentication={auth_map[auth]}",
        "Encrypt=yes",
        # read-only intent (documentation of intent; the role enforces it)
        "ApplicationIntent=ReadOnly",
    ]
    if os.environ.get("FABRIC_SQL_UID"):
        parts.append(f"UID={os.environ['FABRIC_SQL_UID']}")
    if os.environ.get("FABRIC_SQL_PWD"):
        parts.append(f"PWD={os.environ['FABRIC_SQL_PWD']}")
    # NB: mssql-python rejects TenantId in the connection string. Tenant is
    # selected via the isolated AZURE_CONFIG_DIR / az login instead.
    return ";".join(parts) + ";"


# --- logging ---------------------------------------------------------------

def log(sql: str, status: str, rows: int | None, secs: float) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    one_line = " ".join(sql.split())
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{ts}\t{status}\trows={rows}\t{secs:.2f}s\t{one_line}\n")


# --- run -------------------------------------------------------------------

def run(sql: str, csv_path: str | None = None, max_print: int = 50) -> int:
    import mssql_python  # imported lazily so --help works without the driver

    assert_read_only(sql)
    conn_str = connection_string()
    timeout = int(os.environ.get("FABRIC_QUERY_TIMEOUT", "300"))

    started = _dt.datetime.now()
    try:
        with mssql_python.connect(conn_str, timeout=30) as conn:
            conn.timeout = timeout
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
    except Exception as exc:  # noqa: BLE001
        log(sql, f"ERROR:{type(exc).__name__}", None, (_dt.datetime.now() - started).total_seconds())
        print(f"Query failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    secs = (_dt.datetime.now() - started).total_seconds()
    log(sql, "OK", len(rows), secs)

    if csv_path:
        out = Path(csv_path)
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            w.writerows(rows)
        print(f"Wrote {len(rows)} rows x {len(cols)} cols -> {out}  ({secs:.2f}s)")
        return 0

    print(f"{len(rows)} rows, {len(cols)} cols, {secs:.2f}s\n")
    print(" | ".join(cols))
    print("-" * 80)
    for r in rows[:max_print]:
        print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows) > max_print:
        print(f"... ({len(rows) - max_print} more; use --csv to save all)")
    return 0


def info() -> int:
    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
        "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA NOT IN "
        "('sys','INFORMATION_SCHEMA','queryinsights') "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
    )
    return run(sql, max_print=500)


def show_env() -> int:
    """Print the active profile with secrets redacted."""
    info = env_config.load()  # idempotent; already loaded by main()
    print(f"profile : {info['profile']}")
    print(f"file    : {info['file']}  ({'found' if info['found'] else 'NOT FOUND'})")
    print()
    width = max(len(k) for k, _ in env_config.describe())
    for key, value in env_config.describe():
        print(f"{key.ljust(width)} : {value}")
    return 0 if info["found"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Fabric Warehouse query tool.")
    ap.add_argument("sql", nargs="?", help="a single SELECT/WITH statement")
    ap.add_argument("--csv", help="write the full result to this CSV path")
    ap.add_argument("--test", action="store_true", help="connect and SELECT 1")
    ap.add_argument("--info", action="store_true", help="list tables/columns")
    ap.add_argument("--max-print", type=int, default=50)
    ap.add_argument(
        "--env",
        help="environment profile to load (default: FABRIC_ENV or 'local')",
    )
    ap.add_argument(
        "--show-env",
        action="store_true",
        help="show the active profile and connection settings (secrets redacted)",
    )
    args = ap.parse_args()

    env_config.load(args.env)

    if args.show_env:
        return show_env()
    if args.test:
        return run("SELECT 1 AS ok")
    if args.info:
        return info()
    if not args.sql:
        ap.print_help()
        return 2
    return run(args.sql, csv_path=args.csv, max_print=args.max_print)


if __name__ == "__main__":
    raise SystemExit(main())
