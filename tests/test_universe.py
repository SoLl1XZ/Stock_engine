from stock_engine.universe import Company, TICKERS_URL, load_universe, parse_tickers, search_index

FIELDS = ["cik", "name", "ticker", "exchange"]


def raw_of(*rows: list) -> dict:
    return {"fields": FIELDS, "data": [list(row) for row in rows]}


def tickers_of(raw: dict) -> list[str]:
    return [company.ticker for company in parse_tickers(raw)]


def test_keeps_only_nyse_and_nasdaq() -> None:
    raw = raw_of(
        [1, "Keep Nasdaq", "AAA", "Nasdaq"],
        [2, "Keep Nyse", "BBB", "NYSE"],
        [3, "Otc", "CCC", "OTC"],
        [4, "Cboe", "DDD", "CBOE"],
        [5, "No exchange", "EEE", None],
    )
    assert tickers_of(raw) == ["AAA", "BBB"]


def test_drops_non_common_shares() -> None:
    raw = raw_of(
        [1, "Bank pref", "BAC-PL", "NYSE"],
        [2, "Warrant", "ABC-WT", "NYSE"],
        [3, "Unit", "ABC-UN", "NYSE"],
        [4, "Right", "ABC-RT", "NYSE"],
        [5, "Lucid warrant", "LCIDW", "Nasdaq"],
        [6, "Spac unit", "ABCDU", "Nasdaq"],
        [7, "Spac right", "ABCDR", "Nasdaq"],
        [8, "Common", "OK", "NYSE"],
    )
    assert tickers_of(raw) == ["OK"]


def test_keeps_share_classes() -> None:
    raw = raw_of(
        [1067983, "Berkshire", "BRK-B", "NYSE"],
        [1652044, "Alphabet C", "GOOG", "Nasdaq"],
        [1652044, "Alphabet A", "GOOGL", "Nasdaq"],
    )
    assert tickers_of(raw) == ["BRK-B", "GOOG", "GOOGL"]


def test_dedupes_ticker() -> None:
    raw = raw_of(
        [1, "First", "AAA", "Nasdaq"],
        [2, "Second", "AAA", "Nasdaq"],
    )
    assert parse_tickers(raw) == [Company("AAA", "First", 1, "Nasdaq")]


def test_search_index_shape() -> None:
    companies = parse_tickers(
        raw_of(
            [789019, "Microsoft Corp", "MSFT", "Nasdaq"],
            [320193, "Apple Inc.", "AAPL", "Nasdaq"],
        )
    )
    index = search_index(companies)
    assert all(set(entry) == {"t", "n", "cik", "ex"} for entry in index)
    assert index == [
        {"t": "AAPL", "n": "Apple Inc.", "cik": 320193, "ex": "Nasdaq"},
        {"t": "MSFT", "n": "Microsoft Corp", "cik": 789019, "ex": "Nasdaq"},
    ]


def test_load_universe_fetches_tickers_url() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get_json(self, url: str) -> dict:
            self.urls.append(url)
            return raw_of([320193, "Apple Inc.", "AAPL", "Nasdaq"])

    client = FakeClient()
    assert load_universe(client) == [Company("AAPL", "Apple Inc.", 320193, "Nasdaq")]
    assert client.urls == [TICKERS_URL]
