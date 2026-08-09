import pytest

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


def test_get_meta_accepts_legacy_kosis_array_metadata(monkeypatch) -> None:
    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response(b'[{STAT_ID:"1964001",DEPT_NM:"department"}]'))
    assert transport.get_meta("secret", "101", "DT_TEST", retries=1) == [{"STAT_ID": "1964001", "DEPT_NM": "department"}]
