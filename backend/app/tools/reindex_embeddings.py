"""Re-embed existing fabrics with the active embedding model.

Run inside the backend container (or the backend venv):

    python -m app.tools.reindex_embeddings                 # every fabric in the store
    python -m app.tools.reindex_embeddings --fabric <id>   # one fabric (repeatable)
    python -m app.tools.reindex_embeddings --status        # report only
    python -m app.tools.reindex_embeddings --include-orphans --purge-legacy

Non-destructive unless ``--purge-legacy`` is given.
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fabric", action="append", default=[], help="Fabric id to re-index (repeatable)")
    parser.add_argument("--status", action="store_true", help="Only report which fabrics need re-indexing")
    parser.add_argument("--include-orphans", action="store_true",
                        help="Also migrate legacy chunks whose fabric record no longer exists")
    parser.add_argument("--purge-legacy", action="store_true",
                        help="Delete a fabric's old vectors after its copy is verified")
    args = parser.parse_args()

    from app.services.platform.fabric_store import fabric_store
    from app.services.platform.reindex import embedding_status, reindex_fabrics

    fabric_store.initialize()

    if args.status:
        print(json.dumps(embedding_status(), indent=2, default=str))
        return 0

    last = {"pct": -5.0}

    def on_progress(pct: float, message: str) -> None:
        if pct - last["pct"] >= 5.0 or pct >= 100.0:
            last["pct"] = pct
            print(f"[{pct:5.1f}%] {message}", flush=True)

    summary = reindex_fabrics(
        args.fabric or None,
        include_orphans=args.include_orphans,
        purge_legacy=args.purge_legacy,
        progress=on_progress,
    )
    brief = {k: v for k, v in summary.items() if k != "results"}
    print(json.dumps(brief, indent=2, default=str))
    for row in summary["results"]:
        print(f"  {row.get('status', '?'):11s} {int(row.get('chunks') or 0):7d}  {row.get('source_id')}")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
