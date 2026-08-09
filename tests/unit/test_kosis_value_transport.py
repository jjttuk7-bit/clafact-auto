import core.kosis_value_transport as transport


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return b'[{DT:"109.67",PRD_DE:"2025-05"}]'


def test_get_parameter_data_uses_explicit_coordinate(monkeypatch) -> None:
    requested: list[str] = []
    def fake_urlopen(url: str, **_kwargs):
        requested.append(url)
        return Response()
    monkeypatch.setattr(transport, "urlopen", fake_urlopen)

    rows = transport.get_parameter_data("secret", "101", "DT_TEST", "T", "M", "202405", "202505", ["T10", "B01"])

    assert rows == [{"DT": "109.67", "PRD_DE": "2025-05"}]
    assert "objL1=T10" in requested[0]
    assert "objL2=B01" in requested[0]
    assert "apiKey=secret" not in str(rows)


def test_get_parameter_data_retries_transient_connection_failure(monkeypatch) -> None:
    attempts = 0
    def flaky_urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("reset")
        return Response()
    monkeypatch.setattr(transport, "urlopen", flaky_urlopen)
    monkeypatch.setattr(transport, "sleep", lambda _seconds: None)

    rows = transport.get_parameter_data("secret", "101", "DT_TEST", "T", "M", "202405", "202505", ["T10"], retries=2)

    assert rows[0]["DT"] == "109.67"
    assert attempts == 2
