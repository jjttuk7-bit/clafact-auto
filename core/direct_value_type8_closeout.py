from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Type8Closeout:
    rows: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _is_verified_publication(value: object) -> bool:
    return isinstance(value, Mapping) and _text(value.get("status")).upper() == "VERIFIED"


def _strict_live_complete(update: Mapping[str, object]) -> bool:
    if _text(update.get("terminal_status")).upper() != "AUTO":
        return False
    if _text(update.get("verdict")).upper() not in {"MATCH", "MISMATCH"}:
        return False
    if not isinstance(update.get("official_values"), list) or not update["official_values"]:
        return False
    evidence = update.get("evidence_cells")
    provenance = update.get("provenance")
    if not isinstance(evidence, list) or not evidence:
        return False
    if not isinstance(provenance, list) or not provenance:
        return False
    evidence_keys = [_text(row.get("canonical_key")) for row in evidence if isinstance(row, Mapping)]
    provenance_keys = [_text(row.get("evidence_key")) for row in provenance if isinstance(row, Mapping)]
    if not evidence_keys or not provenance_keys or any(not key for key in evidence_keys + provenance_keys):
        return False
    if Counter(evidence_keys) != Counter(provenance_keys):
        return False
    return all(
        isinstance(row, Mapping)
        and _text(row.get("source")).upper() == "API"
        and bool(_text(row.get("source_url")))
        and bool(_text(row.get("content_hash")))
        and bool(_text(row.get("retrieved_at")))
        and _is_verified_publication(row.get("publication"))
        for row in provenance
    )


def _parsed_nonempty_list(value: object) -> bool:
    try:
        parsed = json.loads(_text(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(parsed, list) and bool(parsed)


def _strict_base_complete(row: Mapping[str, object]) -> bool:
    if _text(row.get("공식판정완료")).upper() != "Y":
        return False
    if _text(row.get("최종상태")).upper() != "AUTO":
        return False
    if _text(row.get("판정")).upper() not in {"MATCH", "MISMATCH"}:
        return False
    if not _text(row.get("공식계산값")):
        return False
    if not _text(row.get("공식근거URL")) or not _text(row.get("응답해시")):
        return False
    if _text(row.get("공표확인")).upper() != "VERIFIED":
        return False
    evidence_type = _text(row.get("공식근거종류")).upper()
    if evidence_type == "KOSIS_API":
        return _parsed_nonempty_list(row.get("공식좌표JSON"))
    return evidence_type == "OFFICIAL_DOCUMENT"


def _base_projection(row: Mapping[str, object]) -> dict[str, object]:
    strict = _strict_base_complete(row)
    return {
        "8번최종상태": _text(row.get("최종상태")),
        "8번최종사유": _text(row.get("최종사유코드")),
        "8번최종실패단계": _text(row.get("실패단계")),
        "8번최종판정": _text(row.get("판정")),
        "8번공식값JSON": _json([row.get("공식계산값")]) if _text(row.get("공식계산값")) else "[]",
        "8번공식좌표JSON": _text(row.get("공식좌표JSON")) or "[]",
        "8번공식출처JSON": "[]",
        "8번공식근거URL": _text(row.get("공식근거URL")),
        "8번응답해시": _text(row.get("응답해시")),
        "8번공표상태": _text(row.get("공표확인")),
        "8번엄격공식판정완료": "Y" if strict else "N",
        "8번최종결과출처": "230_BASE",
    }


def _update_projection(update: Mapping[str, object]) -> dict[str, object]:
    provenance = update.get("provenance") if isinstance(update.get("provenance"), list) else []
    urls = [_text(row.get("source_url")) for row in provenance if isinstance(row, Mapping) and _text(row.get("source_url"))]
    hashes = [_text(row.get("content_hash")) for row in provenance if isinstance(row, Mapping) and _text(row.get("content_hash"))]
    publications = [
        _text(row.get("publication", {}).get("status"))
        for row in provenance
        if isinstance(row, Mapping) and isinstance(row.get("publication"), Mapping)
    ]
    strict = _strict_live_complete(update)
    return {
        "8번최종상태": _text(update.get("terminal_status")),
        "8번최종사유": _text(update.get("reason_code")),
        "8번최종실패단계": _text(update.get("failure_stage")),
        "8번최종판정": _text(update.get("verdict")),
        "8번공식값JSON": _json(update.get("official_values") if isinstance(update.get("official_values"), list) else []),
        "8번공식좌표JSON": _json(update.get("evidence_cells") if isinstance(update.get("evidence_cells"), list) else []),
        "8번공식출처JSON": _json(provenance),
        "8번공식근거URL": " | ".join(dict.fromkeys(urls)),
        "8번응답해시": " | ".join(dict.fromkeys(hashes)),
        "8번공표상태": "VERIFIED" if publications and all(status.upper() == "VERIFIED" for status in publications) else "",
        "8번엄격공식판정완료": "Y" if strict else "N",
        "8번최종결과출처": _text(update.get("source")),
    }


def _index_updates(
    updates: Iterable[Mapping[str, object]], base_ids: set[str]
) -> dict[str, Mapping[str, object]]:
    index: dict[str, Mapping[str, object]] = {}
    for update in updates:
        claim_id = _text(update.get("claim_id"))
        if not claim_id or claim_id in index:
            raise ValueError("TYPE8_UPDATE_ID_INVALID")
        if claim_id not in base_ids:
            raise ValueError("TYPE8_UPDATE_OUTSIDE_SCOPE")
        index[claim_id] = update
    return index


def merge_type8_closeout(
    base_rows: Iterable[Mapping[str, object]],
    run176_updates: Iterable[Mapping[str, object]],
    run94_updates: Iterable[Mapping[str, object]],
    *,
    expected_count: int = 230,
) -> Type8Closeout:
    base = list(base_rows)
    base_ids = [_text(row.get("자식Claim번호")) for row in base]
    if len(base) != expected_count or any(not claim_id for claim_id in base_ids) or len(set(base_ids)) != len(base_ids):
        raise ValueError("TYPE8_BASE_ID_INVALID")
    scope = set(base_ids)
    updates176 = _index_updates(run176_updates, scope)
    updates94 = _index_updates(run94_updates, scope)

    merged: list[dict[str, Any]] = []
    for row, claim_id in zip(base, base_ids):
        output = dict(row)
        update = updates94.get(claim_id) or updates176.get(claim_id)
        output.update(_update_projection(update) if update is not None else _base_projection(row))
        merged.append(output)

    summary = {
        "scope_count": len(merged),
        "strict_official_complete_count": sum(row["8번엄격공식판정완료"] == "Y" for row in merged),
        "match_count": sum(row["8번최종판정"] == "MATCH" and row["8번엄격공식판정완료"] == "Y" for row in merged),
        "mismatch_count": sum(row["8번최종판정"] == "MISMATCH" and row["8번엄격공식판정완료"] == "Y" for row in merged),
        "source_counts": dict(Counter(row["8번최종결과출처"] for row in merged)),
        "status_counts": dict(Counter(row["8번최종상태"] for row in merged)),
        "reason_counts": dict(Counter(row["8번최종사유"] for row in merged)),
        "failure_stage_counts": dict(Counter(row["8번최종실패단계"] for row in merged)),
    }
    return Type8Closeout(rows=tuple(merged), summary=summary)
