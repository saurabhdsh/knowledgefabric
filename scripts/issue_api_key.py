#!/usr/bin/env python3
"""
Inbound API key admin CLI
=========================

Mint, list, and revoke inbound API keys that external agents use to call
the Knowledge Fabric backend over HTTPS (ngrok / public hosts).

Storage is the same JSON file the FastAPI middleware reads, so keys take
effect immediately — no backend restart needed.

Usage
-----
    # Issue a new key for the CSNP CLI
    python scripts/issue_api_key.py issue \\
        --name "csnp-cli" \\
        --description "External CSNP operations console" \\
        --scopes query

    # Restrict the key to specific fabrics
    python scripts/issue_api_key.py issue \\
        --name "partner-acme" \\
        --fabric-ids fb_123,fb_456

    # Add an expiry (YYYY-MM-DD)
    python scripts/issue_api_key.py issue --name "demo" --expires-at 2026-12-31

    # List
    python scripts/issue_api_key.py list

    # Revoke
    python scripts/issue_api_key.py revoke --id <key-id>

NOTE: the plain key is shown ONLY at issuance time. Save it then; the
server only stores its hash.
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the backend package importable when running from the repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(os.path.dirname(_HERE), "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.services.inbound_api_key_service import (  # noqa: E402
    inbound_api_key_service,
)

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    _RICH = True
    _console = Console()
except ImportError:  # pragma: no cover — rich is optional
    _RICH = False
    _console = None  # type: ignore[assignment]


def _print(msg: str = "") -> None:
    if _RICH:
        _console.print(msg)
    else:
        print(msg)


def cmd_issue(args: argparse.Namespace) -> int:
    scopes = [s.strip() for s in (args.scopes or "query").split(",") if s.strip()]
    fabric_ids = (
        [f.strip() for f in args.fabric_ids.split(",") if f.strip()]
        if args.fabric_ids
        else None
    )
    record, plain = inbound_api_key_service.issue(
        name=args.name,
        description=args.description or "",
        scopes=scopes,
        fabric_ids=fabric_ids,
        expires_at=args.expires_at,
    )

    if _RICH:
        body = Text()
        body.append("Key ID:       ", style="bold")
        body.append(f"{record.id}\n")
        body.append("Name:         ", style="bold")
        body.append(f"{record.name}\n")
        body.append("Description:  ", style="bold")
        body.append(f"{record.description or '—'}\n")
        body.append("Scopes:       ", style="bold")
        body.append(f"{', '.join(record.scopes)}\n")
        body.append("Fabric scope: ", style="bold")
        body.append(
            "all fabrics\n"
            if not record.fabric_ids
            else f"{', '.join(record.fabric_ids)}\n"
        )
        body.append("Created:      ", style="bold")
        body.append(f"{record.created_at}\n")
        if record.expires_at:
            body.append("Expires:      ", style="bold")
            body.append(f"{record.expires_at}\n")
        _console.print(Panel(body, title="API key issued", box=box.ROUNDED, border_style="green"))

        _console.print()
        _console.print(
            Panel(
                Text(plain, style="bold green"),
                title="Plain key — copy now, this is the only time it will be shown",
                border_style="yellow",
                box=box.HEAVY,
            )
        )
        _console.print()
        _console.print(
            "[bold]How to use it[/bold]:\n"
            f"  export KF_API_KEY={plain}\n"
            "  # then call the API with header:  X-API-Key: $KF_API_KEY"
        )
    else:
        print(f"Key ID:      {record.id}")
        print(f"Name:        {record.name}")
        print(f"Scopes:      {', '.join(record.scopes)}")
        print(f"Created:     {record.created_at}")
        print("\n--- PLAIN KEY (save this — shown only once) ---")
        print(plain)
        print("------------------------------------------------")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    keys = inbound_api_key_service.list()
    if not keys:
        _print("No inbound API keys issued yet. Use `issue` to mint one.")
        return 0

    if _RICH:
        tbl = Table(title="Inbound API keys", box=box.SIMPLE_HEAVY)
        tbl.add_column("ID", style="cyan")
        tbl.add_column("Name")
        tbl.add_column("Prefix", style="dim")
        tbl.add_column("Scopes")
        tbl.add_column("Fabrics")
        tbl.add_column("Created", style="dim")
        tbl.add_column("Last used", style="dim")
        tbl.add_column("Status")
        for k in keys:
            status = (
                "[red]revoked[/red]"
                if k.revoked
                else ("[yellow]expires " + k.expires_at + "[/yellow]" if k.expires_at else "[green]active[/green]")
            )
            tbl.add_row(
                k.id,
                k.name,
                k.display_prefix + "…",
                ", ".join(k.scopes),
                "all" if not k.fabric_ids else ", ".join(k.fabric_ids),
                k.created_at[:19],
                (k.last_used_at or "—")[:19] if k.last_used_at else "—",
                status,
            )
        _console.print(tbl)
    else:
        for k in keys:
            tag = "revoked" if k.revoked else "active"
            print(
                f"{k.id}\t{k.name}\t{k.display_prefix}…\t"
                f"{','.join(k.scopes)}\t{tag}\tcreated={k.created_at}"
            )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    ok = inbound_api_key_service.revoke(args.id)
    if ok:
        _print(f"[green]Revoked[/green] key {args.id}" if _RICH else f"Revoked {args.id}")
        return 0
    _print(
        f"[red]No key found[/red] with id {args.id}"
        if _RICH
        else f"No key found with id {args.id}"
    )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="issue_api_key",
        description="Mint / list / revoke inbound Knowledge Fabric API keys.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_issue = sub.add_parser("issue", help="Issue a new API key")
    p_issue.add_argument("--name", required=True, help="Human-friendly identifier (e.g. 'csnp-cli')")
    p_issue.add_argument("--description", default="", help="Free-form description")
    p_issue.add_argument(
        "--scopes",
        default="query",
        help="Comma-separated scopes. Default: 'query'.",
    )
    p_issue.add_argument(
        "--fabric-ids",
        help="Optional comma-separated fabric IDs to restrict this key to.",
    )
    p_issue.add_argument(
        "--expires-at",
        help="Optional expiry date (YYYY-MM-DD or full ISO timestamp).",
    )
    p_issue.set_defaults(func=cmd_issue)

    p_list = sub.add_parser("list", help="List all issued keys")
    p_list.set_defaults(func=cmd_list)

    p_revoke = sub.add_parser("revoke", help="Revoke a key by ID")
    p_revoke.add_argument("--id", required=True, help="Key ID returned at issuance")
    p_revoke.set_defaults(func=cmd_revoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
