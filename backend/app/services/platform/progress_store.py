"""Disk-backed progress store so uvicorn --reload does not lose fabric progress."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def _root() -> Path:
    root = Path(settings.UPLOAD_DIR) / "progress"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(progress_id: str) -> Path:
    safe = "".join(c for c in progress_id if c.isalnum() or c in ("_", "-", "."))
    return _root() / f"{safe}.json"


class ProgressStore:
    """dict-like store persisted as one JSON file per progress_id."""

    def __contains__(self, progress_id: object) -> bool:
        if not isinstance(progress_id, str):
            return False
        return _path(progress_id).exists()

    def __getitem__(self, progress_id: str) -> Dict[str, Any]:
        data = self.get(progress_id)
        if data is None:
            raise KeyError(progress_id)
        return data

    def __setitem__(self, progress_id: str, value: Dict[str, Any]) -> None:
        self.set(progress_id, value)

    def __delitem__(self, progress_id: str) -> None:
        self.delete(progress_id)

    def get(self, progress_id: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        path = _path(progress_id)
        if not path.exists():
            return default
        try:
            with _lock:
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed reading progress %s: %s", progress_id, exc)
            return default

    def set(self, progress_id: str, value: Dict[str, Any]) -> None:
        path = _path(progress_id)
        tmp = path.with_suffix(".tmp")
        payload = json.dumps(value, default=str)
        with _lock:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)

    def delete(self, progress_id: str) -> None:
        path = _path(progress_id)
        with _lock:
            if path.exists():
                path.unlink()

    def keys(self) -> Iterator[str]:
        for path in _root().glob("*.json"):
            yield path.stem


progress_store = ProgressStore()
