"""KOSIS OpenAPI read-only transport with retry and snapshot-ready responses."""

from __future__ import annotations

import json
import re
from time import sleep
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

_ERROR_CODE = re.compile(r'^\s*\{\s*err\s*:\s*["\'](?P<code>\d+)["\']')
_LEGACY_KEY = re.compile(r'([\[{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')


def get_meta(api_key: str, org_id: str, table_id: str, *, meta_type: str = "SOURCE", obj_id: str | None = None, itm_id: str | None = None, retries: int = 3) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch KOSIS metadata without exposing API keys or raw failure responses."""
    params = {"method": "getMeta", "apiKey": api_key, "format": "json", "orgId": org_id, "tblId": table_id, "type": meta_type}
    if obj_id:
        params["objId"] = obj_id
    if itm_id:
        params["itmId"] = itm_id
    url = "https://kosis.kr/openapi/statisticsData.do?" + urlencode(params)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=20) as response:
                payload = response.read()
            decoded = _decode_kosis_payload(payload)
            if not isinstance(decoded, (dict, list)):
                raise RuntimeError("KOSIS_METADATA_INVALID_RESPONSE")
            return decoded
        except RuntimeError:
            raise
        except Exception as error:
            last = error
            if attempt + 1 < retries:
                sleep(2**attempt)
    raise RuntimeError("KOSIS_METADATA_FETCH_FAILED") from last


def _decode_kosis_payload(payload: bytes) -> Any:
    """Decode strict JSON and KOSIS's legacy unquoted-key JSON variant."""
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        text = payload.decode("utf-8", errors="ignore")
        error_code = _kosis_error_code(payload)
        if error_code:
            raise RuntimeError(f"KOSIS_METADATA_API_ERROR_{error_code}") from error
        try:
            return json.loads(_LEGACY_KEY.sub(r'\1"\2"\3', text))
        except json.JSONDecodeError as legacy_error:
            raise RuntimeError("KOSIS_METADATA_INVALID_RESPONSE") from legacy_error


def _kosis_error_code(payload: bytes) -> str | None:
    """Extract only a KOSIS error code from its legacy JavaScript-object response."""
    match = _ERROR_CODE.match(payload.decode("utf-8", errors="ignore"))
    return match.group("code") if match else None
