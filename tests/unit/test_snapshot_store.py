from datetime import date

from core.snapshot_store import save_snapshot


def test_save_snapshot_records_hash_and_query_without_secret(tmp_path) -> None:
    target = tmp_path / "metadata.json"
    result = save_snapshot(target, {"orgId": "101", "tblId": "DT_TEST"}, {"items": ["T1"]})

    saved = target.read_text(encoding="utf-8")
    assert result["response_hash"] in saved
    assert '"orgId": "101"' in saved
    assert "apiKey" not in saved


def test_save_snapshot_records_article_date_and_excludes_api_key(tmp_path) -> None:
    target = tmp_path / "metadata.json"

    result = save_snapshot(
        target,
        {"orgId": "101", "tblId": "DT_TEST", "apiKey": "secret"},
        {"items": ["T1"]},
        article_date=date(2025, 6, 26),
    )

    saved = target.read_text(encoding="utf-8")
    assert result["response_hash"] in saved
    assert '"article_date": "2025-06-26"' in saved
    assert '"tblId": "DT_TEST"' in saved
    assert "secret" not in saved