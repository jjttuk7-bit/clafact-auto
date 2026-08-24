from core import official_author_fetcher as fetcher_module


class _Response:
    def read(self) -> bytes:
        return b"ok"


def test_default_opener_uses_project_tls_context(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, *, timeout, context):
        captured.update(request=request, timeout=timeout, context=context)
        return _Response()

    monkeypatch.setattr(fetcher_module, "urlopen", fake_urlopen)

    response = fetcher_module._default_official_opener(object(), timeout=7)

    assert response.read() == b"ok"
    assert captured["timeout"] == 7
    assert captured["context"] is not None
