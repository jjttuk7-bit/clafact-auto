"""Secret-safe configuration identifiers for operator diagnostics."""

from hashlib import sha256


def describe_secret_fingerprint(value: str | None) -> str:
    """Return a non-reversible identifier without exposing a secret value."""
    if not value:
        return "미설정"
    fingerprint = sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"설정됨 (SHA-256: {fingerprint})"