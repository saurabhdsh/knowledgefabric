"""Make Python structures safe for JSON (NaN/Inf/numpy scalars)."""
from __future__ import annotations

import math
from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """Recursively replace non-JSON-compliant floats and numpy scalars."""
    if obj is None:
        return None

    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]

    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # numpy / pandas scalar types
    if hasattr(obj, "item") and callable(getattr(obj, "item", None)):
        try:
            return sanitize_for_json(obj.item())
        except Exception:
            pass

    if isinstance(obj, (str, bytes)):
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8", errors="replace")
            except Exception:
                return str(obj)
        return obj

    # Last resort for dates, decimals, etc.
    try:
        if isinstance(obj, float):
            return None if math.isnan(obj) or math.isinf(obj) else obj
    except Exception:
        pass

    return str(obj)
