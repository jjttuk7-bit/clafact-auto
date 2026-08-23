"""Official KOSIS value access through immutable snapshots or explicit API rows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

from core.snapshot_asof import filter_rows_as_of
from core.kosis_api_adapter import api_period
from core.kosis_publication import PublicationEvidence
from schemas.evidence import EvidenceCellSchema

ValueStatus = Literal["SUCCESS", "NO_DATA", "INVALID_RESPONSE", "AS_OF_UNAVAILABLE", "PUBLICATION_FETCH_FAILED", "FETCH_FAILED"]


@dataclass(frozen=True, slots=True)
class KosisValue:
    value: float | None
    status: ValueStatus
    snapshot_hash: str
    source: Literal["SNAPSHOT", "API", "NONE"] = "SNAPSHOT"
    publication: PublicationEvidence | None = None
    source_url: str = ""
    retrieved_at: str = ""
    value_last_changed_at: date | None = None


def fetch_kosis_value(cell: EvidenceCellSchema, snapshot_path: Path) -> KosisValue:
    """Read an official value from a legacy flat snapshot; never synthesize one."""
    raw = snapshot_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
        value = payload.get(cell.canonical_key)
    except (json.JSONDecodeError, AttributeError):
        return KosisValue(None, "INVALID_RESPONSE", digest)
    if value is None:
        return KosisValue(None, "NO_DATA", digest)
    if not isinstance(value, (int, float)):
        return KosisValue(None, "INVALID_RESPONSE", digest)
    return KosisValue(float(value), "SUCCESS", digest)


class OfficialValueFetcher:
    """Prefer auditable local snapshots, then use an injected read-only KOSIS API adapter."""

    def __init__(
        self,
        snapshot_paths: Iterable[Path],
        api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None,
        *,
        prefer_api: bool = False,
        as_of_metadata_paths: Iterable[Path] = (),
        publication_lookup: Any | None = None,
        require_verified_release_metadata: bool = False,
    ) -> None:
        self._snapshot_paths = list(snapshot_paths)
        self._api_lookup = api_lookup
        self._prefer_api = prefer_api
        self._as_of_metadata_paths = list(as_of_metadata_paths)
        self._publication_lookup = publication_lookup
        self._publication_cache: dict[tuple[str, str, str], PublicationEvidence] = {}
        self._require_verified_release_metadata = require_verified_release_metadata

    def fetch(self, cell: EvidenceCellSchema, *, article_date: date | None = None) -> KosisValue:
        as_of_unavailable = False
        publication_failed = False
        fetch_failed = False
        api_result: KosisValue | None = None
        if self._prefer_api:
            api_result = self._fetch_api(cell, article_date)
            if api_result is not None and api_result.status == "SUCCESS":
                return api_result
            as_of_unavailable = bool(api_result and api_result.status == "AS_OF_UNAVAILABLE")
            publication_failed = bool(api_result and api_result.status == "PUBLICATION_FETCH_FAILED")
            fetch_failed = bool(api_result and api_result.status == "FETCH_FAILED")
        for path in self._snapshot_paths:
            result = self._fetch_snapshot(cell, path, article_date)
            if result.status == "SUCCESS":
                return result
            as_of_unavailable = as_of_unavailable or result.status == "AS_OF_UNAVAILABLE"
            fetch_failed = fetch_failed or result.status == "FETCH_FAILED"
        if not self._prefer_api:
            api_result = self._fetch_api(cell, article_date)
            if api_result is not None and api_result.status in {"SUCCESS", "AS_OF_UNAVAILABLE", "PUBLICATION_FETCH_FAILED"}:
                return api_result
            fetch_failed = fetch_failed or bool(
                api_result and api_result.status == "FETCH_FAILED"
            )
        status: ValueStatus = (
            "AS_OF_UNAVAILABLE" if as_of_unavailable
            else "PUBLICATION_FETCH_FAILED" if publication_failed
            else "FETCH_FAILED" if fetch_failed
            else "NO_DATA"
        )
        if self._prefer_api and api_result is not None and api_result.status == status:
            return api_result
        return KosisValue(None, status, "", "NONE")

    def fetch_many(
        self,
        cells: list[EvidenceCellSchema],
        *,
        article_date: date | None = None,
    ) -> list[KosisValue]:
        """Fetch identical coordinates across periods with one API range request."""
        batch_lookup = getattr(self._api_lookup, "fetch_many", None)
        if not self._prefer_api or not callable(batch_lookup) or not cells:
            return [self.fetch(cell, article_date=article_date) for cell in cells]
        try:
            rows = batch_lookup(cells)
        except Exception:
            return [self.fetch(cell, article_date=article_date) for cell in cells]
        digest = hashlib.sha256(
            json.dumps(
                rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return [self._api_result(cell, rows, article_date, digest) for cell in cells]

    def fetch_record_history(
        self,
        cells: list[EvidenceCellSchema],
        *,
        article_date: date,
    ) -> list[KosisValue]:
        """Fetch a record-comparison range with one verified target release."""
        if not cells:
            return []
        first = cells[0]
        coordinate = (
            first.org_id,
            first.tbl_id,
            first.itm_id,
            first.obj_id,
            first.member_code,
            first.dimension_members,
            first.dimension_codes,
            first.prd_se,
            first.unit,
        )
        if any(
            (
                cell.org_id,
                cell.tbl_id,
                cell.itm_id,
                cell.obj_id,
                cell.member_code,
                cell.dimension_members,
                cell.dimension_codes,
                cell.prd_se,
                cell.unit,
            )
            != coordinate
            for cell in cells[1:]
        ):
            return [
                KosisValue(None, "INVALID_RESPONSE", "", "NONE")
                for _ in cells
            ]

        source_url = _api_range_source_url(cells)
        retrieved_at = _now()
        batch_lookup = getattr(self._api_lookup, "fetch_many", None)
        if not self._prefer_api or not callable(batch_lookup):
            return [
                KosisValue(
                    None,
                    "FETCH_FAILED",
                    "",
                    "NONE",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for _ in cells
            ]
        try:
            rows = batch_lookup(cells)
        except Exception:
            return [
                KosisValue(
                    None,
                    "FETCH_FAILED",
                    "",
                    "NONE",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for _ in cells
            ]
        if not isinstance(rows, list):
            return [
                KosisValue(
                    None,
                    "INVALID_RESPONSE",
                    "",
                    "API",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for _ in cells
            ]

        raw_rows = getattr(rows, "raw_rows", rows)
        digest = hashlib.sha256(
            json.dumps(
                raw_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        publication = self._fetch_publication(cells[-1])
        if (
            publication is None
            or publication.status != "VERIFIED"
            or publication.published_at is None
            or publication.reference_period is None
            or api_period(publication.reference_period) != api_period(cells[-1].prd_de)
        ):
            status: ValueStatus = (
                "PUBLICATION_FETCH_FAILED"
                if publication is not None and publication.status == "FETCH_FAILED"
                else "AS_OF_UNAVAILABLE"
            )
            return [
                KosisValue(
                    None,
                    status,
                    digest,
                    "API",
                    publication,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for _ in cells
            ]
        if publication.published_at > article_date:
            return [
                KosisValue(
                    None,
                    "AS_OF_UNAVAILABLE",
                    digest,
                    "API",
                    publication,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for _ in cells
            ]

        range_publication = replace(
            publication,
            evidence_scope="CALCULATION_RANGE",
            reference_period=cells[-1].prd_de,
            coverage_start_period=cells[0].prd_de,
            coverage_end_period=cells[-1].prd_de,
        )
        def range_failure(status: ValueStatus) -> list[KosisValue]:
            return [
                KosisValue(
                    None,
                    status,
                    digest,
                    "API",
                    range_publication,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for _ in cells
            ]

        # KOSIS returns every period inside a range request. Non-comparison
        # periods are not calculation operands, but every returned row is still
        # coordinate-, duplicate-, and article-date-guarded before use.
        returned_periods: set[str] = set()
        range_start = min(api_period(cell.prd_de) for cell in cells)
        range_end = max(api_period(cell.prd_de) for cell in cells)
        for row in rows:
            if not isinstance(row, dict):
                return range_failure("INVALID_RESPONSE")
            returned_period = str(row.get("period", row.get("PRD_DE", ""))).replace("-", "")
            if (
                not returned_period
                or returned_period < range_start
                or returned_period > range_end
                or returned_period in returned_periods
            ):
                return range_failure("INVALID_RESPONSE")
            probe = first.model_copy(update={"prd_de": returned_period})
            if not _matches_cell(row, probe, allow_missing_codes=True):
                return range_failure("INVALID_RESPONSE")
            returned_periods.add(returned_period)
            changed_text = str(row.get("LST_CHN_DE", "")).strip()
            try:
                changed_at = date.fromisoformat(changed_text)
            except ValueError:
                changed_at = None
            if (
                changed_at is None
                or changed_at.isoformat() != changed_text
                or changed_at > article_date
            ):
                return range_failure("AS_OF_UNAVAILABLE")

        resolved: list[KosisValue] = []
        for cell in cells:
            matching = [
                row
                for row in rows
                if isinstance(row, dict)
                and _matches_cell(row, cell, allow_missing_codes=True)
            ]
            if len(matching) != 1:
                status = "NO_DATA" if not matching else "INVALID_RESPONSE"
                return [
                    KosisValue(
                        None,
                        status,
                        digest,
                        "API",
                        range_publication,
                        source_url=source_url,
                        retrieved_at=retrieved_at,
                    )
                    for _ in cells
                ]
            row = matching[0]
            changed_text = str(row.get("LST_CHN_DE", "")).strip()
            try:
                changed_at = date.fromisoformat(changed_text)
            except ValueError:
                changed_at = None
            if (
                changed_at is None
                or changed_at.isoformat() != changed_text
                or changed_at > article_date
            ):
                return [
                    KosisValue(
                        None,
                        "AS_OF_UNAVAILABLE",
                        digest,
                        "API",
                        range_publication,
                        source_url=source_url,
                        retrieved_at=retrieved_at,
                    )
                    for _ in cells
                ]
            raw_value = row.get("value", row.get("DT"))
            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError):
                return [
                    KosisValue(
                        None,
                        "INVALID_RESPONSE",
                        digest,
                        "API",
                        range_publication,
                        source_url=source_url,
                        retrieved_at=retrieved_at,
                    )
                    for _ in cells
                ]
            resolved.append(
                KosisValue(
                    numeric_value,
                    "SUCCESS",
                    digest,
                    "API",
                    range_publication,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    value_last_changed_at=changed_at,
                )
            )
        return resolved
    def _fetch_api(self, cell: EvidenceCellSchema, article_date: date | None) -> KosisValue | None:
        if self._api_lookup is None:
            return None
        try:
            rows = self._api_lookup(cell)
        except Exception:
            return KosisValue(
                None, "FETCH_FAILED", "", "NONE",
                source_url=_api_source_url(cell), retrieved_at=_now(),
            )
        digest = hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return self._api_result(cell, rows, article_date, digest)


    def _api_result(
        self,
        cell: EvidenceCellSchema,
        rows: list[dict[str, Any]],
        article_date: date | None,
        digest: str,
    ) -> KosisValue:
        publication: PublicationEvidence | None = None
        source_url = _api_source_url(cell)
        retrieved_at = _now()
        if article_date:
            dated_rows, publication = self._with_release_metadata(cell, rows)
        else:
            dated_rows = rows
        if dated_rows is None:
            status: ValueStatus = (
                "PUBLICATION_FETCH_FAILED"
                if publication is not None and publication.status == "FETCH_FAILED"
                else "AS_OF_UNAVAILABLE"
            )
            return KosisValue(
                None, status, digest, "API", publication,
                source_url=source_url, retrieved_at=retrieved_at,
            )
        result = self._extract_rows(
            cell, dated_rows, article_date, source="API", digest=digest,
            publication=publication,
        )
        return replace(result, source_url=source_url, retrieved_at=retrieved_at)

    def _with_release_metadata(
        self, cell: EvidenceCellSchema, rows: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]] | None, PublicationEvidence | None]:
        publication = self._fetch_publication(cell)
        if publication is not None and publication.status == "FETCH_FAILED":
            return None, publication
        if publication is not None and publication.status == "VERIFIED" and publication.published_at:
            return (
                [{**row, "official_published_at": publication.published_at.isoformat()} for row in rows],
                publication,
            )
        if self._require_verified_release_metadata and publication is not None:
            return None, publication
        published_at: str | None = None
        for path in self._as_of_metadata_paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("org_id") not in (None, cell.org_id):
                continue
            if payload.get("tbl_id") not in (None, cell.tbl_id):
                continue
            if payload.get("item_id") not in (None, cell.itm_id):
                continue
            records = payload.get("records")
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict) or not _matches_cell(record, cell):
                    continue
                if record.get("official_release_verified") is not True:
                    continue
                published_at = str(
                    record.get("official_published_at")
                    or record.get("source_published_at")
                    or payload.get("source_published_at")
                    or ""
                ).strip() or None
                if published_at:
                    break
            if published_at:
                break
        if not published_at:
            return (
                None if self._require_verified_release_metadata else rows,
                publication,
            )
        return ([{**row, "official_published_at": published_at} for row in rows], publication)

    def _fetch_publication(self, cell: EvidenceCellSchema) -> PublicationEvidence | None:
        if self._publication_lookup is None:
            return None
        key = (cell.org_id, cell.tbl_id, cell.prd_de)
        if key not in self._publication_cache:
            try:
                self._publication_cache[key] = self._publication_lookup.fetch(
                    cell.org_id, cell.tbl_id, period=cell.prd_de
                )
            except Exception:
                self._publication_cache[key] = PublicationEvidence(status="FETCH_FAILED")
        return self._publication_cache[key]

    def _fetch_snapshot(self, cell: EvidenceCellSchema, path: Path, article_date: date | None) -> KosisValue:
        try:
            raw = path.read_bytes()
        except OSError:
            return KosisValue(None, "FETCH_FAILED", "", "NONE")
        digest = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return KosisValue(None, "INVALID_RESPONSE", digest)
        if isinstance(payload, dict) and cell.canonical_key in payload:
            return fetch_kosis_value(cell, path)
        if not isinstance(payload, dict):
            return KosisValue(None, "INVALID_RESPONSE", digest)
        records = payload.get("records", payload.get("response"))
        if not isinstance(records, list):
            return KosisValue(None, "NO_DATA", digest)
        if payload.get("tbl_id") and payload.get("tbl_id") != cell.tbl_id:
            return KosisValue(None, "NO_DATA", digest)
        if payload.get("item_id") and payload.get("item_id") != cell.itm_id:
            return KosisValue(None, "NO_DATA", digest)
        published_at = payload.get("source_published_at")
        inherited_records = [
            {
                **row,
                **(
                    {"source_published_at": published_at}
                    if published_at and "source_published_at" not in row
                    else {}
                ),
            }
            for row in records
            if isinstance(row, dict)
        ]
        return self._extract_rows(cell, inherited_records, article_date, source="SNAPSHOT", digest=digest)

    def _extract_rows(self, cell: EvidenceCellSchema, rows: list[dict[str, Any]], article_date: date | None, *, source: Literal["SNAPSHOT", "API"], digest: str, publication: PublicationEvidence | None = None) -> KosisValue:
        matching = [row for row in rows if _matches_cell(row, cell, allow_missing_codes=source == "API")]
        if not matching:
            return KosisValue(None, "NO_DATA", digest, source)
        usable = filter_rows_as_of(matching, article_date) if article_date else matching
        if article_date and not usable:
            changed_at = _row_changed_at(matching[0])
            return KosisValue(
                None, "AS_OF_UNAVAILABLE", digest, source, publication,
                value_last_changed_at=changed_at,
            )
        selected = usable[0]
        value = selected.get("value", selected.get("DT"))
        changed_at = _row_changed_at(selected)
        try:
            return KosisValue(
                float(value), "SUCCESS", digest, source, publication,
                value_last_changed_at=changed_at,
            )
        except (TypeError, ValueError):
            return KosisValue(None, "INVALID_RESPONSE", digest, source)


def _row_changed_at(row: dict[str, Any]) -> date | None:
    changed_text = row.get("LST_CHN_DE") or row.get("last_changed_at")
    if not isinstance(changed_text, str):
        return None
    try:
        return date.fromisoformat(changed_text)
    except ValueError:
        return None


def _matches_cell(row: dict[str, Any], cell: EvidenceCellSchema, *, allow_missing_codes: bool = False) -> bool:
    table = row.get("tbl_id", row.get("TBL_ID"))
    item = row.get("item_id", row.get("ITM_ID"))
    period = str(row.get("period", row.get("PRD_DE", ""))).replace("-", "")
    expected_period = api_period(cell.prd_de)
    codes = row.get("dimension_codes")
    if not isinstance(codes, dict):
        codes = {key: row.get(key) for key in cell.dimension_codes}
    has_returned_codes = any(value is not None for value in codes.values())
    codes_match = (
        not cell.dimension_codes
        or (allow_missing_codes and not has_returned_codes)
        or all(codes.get(key) == value for key, value in cell.dimension_codes.items())
    )
    return (table in (None, cell.tbl_id) and item in (None, cell.itm_id) and period == expected_period and codes_match)





def _api_range_source_url(cells: list[EvidenceCellSchema]) -> str:
    first, last = cells[0], cells[-1]
    frequency = {
        "월": "M", "monthly": "M", "month": "M",
        "년": "Y", "year": "Y", "yearly": "Y", "annual": "Y",
        "분기": "Q", "반기": "H",
    }.get(first.prd_se.casefold(), first.prd_se)
    params = {
        "method": "getList",
        "orgId": first.org_id,
        "tblId": first.tbl_id,
        "itmId": first.itm_id,
        "prdSe": frequency,
        "startPrdDe": api_period(first.prd_de),
        "endPrdDe": api_period(last.prd_de),
    }
    params.update(
        {f"objL{index}": code for index, code in enumerate(first.dimension_codes.values(), start=1)}
    )
    return "https://kosis.kr/openapi/Param/statisticsParameterData.do?" + urlencode(params)
def _api_source_url(cell: EvidenceCellSchema) -> str:
    frequency = {
        "월": "M", "monthly": "M", "month": "M",
        "년": "Y", "year": "Y", "yearly": "Y", "annual": "Y",
        "분기": "Q", "반기": "H",
    }.get(cell.prd_se.casefold(), cell.prd_se)
    period = api_period(cell.prd_de)
    params = {
        "method": "getList",
        "orgId": cell.org_id,
        "tblId": cell.tbl_id,
        "itmId": cell.itm_id,
        "prdSe": frequency,
        "startPrdDe": period,
        "endPrdDe": period,
    }
    params.update(
        {f"objL{index}": code for index, code in enumerate(cell.dimension_codes.values(), start=1)}
    )
    return "https://kosis.kr/openapi/Param/statisticsParameterData.do?" + urlencode(params)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

