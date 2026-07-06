#!/usr/bin/env python3
"""Snapshot Chroma DB alongside platform metadata."""
from __future__ import annotations

import argparse
import os
import sys
import tarfile
from datetime import datetime
from pathlib import Path

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.core.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Chroma vector store")
    parser.add_argument("--output", default="backend/data/backups")
    args = parser.parse_args()

    src = Path(settings.CHROMA_PERSIST_DIRECTORY)
    if not src.exists():
        raise SystemExit(f"Chroma directory not found: {src}")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    archive = out_dir / f"chroma_backup_{stamp}.tar.gz"

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(src, arcname=src.name)

    print(f"Backup written to {archive}")


if __name__ == "__main__":
    main()
