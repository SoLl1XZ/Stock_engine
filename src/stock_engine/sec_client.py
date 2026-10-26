import time
from collections.abc import Callable
from pathlib import Path

import httpx

from stock_engine.config import sec_user_agent

BACKOFF_SECONDS: tuple[float, ...] = (1, 2, 4)


class SecClient:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        max_per_second: float = 8,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        user_agent: str | None = None,
    ) -> None:
        self._client = httpx.Client(
            transport=transport,
            headers={"User-Agent": user_agent or sec_user_agent()},
            follow_redirects=True,
            timeout=60,
        )
        self._min_interval = 1 / max_per_second
        self._sleep = sleep
        self._clock = clock
        self._next_allowed = 0.0

    def _wait_for_slot(self) -> None:
        wait = self._next_allowed - self._clock()
        if wait > 0:
            self._sleep(wait)
        # Space request starts evenly; reading the clock again keeps this right after a sleep.
        self._next_allowed = max(self._clock(), self._next_allowed) + self._min_interval

    def _open(self, url: str) -> httpx.Response:
        """Return a streamed 2xx response, retrying 429/5xx with backoff. Caller must close it."""
        for pause in (*BACKOFF_SECONDS, None):
            self._wait_for_slot()
            response = self._client.send(self._client.build_request("GET", url), stream=True)
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or pause is None:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    response.close()
                    raise
                return response
            response.close()
            self._sleep(pause)
        raise AssertionError("unreachable")

    def get_json(self, url: str) -> dict:
        response = self._open(url)
        try:
            response.read()
            return response.json()
        finally:
            response.close()

    def download(self, url: str, dest: Path) -> Path:
        # Write to .part and rename last, so an interrupted download never looks complete.
        part = dest.with_name(dest.name + ".part")
        response = self._open(url)
        try:
            with part.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        finally:
            response.close()
        part.replace(dest)
        return dest
