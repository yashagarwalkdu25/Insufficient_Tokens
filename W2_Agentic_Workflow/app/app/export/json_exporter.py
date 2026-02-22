"""JSON export/import of full state."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    return obj


def export_to_json(state: dict[str, Any]) -> str:
    """Serialize state with metadata; pretty-print."""
    from datetime import datetime as dt
    out = {
        "export_date": dt.utcnow().isoformat() + "Z",
        "app_version": "1.0.0",
        "state": _serialize(state),
    }
    return json.dumps(out, indent=2, default=str)


def import_from_json(json_str: str) -> dict[str, Any]:
    """Parse JSON and return state dict (nested in .state if exported by us)."""
    data = json.loads(json_str)
    if isinstance(data, dict) and "state" in data:
        return data["state"]
    return data
