from core.secret_fingerprint import describe_secret_fingerprint


def test_describes_missing_secret_without_hash() -> None:
    assert describe_secret_fingerprint(None) == "미설정"
    assert describe_secret_fingerprint("") == "미설정"


def test_describes_secret_with_stable_non_reversible_fingerprint() -> None:
    secret = "sk-proj-sensitive-test-value"

    description = describe_secret_fingerprint(secret)

    assert description == "설정됨 (SHA-256: d9129f2d0947)"
    assert secret not in description