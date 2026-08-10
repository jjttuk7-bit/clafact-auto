"""Immutable-style JSON snapshot writer for audited KOSIS responses."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def save_snapshot(
    path: Path,
    request_params: dict[str, str],
    response: Any,
    *,
    article_date: date | None = None,
) -> dict[str, str]:
    """Write an auditable response snapshot without persisting request secrets."""
    raw = json.dumps(response, ensure_ascii=False, sort_keys=True).encode()
    record: dict[str, Any] = {
        "request_params": _without_secret_params(request_params),
        "response": response,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "response_hash": hashlib.sha256(raw).hexdigest(),
    }
    if article_date is not None:
        record["article_date"] = article_date.isoformat()
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"response_hash": record["response_hash"]}


def _without_secret_params(request_params: dict[str, str]) -> dict[str, str]:
    """Exclude API-key-like request parameters from persisted audit records."""
    return {
        key: value
        for key, value in request_params.items()
        if "key" not in key.lower() and "token" not in key.lower()
    }