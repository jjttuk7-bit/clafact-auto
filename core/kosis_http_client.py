from dataclasses import dataclass
from time import sleep
from typing import Callable, Literal

@dataclass(frozen=True, slots=True)
class HttpKosisValue:
    value: float | None
    status: Literal["SUCCESS", "TIMEOUT", "INVALID_RESPONSE"]

class KosisHttpClient:
    def __init__(self, transport: Callable[[dict[str, str]], object], *, retries: int = 3, backoff_seconds: float = 0.25) -> None:
        self.transport, self.retries, self.backoff_seconds = transport, retries, backoff_seconds
    def fetch(self, params: dict[str, str]) -> HttpKosisValue:
        for attempt in range(self.retries):
            try:
                response = self.transport(params)
                value = response.get("value") if isinstance(response, dict) else None
                return HttpKosisValue(float(value), "SUCCESS")
            except (TimeoutError, ConnectionError):
                if attempt + 1 < self.retries: sleep(self.backoff_seconds * 2**attempt)
            except (TypeError, ValueError): return HttpKosisValue(None, "INVALID_RESPONSE")
        return HttpKosisValue(None, "TIMEOUT")
