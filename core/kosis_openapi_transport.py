"""KOSIS OpenAPI read-only transport with retry and snapshot-ready responses."""

from __future__ import annotations

import json
import re
import ssl
from time import sleep
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_ERROR_CODE = re.compile(r'^\s*\{\s*err\s*:\s*["\'](?P<code>\d+)["\']')
_LEGACY_KEY = re.compile(r'([\[{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)')


class _RetryableMetadataResponse(RuntimeError):
    """A syntactically valid but transiently empty KOSIS metadata response."""


def create_kosis_tls_context() -> ssl.SSLContext:
    """Use TLS 1.2 for KOSIS legacy endpoints that reset modern handshakes."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    return context

def get_meta(api_key: str, org_id: str, table_id: str, *, meta_type: str = "SOURCE", obj_id: str | None = None, itm_id: str | None = None, retries: int = 3, timeout_seconds: float = 20) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch KOSIS metadata without exposing API keys or raw failure responses."""
    params = {"method": "getMeta", "apiKey": api_key, "format": "json", "orgId": org_id, "tblId": table_id, "type": meta_type}
    if obj_id:
        params["objId"] = obj_id
    if itm_id:
        params["itmId"] = itm_id
    url = "https://kosis.kr/openapi/statisticsData.do?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "CLAFACT-AUTO/0.1"})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout_seconds, context=create_kosis_tls_context()) as response:
                payload = response.read()
            decoded = _decode_kosis_payload(payload)
            if error_code := _decoded_kosis_error_code(decoded):
                raise RuntimeError(f"KOSIS_METADATA_API_ERROR_{error_code}")
            if not isinstance(decoded, (dict, list)):
                raise RuntimeError("KOSIS_METADATA_INVALID_RESPONSE")
            if meta_type in {"ITM", "PRD"} and decoded == []:
                raise _RetryableMetadataResponse("KOSIS_METADATA_EMPTY_RESPONSE")
            return _repair_kosis_mojibake(decoded)
        except _RetryableMetadataResponse as error:
            last = error
            if attempt + 1 < retries:
                sleep(2**attempt)
        except RuntimeError:
            raise
        except Exception as error:
            last = error
            if attempt + 1 < retries:
                sleep(2**attempt)
    raise RuntimeError("KOSIS_METADATA_FETCH_FAILED") from last

def _repair_kosis_mojibake(value: Any) -> Any:
    """Repair KOSIS metadata that arrives as CP949 bytes re-encoded as UTF-8 text."""
    if isinstance(value, dict):
        return {key: _repair_kosis_mojibake(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_repair_kosis_mojibake(item) for item in value]
    if not isinstance(value, str) or not any(ord(character) > 127 for character in value):
        return value
    try:
        repaired = value.encode("latin-1").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired if _looks_like_korean(repaired) else value


def _looks_like_korean(value: str) -> bool:
    return any("가" <= character <= "힣" for character in value)
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


def _decoded_kosis_error_code(payload: object) -> str | None:
    """Extract a numeric KOSIS error code from a decoded JSON object only."""
    if not isinstance(payload, dict):
        return None
    value = payload.get("err") or payload.get("error")
    code = str(value).strip() if value is not None else ""
    return code if code.isdigit() else None

def _kosis_error_code(payload: bytes) -> str | None:
    """Extract only a KOSIS error code from its legacy JavaScript-object response."""
    match = _ERROR_CODE.match(payload.decode("utf-8", errors="ignore"))
    return match.group("code") if match else None
