"""Read-only loaders for normalized semantic-standard and KOSIS catalog data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemas.candidate import KosisCandidateSchema


@dataclass(frozen=True, slots=True)
class SemanticStandardRecord:
    """A canonical concept and the aliases eligible for deterministic matching."""

    concept_id: str
    canonical_name: str
    standard_key: str
    aliases: tuple[str, ...]
    kosis_search_terms: tuple[str, ...] = ()


def load_standard_concepts(path: Path) -> list[SemanticStandardRecord]:
    """Load application-owned seed concepts from a JSON array."""
    records = _read_json_array(path)
    return [
        SemanticStandardRecord(
            concept_id=_required_string(record, "concept_id"),
            canonical_name=_required_string(record, "canonical_name"),
            standard_key=_required_string(record, "standard_key"),
            aliases=tuple(_string_list(record.get("aliases", []))),
            kosis_search_terms=tuple(_string_list(record.get("kosis_search_terms", []))),
        )
        for record in records
    ]


def load_kosis_catalog(path: Path) -> list[KosisCandidateSchema]:
    """Load normalized KOSIS metadata in stable table-id order."""
    candidates = [normalize_catalog_record(record) for record in _read_json_array(path)]
    return sorted(candidates, key=lambda candidate: (candidate.tbl_id, candidate.org_id))


def normalize_catalog_record(record: Mapping[str, Any]) -> KosisCandidateSchema:
    """Translate raw KOSIS metadata fields to the catalog data contract."""
    dimensions = _parse_dimension_members(record.get("DIMENSION_MEMBERS_JSON", {}))
    return KosisCandidateSchema(
        org_id=_required_string(record, "ORG_ID"),
        tbl_id=_required_string(record, "TBL_ID"),
        tbl_name=_first_string(record, "TBL_NM_META", "TBL_NM_INPUT"),
        core_item_ids=_split_field(record.get("CORE_ITEM_IDS")),
        core_item_names=_split_field(record.get("CORE_ITEM_NAMES")),
        dimension_ids=_split_field(record.get("DIMENSION_IDS")),
        dimension_names=_split_field(record.get("DIMENSION_NAMES")),
        dimension_members=dimensions,
        unit_names=_split_field(record.get("UNIT_NAMES_FINAL", record.get("UNIT_NAMES"))),
        frequency=_optional_string(record.get("PRD_SE_META")),
        start_period=_optional_string(record.get("STRT_PRD_DE")),
        end_period=_optional_string(record.get("END_PRD_DE")),
        source_stat_id=_optional_string(record.get("SOURCE_STAT_ID")),
        source_name=_optional_string(record.get("SOURCE_JOSA_NM")),
        metadata_status=_first_string(record, "semantic_core_status", "METADATA_STATUS"),
    )


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"Expected a JSON array of objects: {path}")
    return payload


def _parse_dimension_members(value: Any) -> dict[str, list[str]]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as error:
        raise ValueError("Invalid DIMENSION_MEMBERS_JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("Invalid DIMENSION_MEMBERS_JSON")
    return {str(key): (_string_list(members.get("members", [])) if isinstance(members, dict) else _string_list(members)) for key, members in parsed.items()}


def _split_field(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return _string_list(value)
    return [part.strip() for part in str(value).split("|") if part.strip()]


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("Expected a list of strings")
    return [str(value) for value in values]


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = _optional_string(record.get(key))
    if value is None:
        raise ValueError(f"Missing required catalog field: {key}")
    return value


def _first_string(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _optional_string(record.get(key))
        if value is not None:
            return value
    raise ValueError(f"Missing required catalog field: one of {', '.join(keys)}")


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None

