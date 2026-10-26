from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from stock_engine.fetch_prices import UpdateResult, load_prices, update_prices


class FakeFetch:
    """Records calls; `nan_tickers` come back all-NaN, `raise_on` makes a call raise."""

    def __init__(
        self,
        days: list[str] = ("2026-10-20", "2026-10-21"),
        value: float = 1.0,
        nan_tickers: set[str] = frozenset(),
        raise_on: set[str] = frozenset(),
        full_days: list[str] | None = None,
        fail_full: bool = False,
    ) -> None:
        self.calls: list[tuple[list[str], date | None]] = []
        self.days = pd.to_datetime(list(days))
        self.value = value
        self.nan_tickers = nan_tickers
        self.raise_on = raise_on
        self.full_days = None if full_days is None else pd.to_datetime(list(full_days))
        self.fail_full = fail_full

    def __call__(self, tickers: list[str], start: date | None):
        self.calls.append((list(tickers), start))
        if self.raise_on & set(tickers):
            raise RuntimeError("yahoo down")
        if start is None and self.fail_full:
            raise RuntimeError("yahoo down")
        days = self.full_days if start is None and self.full_days is not None else self.days
        frame = pd.DataFrame(self.value, index=days, columns=tickers)
        frame[[t for t in tickers if t in self.nan_tickers]] = np.nan
        return frame, frame * 2


def write_cache(cache_dir: Path, ticker: str, day: str, value: float) -> None:
    frame = pd.DataFrame({ticker: [value]}, index=pd.to_datetime([day]))
    frame.to_parquet(cache_dir / "close.parquet")
    (frame * 2).to_parquet(cache_dir / "adj_close.parquet")


def test_first_run_fetches_full_history(tmp_path):
    fetch = FakeFetch()
    cache_dir = tmp_path / "cache"  # does not exist yet

    result = update_prices(["AAA", "BBB"], cache_dir, fetch)

    assert fetch.calls == [(["AAA", "BBB"], None)]
    assert result == UpdateResult(ok=2, failed=[])
    close, adj_close = load_prices(cache_dir)
    assert list(close.columns) == ["AAA", "BBB"]
    assert adj_close.loc["2026-10-21", "AAA"] == 2.0


def test_incremental_run_starts_five_days_back(tmp_path):
    write_cache(tmp_path, "AAA", "2026-10-20", 10.0)
    fetch = FakeFetch(value=10.0)  # same as cached, so no re-based refetch

    update_prices(["AAA", "NEW"], tmp_path, fetch)

    assert (["AAA"], date(2026, 10, 15)) in fetch.calls
    assert (["NEW"], None) in fetch.calls
    assert len(fetch.calls) == 2


def test_overlap_is_overwritten(tmp_path):
    write_cache(tmp_path, "AAA", "2026-10-20", 10.0)

    update_prices(["AAA"], tmp_path, FakeFetch(value=11.0))

    close, _ = load_prices(tmp_path)
    assert close.loc["2026-10-20", "AAA"] == 11.0
    assert close.index.is_monotonic_increasing


def test_batches(tmp_path):
    fetch = FakeFetch()
    tickers = [f"T{i}" for i in range(250)]

    update_prices(tickers, tmp_path, fetch, batch_size=100)

    assert [len(t) for t, _ in fetch.calls] == [100, 100, 50]


def test_all_nan_ticker_counts_as_failed(tmp_path):
    tickers = [f"T{i}" for i in range(10)]
    fetch = FakeFetch(nan_tickers={"T0", "T1", "T2"})

    result = update_prices(tickers, tmp_path, fetch)

    assert result.failed == ["T0", "T1", "T2"]
    assert result.ok == 7
    assert result.failure_ratio == 0.3


def test_failed_ticker_keeps_cached_data(tmp_path):
    write_cache(tmp_path, "AAA", "2026-10-20", 10.0)

    result = update_prices(["AAA"], tmp_path, FakeFetch(nan_tickers={"AAA"}))

    assert result.failed == ["AAA"]
    close, _ = load_prices(tmp_path)
    assert close.loc["2026-10-20", "AAA"] == 10.0


def test_fetch_exception_fails_whole_batch(tmp_path):
    tickers = [f"T{i}" for i in range(250)]
    fetch = FakeFetch(raise_on={"T150"})  # sits in the second batch

    result = update_prices(tickers, tmp_path, fetch, batch_size=100)

    assert len(fetch.calls) == 3
    assert result.failed == tickers[100:200]
    assert result.ok == 150


def test_load_prices_missing_files_gives_empty_frames(tmp_path):
    close, adj_close = load_prices(tmp_path)
    assert close.empty and adj_close.empty


def test_failure_ratio_of_empty_result_is_zero():
    assert UpdateResult(ok=0, failed=[]).failure_ratio == 0


def test_rebased_history_is_refetched_and_replaced(tmp_path):
    cached = pd.DataFrame({"AAA": [10.0, 10.0]}, index=pd.to_datetime(["2026-10-01", "2026-10-20"]))
    cached.to_parquet(tmp_path / "close.parquet")
    (cached * 2).to_parquet(tmp_path / "adj_close.parquet")
    # value 15 -> adj 30 against cached adj 20: a 50 % jump on the overlap.
    fetch = FakeFetch(value=15.0, full_days=["2026-09-30", "2026-10-20", "2026-10-21"])

    result = update_prices(["AAA"], tmp_path, fetch)

    assert fetch.calls == [(["AAA"], date(2026, 10, 15)), (["AAA"], None)]
    assert result == UpdateResult(ok=1, failed=[])
    close, adj_close = load_prices(tmp_path)
    assert list(close.index.strftime("%Y-%m-%d")) == ["2026-09-30", "2026-10-20", "2026-10-21"]
    assert adj_close.loc["2026-09-30", "AAA"] == 30.0


def test_small_overlap_difference_does_not_refetch(tmp_path):
    write_cache(tmp_path, "AAA", "2026-10-20", 10.0)
    fetch = FakeFetch(value=10.005)  # adj 20.01 vs 20: 0.05 %

    update_prices(["AAA"], tmp_path, fetch)

    assert fetch.calls == [(["AAA"], date(2026, 10, 15))]


def test_failed_rebase_refetch_keeps_merged_data_and_counts_failed(tmp_path):
    write_cache(tmp_path, "AAA", "2026-10-20", 10.0)

    result = update_prices(["AAA"], tmp_path, FakeFetch(value=15.0, fail_full=True))

    assert result == UpdateResult(ok=0, failed=["AAA"])
    close, _ = load_prices(tmp_path)
    assert close.loc["2026-10-20", "AAA"] == 15.0


def test_duplicate_input_tickers_are_fetched_once(tmp_path):
    fetch = FakeFetch()

    result = update_prices(["A", "A", "B"], tmp_path, fetch)

    assert fetch.calls == [(["A", "B"], None)]
    assert result.ok == 2


def test_duplicate_dates_in_fetched_data_are_dropped(tmp_path):
    fetch = FakeFetch(days=["2026-10-20", "2026-10-20", "2026-10-21"])

    update_prices(["AAA"], tmp_path, fetch)

    close, adj_close = load_prices(tmp_path)
    assert close.index.is_unique and adj_close.index.is_unique
