from core.kosis_http_client import KosisHttpClient

def test_client_retries_then_returns_numeric_value() -> None:
    responses = iter([TimeoutError(), {"value": "70.0"}])
    def transport(_: dict[str, str]) -> object:
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value
    result = KosisHttpClient(transport, retries=2, backoff_seconds=0).fetch({})
    assert result.status == "SUCCESS" and result.value == 70.0

def test_client_returns_invalid_response_status() -> None:
    assert KosisHttpClient(lambda _: {"value": "bad"}, backoff_seconds=0).fetch({}).status == "INVALID_RESPONSE"