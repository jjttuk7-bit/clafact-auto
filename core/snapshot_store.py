"""Immutable-style JSON snapshot writer for audited KOSIS responses."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def save_snapshot(path: Path, request_params: dict[str, str], response: Any) -> dict[str, str]:
    raw=json.dumps(response,ensure_ascii=False,sort_keys=True).encode()
    record={"request_params":request_params,"response":response,"retrieved_at":datetime.now(timezone.utc).isoformat(),"response_hash":hashlib.sha256(raw).hexdigest()}
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"response_hash":record["response_hash"]}
