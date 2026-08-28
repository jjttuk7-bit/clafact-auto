from tools.compile_direct_value_indicator_refinement_18 import _official_complete


def _provenance(key: str) -> dict[str, object]:
    return {
        "evidence_key": key,
        "source": "API",
        "source_url": "https://kosis.kr/example",
        "content_hash": "abc",
        "retrieved_at": "2026-08-28T00:00:00Z",
        "publication": {"status": "VERIFIED"},
    }


def test_official_complete_requires_exact_evidence_provenance_keys() -> None:
    result = {"terminal_status": "AUTO"}
    verdict = {"route_status": "AUTO", "verdict": "MATCH"}
    evidence = [{"canonical_key": "A"}, {"canonical_key": "B"}]

    assert _official_complete(
        result, verdict, evidence, [_provenance("A"), _provenance("B")]
    )
    assert not _official_complete(
        result, verdict, evidence, [_provenance("A"), _provenance("A")]
    )


def test_official_complete_rejects_snapshot_or_unverified_publication() -> None:
    result = {"terminal_status": "AUTO"}
    verdict = {"route_status": "AUTO", "verdict": "MATCH"}
    evidence = [{"canonical_key": "A"}]
    snapshot = _provenance("A") | {"source": "SNAPSHOT"}
    unverified = _provenance("A") | {"publication": {"status": "UNKNOWN"}}

    assert not _official_complete(result, verdict, evidence, [snapshot])
    assert not _official_complete(result, verdict, evidence, [unverified])
