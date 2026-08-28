from core.direct_value_coordinate_spec_registry import ledger_row_to_registry


def test_ledger_row_rebuilds_lossless_registry_record() -> None:
    row = {
        "원본부모Claim번호": "A1_1", "자식Claim번호": "C1", "기사그룹ID": "A1",
        "원문": "2024년 서울 취업자는 100만 명이다.", "기사작성일": "2025-01-10",
        "지표": "취업자 수", "기사값": "1000000", "단위": "명", "기준시점": "2024",
        "주기": "Y", "지역": "서울", "대상집단": "15세 이상", "차원JSON": '{"sex":"계"}',
        "계산방식": "DIRECT_VALUE", "조건JSON": "", "파싱상태": "AUTO_OK",
        "대상수치표현": "100만 명", "사용집합": "RULE_DISCOVERY",
    }

    record = ledger_row_to_registry(row)

    assert record.claim.claim_id == "C1"
    assert record.article_published_at.isoformat() == "2025-01-10"
    assert record.claim.indicator == "취업자 수"
    assert record.claim.value == 1000000
    assert record.claim.dimension == {"sex": "계"}
    assert record.slot_enrichment["target_numeric_expression"] == "100만 명"


def test_ledger_row_preserves_nested_dimension_as_raw_json() -> None:
    row = {
        "원본부모Claim번호": "A1_1", "자식Claim번호": "C1", "기사그룹ID": "A1",
        "원문": "2024년 자동차 수출은 100대다.", "기사작성일": "2025-01-10",
        "지표": "자동차 수출 대수", "기사값": "100", "단위": "대", "기준시점": "2024",
        "주기": "Y", "차원JSON": '{"품목":["자동차"],"성별":"계"}', "파싱상태": "AUTO_OK",
    }

    record = ledger_row_to_registry(row)



def test_ledger_row_marks_missing_span_for_deterministic_grounding_repair() -> None:
    row = {
        "원본부모Claim번호": "A1_1", "자식Claim번호": "C1", "기사그룹ID": "A1",
        "원문": "2024년 전국 출생아 수는 23만 명이다.", "기사작성일": "2025-01-10",
        "지표": "출생아 수", "기사값": "230000", "단위": "명", "기준시점": "2024",
        "주기": "Y", "지역": "전국", "계산방식": "DIRECT_VALUE", "파싱상태": "AUTO_OK",
    }

    record = ledger_row_to_registry(row)

    assert record.slot_enrichment["target_link_status"] == "TARGET_NOT_FOUND_IN_SOURCE"


def test_child_claims_from_same_sentence_receive_unique_batch_source_keys() -> None:
    base = {
        "원본부모Claim번호": "A1_1", "기사그룹ID": "A1",
        "원문": "2024년 값은 1명과 2명이다.", "기사작성일": "2025-01-10",
        "지표": "인구", "단위": "명", "기준시점": "2024", "주기": "Y",
        "계산방식": "DIRECT_VALUE", "파싱상태": "AUTO_OK",
    }
    first = ledger_row_to_registry(base | {"자식Claim번호": "C1", "기사값": "1", "대상수치표현": "1명"})
    second = ledger_row_to_registry(base | {"자식Claim번호": "C2", "기사값": "2", "대상수치표현": "2명"})

    assert (first.article_id, first.sentence_id) != (second.article_id, second.sentence_id)
    assert first.slot_enrichment["original_sentence_id"] == "1"
