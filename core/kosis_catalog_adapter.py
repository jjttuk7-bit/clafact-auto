"""Read-only adapter boundary for refreshing missing KOSIS table metadata."""
from collections.abc import Callable
from typing import Any

class KosisCatalogAdapter:
    def __init__(self, request: Callable[[str], dict[str, Any]]) -> None:
        self.request = request
    def fetch_table_metadata(self, table_id: str) -> dict[str, Any]:
        payload = self.request(table_id)
        if str(payload.get("TBL_ID", "")) != table_id:
            raise ValueError("KOSIS metadata response does not match requested table")
        return payload
