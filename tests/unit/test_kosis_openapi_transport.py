import pytest
import ssl

import core.kosis_openapi_transport as transport


class Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload


def test_get_meta_returns_json_metadata(monkeypatch) -> None:
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(b'{"items": []}'))
    assert transport.get_meta("secret", "101", "DT_TEST", retries=1) == {"items": []}


def test_get_meta_hides_non_json_response_details(monkeypatch) -> None:
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(b"<html>gateway</html>"))
    with pytest.raises(RuntimeError, match="KOSIS_METADATA_INVALID_RESPONSE"):
        transport.get_meta("secret", "101", "DT_TEST", retries=1)


def test_get_meta_normalizes_kosis_error_code_without_message(monkeypatch) -> None:
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(b'{err:"30",errMsg:"not available"}'))
    with pytest.raises(RuntimeError, match="KOSIS_METADATA_API_ERROR_30"):
        transport.get_meta("secret", "101", "DT_TEST", retries=1)


def test_get_meta_normalizes_json_kosis_error_code_without_message(monkeypatch) -> None:
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(b'{"err":"30","errMsg":"not available"}'))

    with pytest.raises(RuntimeError, match="KOSIS_METADATA_API_ERROR_30"):
        transport.get_meta("secret", "101", "DT_TEST", retries=1)

def test_get_meta_accepts_legacy_kosis_array_metadata(monkeypatch) -> None:
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(b'[{STAT_ID:"1964001",DEPT_NM:"department"}]'))
    assert transport.get_meta("secret", "101", "DT_TEST", retries=1) == [{"STAT_ID": "1964001", "DEPT_NM": "department"}]


def test_get_meta_accepts_a_configured_timeout(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_urlopen(_request, *, timeout, context):
        observed['timeout'] = timeout
        return Response(b'{"items": []}')

    monkeypatch.setattr(transport, 'urlopen', fake_urlopen)
    transport.get_meta('secret', '101', 'DT_TEST', retries=1, timeout_seconds=5)

    assert observed['timeout'] == 5


def test_get_meta_uses_tls_12_compatibility_context(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_urlopen(_request, *, timeout, context):
        observed["context"] = context
        return Response(b'{"items": []}')

    monkeypatch.setattr(transport, "urlopen", fake_urlopen)

    transport.get_meta("secret", "101", "DT_TEST", retries=1)

    context = observed["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert context.maximum_version == ssl.TLSVersion.TLSv1_2
def test_get_meta_repairs_kosis_cp949_mojibake_in_nested_metadata(monkeypatch) -> None:
    payload = '{"ITM_NM":"Ãµ¸í","members":[{"OBJ_NM":"¼ºº°","ITM_NM":"°è"}]}'.encode("utf-8")
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(payload))

    assert transport.get_meta("secret", "101", "DT_TEST", retries=1) == {
        "ITM_NM": "천명", "members": [{"OBJ_NM": "성별", "ITM_NM": "계"}],
    }
def test_get_meta_retries_empty_period_metadata_response(monkeypatch) -> None:
    payloads = iter([b"[]", '[{"PRD_SE":"월","STRT_PRD_DE":"2024.01"}]'.encode("utf-8")])
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(next(payloads)))
    monkeypatch.setattr(transport, "sleep", lambda _seconds: None)

    result = transport.get_meta("secret", "101", "DT_TEST", meta_type="PRD", retries=2)

    assert result == [{"PRD_SE": "월", "STRT_PRD_DE": "2024.01"}]
