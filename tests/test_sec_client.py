import httpx
import pytest

from stock_engine.sec_client import SecClient


class FakeTime:
    """Fake clock whose sleep advances it, so a correct rate limiter terminates."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


TEST_USER_AGENT = "Stock Engine test@example.com"


def make_client(handler, max_per_second: float = 8) -> tuple[SecClient, FakeTime]:
    fake = FakeTime()
    client = SecClient(
        transport=httpx.MockTransport(handler),
        max_per_second=max_per_second,
        sleep=fake.sleep,
        clock=fake.clock,
        user_agent=TEST_USER_AGENT,
    )
    return client, fake


def test_sends_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        return httpx.Response(200, json={"ok": True})

    client, _ = make_client(handler)
    assert client.get_json("https://example.test/a") == {"ok": True}
    assert seen == [TEST_USER_AGENT]


def test_default_user_agent_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "test@example.com")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        return httpx.Response(200, json={})

    SecClient(transport=httpx.MockTransport(handler)).get_json("https://example.test/a")
    assert seen == ["Stock Engine test@example.com"]


def test_retries_then_succeeds() -> None:
    statuses = iter([503, 503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), json={"ok": True})

    client, fake = make_client(handler)
    assert client.get_json("https://example.test/a") == {"ok": True}
    # Rate-limit pauses are < 1 s, so only backoff pauses remain.
    assert [s for s in fake.sleeps if s >= 1] == [1, 2]


def test_gives_up_after_three_retries() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    client, fake = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_json("https://example.test/a")
    assert len(calls) == 4
    assert [s for s in fake.sleeps if s >= 1] == [1, 2, 4]


def test_rate_limit() -> None:
    client, fake = make_client(lambda request: httpx.Response(200, json={}))
    for _ in range(16):
        client.get_json("https://example.test/a")
    assert sum(fake.sleeps) >= 1.0


def test_download_writes_file(tmp_path) -> None:
    client, _ = make_client(lambda request: httpx.Response(200, content=b"zipbytes"))
    dest = tmp_path / "out.zip"
    assert client.download("https://example.test/f.zip", dest) == dest
    assert dest.read_bytes() == b"zipbytes"
    assert not dest.with_name("out.zip.part").exists()
