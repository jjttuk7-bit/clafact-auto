"""Direct KOSIS publication-information lookup with auditable provenance."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from time import sleep
from typing import Any, Callable, Literal
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from core.kosis_openapi_transport import _decode_kosis_payload, _repair_kosis_mojibake

PublicationStatus = Literal["VERIFIED", "UNRESOLVED", "FETCH_FAILED"]
_ENDPOINT = "https://kosis.kr/openapi/statisticsExplData.do"
_EXACT_DATE_BODY = (
    r"(?<!\d)(?P<year>20\d{2})\s*(?:-|\.|년\s*)\s*"
    r"(?P<month>0?[1-9]|1[0-2])\s*(?:-|\.|월\s*)\s*"
    r"(?P<day>0?[1-9]|[12]\d|3[01])\s*(?:일)?(?!\d)"
)
_EXACT_DATE = re.compile(_EXACT_DATE_BODY)
_RELEASE_DATE = re.compile(r"(?:게시일|보도시점|공표일자)\s*[:：]?\s*" + _EXACT_DATE_BODY)
_OFFICIAL_URL = re.compile(r"https://[^\s<>\"']+")
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class PublicationEvidence:
    status: PublicationStatus
    published_at: date | None = None
    pub_period: str | None = None
    pub_date_text: str | None = None
    publication_method_url: str | None = None
    source_url: str = ""
    retrieved_at: str = ""
    content_hash: str = ""


class KosisPublicationLookup:
    """Fetch official publication metadata by KOSIS organisation and table ID."""

    def __init__(self, api_key: str, *, opener: Callable[..., Any] = urlopen, retries: int = 2, timeout_seconds: int = 10) -> None:
        self._api_key = api_key
        self._opener = opener
        self._retries = max(1, retries)
        self._timeout_seconds = max(1, timeout_seconds)

    def fetch(self, org_id: str, table_id: str, *, period: str | None = None) -> PublicationEvidence:
        public_params = {
            "method": "getList", "format": "json", "jsonVD": "Y",
            "orgId": org_id, "tblId": table_id, "metaItm": "All",
        }
        source_url = f"{_ENDPOINT}?{urlencode(public_params)}"
        request_url = f"{source_url}&{urlencode({'apiKey': self._api_key})}"
        last_hash = ""
        for attempt in range(self._retries):
            try:
                request = Request(request_url, headers={"Accept": "application/json", "User-Agent": "CLAFACT-AUTO/0.1"})
                with self._opener(request, timeout=self._timeout_seconds) as response:
                    raw = response.read()
                last_hash = hashlib.sha256(raw).hexdigest()
                merged = _merge_payload(_repair_kosis_mojibake(_decode_kosis_payload(raw)))
                if merged is None:
                    raise RuntimeError("KOSIS_PUBLICATION_INVALID_RESPONSE")
                pub_date_text = _text(merged.get("pubDate"))
                pub_period = _text(merged.get("pubPeriod"))
                method = _text(merged.get("publictMth"))
                conflict = merged.get("_publication_conflict") is True
                published_at = None if conflict else _parse_exact_date(pub_date_text)
                if published_at is None and period and not conflict:
                    release = self._fetch_official_release(method, period, pub_period, pub_date_text)
                    if release is not None:
                        return release
                return PublicationEvidence(
                    status="VERIFIED" if published_at else "UNRESOLVED",
                    published_at=published_at,
                    pub_period=pub_period,
                    pub_date_text=pub_date_text,
                    publication_method_url=method,
                    source_url=source_url,
                    retrieved_at=_now(),
                    content_hash=last_hash,
                )
            except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
                if attempt + 1 < self._retries:
                    sleep(2**attempt)
        return PublicationEvidence(status="FETCH_FAILED", source_url=source_url, retrieved_at=_now(), content_hash=last_hash)

    def _fetch_official_release(self, method: str | None, period: str, pub_period: str | None, pub_date_text: str | None) -> PublicationEvidence | None:
        official_url = _extract_official_url(method)
        if official_url is None:
            return None
        try:
            request = Request(official_url, headers={"Accept": "text/html", "User-Agent": "CLAFACT-AUTO/0.1"})
            with self._opener(request, timeout=self._timeout_seconds) as response:
                raw = response.read()
            text = unescape(_TAGS.sub(" ", raw.decode("utf-8", errors="replace")))
            if not _period_appears(text, period):
                return None
            published_at = _parse_release_date(text)
            if published_at is None:
                return None
            return PublicationEvidence(
                status="VERIFIED", published_at=published_at, pub_period=pub_period,
                pub_date_text=pub_date_text, publication_method_url=official_url,
                source_url=official_url, retrieved_at=_now(),
                content_hash=hashlib.sha256(raw).hexdigest(),
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return None


def _merge_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return None if any(key in payload for key in ("err", "error", "errMsg")) else payload
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        return None
    merged: dict[str, Any] = {}
    publication_values: dict[str, set[str]] = {
        key: set() for key in ("pubPeriod", "pubDate", "publictMth")
    }
    for row in payload:
        if any(key in row for key in ("err", "error", "errMsg")):
            return None
        for key in publication_values:
            if (value := _text(row.get(key))) is not None:
                publication_values[key].add(value)
        merged.update(row)
    if any(len(values) > 1 for values in publication_values.values()):
        merged["_publication_conflict"] = True
    return merged or None


def _parse_exact_date(value: str | None) -> date | None:
    if not value or len(matches := list(_EXACT_DATE.finditer(value))) != 1:
        return None
    return _date_from_match(matches[0])


def _parse_release_date(value: str) -> date | None:
    matches = list(_RELEASE_DATE.finditer(value))
    if len(matches) != 1:
        return None
    return _date_from_match(matches[0])


def _date_from_match(match: re.Match[str]) -> date | None:
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError:
        return None


def _extract_official_url(value: str | None) -> str | None:
    if not value or (match := _OFFICIAL_URL.search(value)) is None:
        return None
    url = match.group().rstrip(".,;)")
    host = (urlparse(url).hostname or "").casefold()
    return url if host.endswith(".go.kr") or host in {"kosis.kr", "www.kosis.kr"} else None


def _period_appears(value: str, period: str) -> bool:
    normalized = period.replace("-", "").upper()
    if re.fullmatch(r"\d{6}", normalized):
        year, month = normalized[:4], str(int(normalized[4:]))
        return re.search(rf"{year}\s*년?\s*{month}\s*월", value) is not None
    if match := re.fullmatch(r"(\d{4})Q([1-4])", normalized):
        return re.search(rf"{match.group(1)}\s*년?\s*{match.group(2)}\s*(?:분기|/4)", value) is not None
    return bool(re.fullmatch(r"\d{4}", normalized) and re.search(rf"{normalized}\s*년", value))


def _text(value: object) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")