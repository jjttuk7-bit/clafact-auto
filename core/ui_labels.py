"""Korean presentation labels for user-facing CLAFACT-AUTO screens."""


_STATUS_LABELS = {
    "AUTO_OK": "자동 처리 가능",
    "HOLD": "보류",
    "HUMAN_REVIEW": "사람 검토 필요",
    "MATCH": "일치",
    "MISMATCH": "불일치",
    "UNDETERMINED": "판정 보류",
    "AUTO": "자동",
}


def translate_status(value: str | None) -> str:
    """Translate stable internal status codes only for display."""
    if value is None:
        return "-"
    return _STATUS_LABELS.get(value, value)
