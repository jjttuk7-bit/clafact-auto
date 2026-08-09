from core.claim_output_contract import (
    CLAIM_OUTPUT_FIELD_NAMES,
    SEMANTIC_SLOT_NAMES,
    claim_output_json_schema,
)


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
