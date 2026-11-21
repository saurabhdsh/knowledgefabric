"""Registry of uploaded files: stored name <-> original name, owner, checksum.

Uploads are stored on disk under a random name. Before Release 2.0 the original
name was thrown away, so a PDF fabric could not tell which files the request
meant and picked the most recent uploads. This sidecar keeps the mapping so a
fabric is always built from exactly the files that were named.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.user_context import get_current_user_id

logger = logging.getLogger(__name__)

_REGISTRY_FILE = "upload_registry.json"


class UploadNotFoundError(LookupError):
    """A file named in a request is not a known upload."""


class UploadRegistry:
    def __init__(self, upload_dir: Optional[str] = None, registry_path: Optional[str] = None) -> None:
        self.upload_dir = upload_dir or settings.UPLOAD_DIR
        # Kept in the data directory, not next to the uploads: the upload
        # directory is served as static files.
        self._path = registry_path or os.path.join(settings.DATA_DIR, _REGISTRY_FILE)
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as exc:
            logger.warning("Upload registry unreadable (%s); starting empty", exc)
            return {}

    def _save(self, data: Dict[str, Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, self._path)

    def register(self, stored_path: str, original_name: str, content: bytes) -> Dict[str, Any]:
        stored_name = os.path.basename(stored_path)
        entry = {
            "stored_name": stored_name,
            "original_name": os.path.basename(original_name or stored_name),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "owner_id": get_current_user_id(),
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
        }
        with self._lock:
            data = self._load()
            data[stored_name] = entry
            self._save(data)
        return entry

    def get(self, stored_name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._load().get(os.path.basename(stored_name))

    def forget(self, stored_name: str) -> None:
        with self._lock:
            data = self._load()
            if data.pop(os.path.basename(stored_name), None) is not None:
                self._save(data)

    def _visible(self, entry: Dict[str, Any], owner_id: Optional[str]) -> bool:
        entry_owner = entry.get("owner_id")
        return not owner_id or not entry_owner or entry_owner == owner_id

    def resolve(self, name: str) -> Dict[str, Any]:
        """Resolve a name from a request to one upload on disk.

        ``name`` may be the stored name (or its path) returned by the upload
        endpoint, or the original filename. An original filename uploaded more
        than once resolves to the latest upload of that name. Unknown names
        raise ``UploadNotFoundError``; nothing is ever guessed.
        """
        owner_id = get_current_user_id()
        base = os.path.basename(str(name or "").strip())
        if not base:
            raise UploadNotFoundError("Empty file name")

        with self._lock:
            data = self._load()

        entry = data.get(base)
        if entry is not None and not self._visible(entry, owner_id):
            entry = None
        if entry is None:
            matches = [
                e for e in data.values()
                if e.get("original_name") == base and self._visible(e, owner_id)
            ]
            matches = [e for e in matches if os.path.isfile(os.path.join(self.upload_dir, e["stored_name"]))]
            if matches:
                entry = max(matches, key=lambda e: e.get("uploaded_at") or "")
        if entry is None and base not in data:
            # An unregistered file stored under exactly this name (uploads made
            # before the registry existed are stored as <32 hex>.<ext>).
            path = os.path.join(self.upload_dir, base)
            if os.path.isfile(path) and not base.startswith("."):
                entry = {
                    "stored_name": base,
                    "original_name": base,
                    "size": os.path.getsize(path),
                    "sha256": None,
                    "owner_id": None,
                    "uploaded_at": None,
                }
        if entry is None:
            raise UploadNotFoundError(f"'{base}' is not an uploaded file")

        path = os.path.join(self.upload_dir, entry["stored_name"])
        if not os.path.isfile(path):
            raise UploadNotFoundError(f"'{base}' was uploaded but is no longer on disk")
        return {**entry, "path": path}

    def resolve_many(self, names: List[str]) -> List[Dict[str, Any]]:
        """Resolve every name; raise one error listing all that are unknown."""
        resolved: List[Dict[str, Any]] = []
        missing: List[str] = []
        seen = set()
        for name in names:
            try:
                entry = self.resolve(name)
            except UploadNotFoundError:
                missing.append(os.path.basename(str(name)))
                continue
            if entry["stored_name"] in seen:
                continue
            seen.add(entry["stored_name"])
            resolved.append(entry)
        if missing:
            raise UploadNotFoundError(
                "Not uploaded: " + ", ".join(missing) + ". Upload the file(s) first, then create the fabric."
            )
        return resolved


upload_registry = UploadRegistry()
