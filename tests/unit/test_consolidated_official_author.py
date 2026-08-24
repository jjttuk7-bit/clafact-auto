import csv
from pathlib import Path

from core.consolidated_claim_ledger import consolidate_rows, discover_updates


def test_official_author_csv_preserves_document_url_and_routes_unregistered_document(tmp_path: Path) -> None:
    path = tmp_path / "results.csv"
    headers = [
        "부모Claim번호", "자식Claim번호", "최종상태", "중단단계", "중단사유",
        "공식API조회여부", "후보통계표", "공식좌표", "공식값", "계산값", "판정",
        "공표확인", "공식값URL", "공식문서URL", "실행시각",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerow({
            "부모Claim번호": "C1", "자식Claim번호": "child-1", "최종상태": "HOLD",
            "중단단계": "공식문서조회", "중단사유": "OFFICIAL_AUTHOR_DOCUMENT_NOT_REGISTERED",
            "공식API조회여부": "예", "판정": "UNDETERMINED", "공식값URL": "",
            "공식문서URL": "https://official.example/release", "실행시각": "2026-08-24T10:00:00+09:00",
        })

    update = discover_updates([tmp_path], {"C1"}, {})[0]
    row = consolidate_rows([{
        "Claim번호": "C1", "대표문제": "CONTEXT", "다음실행단계": "CLAIM_PARSE", "실행횟수": "0",
    }], [update])[0]

    assert update.source_url == "https://official.example/release"
    assert row["최신공식값출처"] == "https://official.example/release"
    assert row["현재문제묶음"] == "OFFICIAL_PATH"
