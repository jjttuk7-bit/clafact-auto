"""Read-only KOSIS table-selection value transport."""

from __future__ import annotations

from time import sleep
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from core.kosis_openapi_transport import _decode_kosis_payload


def get_parameter_data(
    api_key: str,
    org_id: str,
    table_id: str,
    item_id: str,
    period_type: str,
    start_period: str,
    end_period: str,
    object_codes: list[str],
    *,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """Fetch values for an explicit KOSIS coordinate; never infer dimensions."""
    if not 1 <= len(object_codes) <= 8:
        raise ValueError("KOSIS_OBJECT_CODES_REQUIRED")
    params = {
        "method": "getList", "apiKey": api_key, "format": "json", "jsonVD": "Y",
        "orgId": org_id, "tblId": table_id, "itmId": item_id, "prdSe": period_type,
        "startPrdDe": start_period, "endPrdDe": end_period,
    }
    params.update({f"objL{index}": code for index, code in enumerate(object_codes, start=1)})
    url = "https://kosis.kr/openapi/Param/statisticsParameterData.do?" + urlencode(params)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=20) as response:
                decoded = _decode_kosis_payload(response.read())
            if not isinstance(decoded, list) or not all(isinstance(record, dict) for record in decoded):
                raise RuntimeError("KOSIS_VALUE_INVALID_RESPONSE")
            return decoded
        except RuntimeError:
            raise
        except Exception as error:
            last = error
            if attempt + 1 < retries:
                sleep(2**attempt)
    raise RuntimeError("KOSIS_VALUE_FETCH_FAILED") from last
