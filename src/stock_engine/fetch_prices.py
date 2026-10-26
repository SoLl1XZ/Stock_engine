from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

BENCHMARKS = ["SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]

# Returns (close, adj_close) in wide format (DatetimeIndex x tickers); start=None means 10 years.
FetchFn = Callable[[list[str], date | None], tuple[pd.DataFrame, pd.DataFrame]]

# Each run re-fetches this many days so late corrections overwrite the cache; a ticker whose overlap
# no longer matches the cache has been re-based by Yahoo and gets its full history re-fetched.
OVERLAP_DAYS = 5
REBASE_TOLERANCE = 0.001  # relative difference in adj_close that counts as re-based


@dataclass
class UpdateResult:
    ok: int
    failed: list[str]

    @property
    def failure_ratio(self) -> float:
        total = self.ok + len(self.failed)
        return len(self.failed) / total if total else 0.0


def yf_fetch(tickers: list[str], start: date | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = yf.download(
        tickers,
        period="10y" if start is None else None,
        start=start,
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if not isinstance(raw.columns, pd.MultiIndex):
        # Flat columns mean a single ticker; give them the same (ticker, field) shape.
        raw.columns = pd.MultiIndex.from_product([tickers[:1], raw.columns])
    close, adj_close = (raw.xs(field, axis=1, level=1) for field in ("Close", "Adj Close"))
    for frame in (close, adj_close):
        frame.index = frame.index.tz_localize(None)
    return close, adj_close


def load_prices(cache_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    for name in ("close", "adj_close"):
        path = cache_dir / f"{name}.parquet"
        frames.append(pd.read_parquet(path) if path.exists() else pd.DataFrame())
    return frames[0], frames[1]


def _batches(tickers: list[str], size: int) -> list[list[str]]:
    return [tickers[i : i + size] for i in range(0, len(tickers), size)]


def _unique_dates(frame: pd.DataFrame) -> pd.DataFrame:
    # Yahoo occasionally repeats a date; a duplicate index label would break the merge.
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def _fetch_batches(
    tickers: list[str], start: date | None, fetch: FetchFn, batch_size: int
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Fetch in batches; returns (close, adj_close) of the tickers that delivered data, plus the failed ones."""
    closes, adjs, failed = [], [], []
    for batch in _batches(tickers, batch_size):
        try:
            batch_close, batch_adj = fetch(batch, start)
        except Exception:
            # One bad batch must not stop the rest; the caller judges the failure ratio.
            failed += batch
            continue
        good = [t for t in batch if t in batch_close.columns and batch_close[t].notna().any()]
        failed += [t for t in batch if t not in good]
        closes.append(_unique_dates(batch_close[good]))
        adjs.append(_unique_dates(batch_adj.reindex(columns=good)))
    if not closes:
        return pd.DataFrame(), pd.DataFrame(), failed
    return pd.concat(closes, axis=1, sort=True), pd.concat(adjs, axis=1, sort=True), failed


def _rebased_tickers(fresh_adj: pd.DataFrame, cached_adj: pd.DataFrame) -> list[str]:
    """Tickers whose fresh adj_close differs from the cache on overlapping dates (split or dividend)."""
    dates = fresh_adj.index.intersection(cached_adj.index)
    columns = fresh_adj.columns.intersection(cached_adj.columns)
    # Without a shared date and ticker there is nothing to compare (e.g. a run of only new tickers).
    if dates.empty or columns.empty:
        return []
    fresh, cached = fresh_adj.loc[dates, columns], cached_adj.loc[dates, columns]
    differs = ((fresh - cached).abs() > REBASE_TOLERANCE * cached.abs()).any()
    return list(differs[differs].index)


def update_prices(
    tickers: list[str], cache_dir: Path, fetch: FetchFn = yf_fetch, batch_size: int = 100
) -> UpdateResult:
    """Fetch prices into the parquet cache; known tickers incrementally, new ones with full history."""
    tickers = list(dict.fromkeys(tickers))
    close, adj_close = load_prices(cache_dir)
    known = [t for t in tickers if t in close.columns]
    new = [t for t in tickers if t not in close.columns]
    incremental_start = None if close.empty else close.index.max().date() - timedelta(days=OVERLAP_DAYS)

    known_close, known_adj, failed = _fetch_batches(known, incremental_start, fetch, batch_size)
    new_close, new_adj, failed_new = _fetch_batches(new, None, fetch, batch_size)
    failed += failed_new
    fresh_close = pd.concat([known_close, new_close], axis=1, sort=True)
    fresh_adj = pd.concat([known_adj, new_adj], axis=1, sort=True)
    if fresh_close.columns.empty:
        return UpdateResult(ok=0, failed=failed)

    # combine_first lets fresh values win on overlap and keeps the old ones elsewhere.
    merged_close = fresh_close.combine_first(close)
    merged_adj = fresh_adj.combine_first(adj_close)

    # The merge cannot repair history that Yahoo re-based, so such tickers are replaced wholesale.
    rebased = _rebased_tickers(known_adj, adj_close)
    full_close, full_adj, failed_full = _fetch_batches(rebased, None, fetch, batch_size)
    failed += failed_full
    replace = list(full_close.columns)
    # Dropping a column leaves its old dates behind as empty rows; those dates are gone from the new history.
    merged_close = pd.concat([merged_close.drop(columns=replace), full_close], axis=1, sort=True).dropna(how="all")
    merged_adj = pd.concat([merged_adj.drop(columns=replace), full_adj], axis=1, sort=True).dropna(how="all")

    cache_dir.mkdir(parents=True, exist_ok=True)
    merged_close.to_parquet(cache_dir / "close.parquet")
    merged_adj.to_parquet(cache_dir / "adj_close.parquet")
    return UpdateResult(ok=len(tickers) - len(failed), failed=failed)
