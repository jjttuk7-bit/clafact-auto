from core.claim_value_provenance import has_explicit_percent_value


def test_accepts_exact_percent_value_in_source_sentence() -> None:
    assert has_explicit_percent_value("지난달 소비자물가 상승률이 2.4%를 기록했다.", 2.4)


def test_rejects_broad_percent_band_as_claim_value_proof() -> None:
    assert not has_explicit_percent_value("상승률이 2%대에 올라섰다.", 2.0)


def test_rejects_different_percent_value() -> None:
    assert not has_explicit_percent_value("지난달 소비자물가 상승률이 2.4%를 기록했다.", 2.0)
