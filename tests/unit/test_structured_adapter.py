from core.structured_adapter import StructuredOutputAdapter

def test_adapter_validates_provider_json_as_claim_schema() -> None:
    adapter = StructuredOutputAdapter(lambda sentence: {"claim_id":"x","source_sentence":sentence,"indicator":"고용률","value":70,"unit":"%","time":"2024","parse_status":"AUTO_OK"})
    assert adapter.extract("문장").indicator == "고용률"
