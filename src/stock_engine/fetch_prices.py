from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

BENCHMARKS = ["SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]

# Returns (close, adj_close) in wide format (DatetimeIndex x tickers); start=None means 10 years.
FetchFn = Callable[[list[str], date | None], tuple[pd.DataFrame, pd.DataFrame]]

# Re-fetched on every run so late corrections and split/dividend adjustments overwrite the cache.
OVERLAP_DAYS = 5


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


def update_prices(
    tickers: list[str], cache_dir: Path, fetch: FetchFn = yf_fetch, batch_size: int = 100
) -> UpdateResult:
    """Fetch prices into the parquet cache; known tickers incrementally, new ones with full history."""
    close, adj_close = load_prices(cache_dir)
    known = [t for t in tickers if t in close.columns]
    new = [t for t in tickers if t not in close.columns]
    incremental_start = None if close.empty else close.index.max().date() - timedelta(days=OVERLAP_DAYS)

    ok_close, ok_adj, failed = [], [], []
    for group, start in ((known, incremental_start), (new, None)):
        for batch in _batches(group, batch_size):
            try:
                batch_close, batch_adj = fetch(batch, start)
            except Exception:
                # One bad batch must not stop the rest; the caller judges the failure ratio.
                failed += batch
                continue
            good = [t for t in batch if t in batch_close.columns and batch_close[t].notna().any()]
            failed += [t for t in batch if t not in good]
            ok_close.append(batch_close[good])
            ok_adj.append(batch_adj.reindex(columns=good))

    ok = len(tickers) - len(failed)
    if ok:
        cache_dir.mkdir(parents=True, exist_ok=True)
        for name, old, fresh in (("close", close, ok_close), ("adj_close", adj_close, ok_adj)):
            # combine_first lets fresh values win on overlap and keeps the old ones elsewhere.
            merged = pd.concat(fresh, axis=1).combine_first(old)
            merged.to_parquet(cache_dir / f"{name}.parquet")
    return UpdateResult(ok=ok, failed=failed)
