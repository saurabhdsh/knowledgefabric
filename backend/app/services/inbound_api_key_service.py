"""
Inbound API key management for external Knowledge Fabric consumers (agent
scripts, partner services, the CSNP CLI, etc.).

This is intentionally a separate service from `app.services.api_key_service`,
which manages OUTBOUND keys for LLM providers (OpenAI, Gemini, …).

Storage model:
- Plain key shape: ``kf_live_<32 random url-safe chars>``
- Only the SHA-256 hash of the plain key is persisted.
- A short prefix (``kf_live_xxxx``) is stored alongside for human-readable
  display in lists. The plain key is only returned to the operator at
  issuance time and is unrecoverable afterwards.

The store lives at ``<backend>/data/inbound_api_keys.json`` by default, or
wherever the ``KF_INBOUND_KEYS_FILE`` env var points.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Default storage location: <repo>/backend/data/inbound_api_keys.json
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_KEY_FILE = os.path.join(_BACKEND_ROOT, "data", "inbound_api_keys.json")

KEY_FILE_PATH = os.environ.get("KF_INBOUND_KEYS_FILE", _DEFAULT_KEY_FILE)
KEY_PREFIX = "kf_live_"
DISPLAY_PREFIX_LEN = len(KEY_PREFIX) + 4  # e.g. "kf_live_abcd"


def _hash_key(plain: str) -> str:
    """SHA-256 hash; cheap to recompute on every request."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


@dataclass
class InboundAPIKey:
    """Persisted representation of a single inbound key (never includes plain)."""

    id: str
    name: str
    description: str
    display_prefix: str
    key_hash: str
    scopes: List[str] = field(default_factory=lambda: ["query"])
    fabric_ids: Optional[List[str]] = None  # None = all fabrics
    created_at: str = ""
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    revoked: bool = False


class InboundAPIKeyService:
    """JSON-file backed registry for inbound consumer keys."""

    def __init__(self, store_path: Optional[str] = None) -> None:
        self.store_path = store_path or KEY_FILE_PATH
        parent = os.path.dirname(self.store_path) or "."
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create inbound key store dir %s: %s", parent, exc)
        self._lock = threading.Lock()
        if not os.path.exists(self.store_path):
            self._write([])

    # ---------- storage ----------

    def _read(self) -> List[Dict]:
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, FileNotFoundError, OSError) as exc:
            logger.warning("Could not read inbound key store %s: %s", self.store_path, exc)
        return []

    def _write(self, items: List[Dict]) -> None:
        tmp = f"{self.store_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, default=str)
        os.replace(tmp, self.store_path)

    # ---------- operations ----------

    def issue(
        self,
        name: str,
        description: str = "",
        scopes: Optional[List[str]] = None,
        fabric_ids: Optional[List[str]] = None,
        expires_at: Optional[str] = None,
    ) -> Tuple[InboundAPIKey, str]:
        """
        Mint a new inbound key.

        Returns ``(record, plain_key)``. The plain key is shown to the operator
        exactly once at issuance and is never recoverable afterwards.
        """
        plain = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
        kid = secrets.token_hex(8)
        now = datetime.now(timezone.utc).isoformat()
        rec = InboundAPIKey(
            id=kid,
            name=(name or "").strip() or "unnamed",
            description=(description or "").strip(),
            display_prefix=plain[:DISPLAY_PREFIX_LEN],
            key_hash=_hash_key(plain),
            scopes=scopes or ["query"],
            fabric_ids=fabric_ids,
            created_at=now,
            expires_at=expires_at,
        )
        with self._lock:
            items = self._read()
            items.append(asdict(rec))
            self._write(items)
        return rec, plain

    def list(self) -> List[InboundAPIKey]:
        return [InboundAPIKey(**item) for item in self._read()]

    def validate(self, plain_key: Optional[str]) -> Optional[InboundAPIKey]:
        """
        Return the record for a valid, non-revoked, non-expired key, or None.
        Also updates ``last_used_at`` for observability.
        """
        if not plain_key:
            return None
        h = _hash_key(plain_key)
        with self._lock:
            items = self._read()
            now = datetime.now(timezone.utc)
            for item in items:
                if item.get("key_hash") != h:
                    continue
                if item.get("revoked"):
                    return None
                expires_at = item.get("expires_at")
                if expires_at:
                    try:
                        # Accept "YYYY-MM-DD" or full ISO.
                        when = (
                            datetime.fromisoformat(expires_at)
                            if "T" in expires_at
                            else datetime.fromisoformat(expires_at + "T00:00:00+00:00")
                        )
                        if when.tzinfo is None:
                            when = when.replace(tzinfo=timezone.utc)
                        if when < now:
                            return None
                    except ValueError:
                        pass
                item["last_used_at"] = now.isoformat()
                self._write(items)
                return InboundAPIKey(**item)
        return None

    def revoke(self, key_id: str) -> bool:
        """Mark a key as revoked. Returns True if a matching key was found."""
        with self._lock:
            items = self._read()
            changed = False
            for item in items:
                if item.get("id") == key_id and not item.get("revoked"):
                    item["revoked"] = True
                    changed = True
            if changed:
                self._write(items)
        return changed


# Module-level singleton used by the middleware.
inbound_api_key_service = InboundAPIKeyService()
