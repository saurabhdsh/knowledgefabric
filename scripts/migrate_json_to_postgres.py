#!/usr/bin/env python3
"""Migrate fabrics.json and ontology file data into platform database."""
from __future__ import annotations

import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.core.config import settings  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.services.platform.fabric_store import fabric_store  # noqa: E402


def main() -> None:
    init_db()
    fabric_store.initialize()
    fabrics_path = os.path.join(settings.DATA_DIR, "fabrics.json")
    count = len(fabric_store.list_all_dicts())
    print(f"Platform DB ready — {count} fabric(s) in store")
    if os.path.exists(fabrics_path):
        with open(fabrics_path, encoding="utf-8") as f:
            raw = json.load(f)
        print(f"JSON backup at {fabrics_path} ({len(raw)} records)")


if __name__ == "__main__":
    main()
