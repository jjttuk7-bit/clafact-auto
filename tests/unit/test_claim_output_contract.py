from pathlib import Path

from core.claim_output_contract import (
    CLAIM_OUTPUT_FIELD_NAMES,
    EMIT_CLAIM_FUNCTION_NAME,
    SEMANTIC_SLOT_NAMES,
    claim_output_json_schema,
    emit_claim_tool_definition,
)
from schemas.claim import CLAIM_DEFINITION, ClaimSchema


EXPECTED_SEMANTIC_SLOTS = {
    "indicator",
    "value",
    "unit",
    "time",
    "frequency",
    "region",
    "population",
    "dimension",
    "comparison",
    "calculation",
    "condition",
    "source_hint",
}


def test_claim_contract_contains_and_requires_all_twelve_semantic_slots() -> None:
    schema = claim_output_json_schema()

    assert set(SEMANTIC_SLOT_NAMES) == EXPECTED_SEMANTIC_SLOTS
    assert EXPECTED_SEMANTIC_SLOTS <= set(schema["properties"])
    assert EXPECTED_SEMANTIC_SLOTS <= set(schema["required"])
    assert set(schema["required"]) == set(CLAIM_OUTPUT_FIELD_NAMES)
    assert schema["additionalProperties"] is False


def test_claim_contract_marks_every_optional_field_explicitly_nullable() -> None:
    schema = claim_output_json_schema()
    non_nullable = {"claim_id", "source_sentence", "parse_status"}

    for field_name in set(CLAIM_OUTPUT_FIELD_NAMES) - non_nullable:
        assert "null" in schema["properties"][field_name]["type"]


def test_mapping_slots_are_nullable_string_maps() -> None:
    schema = claim_output_json_schema()

    for field_name in ("dimension", "comparison", "condition"):
        field = schema["properties"][field_name]
        assert field["type"] == ["object", "null"]
        assert field["additionalProperties"] == {"type": "string"}


def test_claim_schema_factory_returns_an_independent_copy() -> None:
    first = claim_output_json_schema()
    first["required"].clear()

    assert claim_output_json_schema()["required"] == list(CLAIM_OUTPUT_FIELD_NAMES)


def test_emit_claim_is_the_only_function_and_reuses_the_claim_schema() -> None:
    tool = emit_claim_tool_definition()

    assert EMIT_CLAIM_FUNCTION_NAME == "emit_claim"
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "emit_claim"
    assert tool["function"]["parameters"] == claim_output_json_schema()


def test_claim_schema_exposes_the_canonical_claim_definition() -> None:
    assert "최소 검증 단위" in CLAIM_DEFINITION
    assert "하나의 최종 판정" in CLAIM_DEFINITION
    assert ClaimSchema.model_json_schema()["description"] == CLAIM_DEFINITION


def test_canonical_claim_definition_is_published_without_drift() -> None:
    for path in (Path("README.md"), Path("docs/reference/03_DATA_SCHEMAS.md")):
        assert CLAIM_DEFINITION in path.read_text(encoding="utf-8")
