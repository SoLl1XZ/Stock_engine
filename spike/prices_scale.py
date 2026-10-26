"""M0 spike: how well does yfinance hold up on all NYSE+Nasdaq tickers? Throwaway code."""
import json
import re
import sys
import time
from collections import Counter

import httpx
import yfinance as yf
from yfinance import shared

from stock_engine.config import SEC_USER_AGENT

BATCH_SIZE = 100
PAUSE_SECONDS = 1.5  # fixed courtesy pause between batches, no evasion
OUT = "spike/out/prices.json"
LOG = "spike/out/prices.log"

def sec_tickers() -> list[str]:
    resp = httpx.get(
        "https://www.sec.gov/files/company_tickers_exchange.json",
        headers={"User-Agent": SEC_USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = [dict(zip(payload["fields"], r)) for r in payload["data"]]
    return sorted({r["ticker"] for r in rows if r["exchange"] in {"NYSE", "Nasdaq"}})


def nasdaqtrader_tickers() -> list[str]:
    """Fallback when sec.gov answers 403: Nasdaq's own symbol directory, non-ETF, non-test."""
    base = "https://www.nasdaqtrader.com/dynamic/SymDir/"
    found: set[str] = set()
    for fname, sym_col, exch_col in [("nasdaqlisted.txt", "Symbol", None), ("otherlisted.txt", "ACT Symbol", "Exchange")]:
        lines = httpx.get(base + fname, timeout=60).text.splitlines()
        header = lines[0].split("|")
        for line in lines[1:]:
            rec = dict(zip(header, line.split("|")))
            if rec.get(sym_col) is None or "File Creation" in line:
                continue
            if rec.get("ETF") != "N" or rec.get("Test Issue") != "N":
                continue
            if exch_col and rec[exch_col] != "N":  # N = NYSE
                continue
            # skip warrants/units/rights/preferreds (contain $ or .)
            if re.search(r"[$.]", rec[sym_col]):
                continue
            found.add(rec[sym_col].replace(".", "-"))
    return sorted(found)


try:
    tickers = sec_tickers()
    SOURCE = "sec company_tickers_exchange.json"
except httpx.HTTPStatusError as e:
    SOURCE = f"nasdaqtrader fallback (SEC answered {e.response.status_code})"
    tickers = nasdaqtrader_tickers()
print("ticker source:", SOURCE, len(tickers), flush=True)
limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(tickers)
tickers = tickers[:limit]
batches = [tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

results: list[dict] = []
error_types: Counter = Counter()
ok_total = 0
start = time.time()
log = open(LOG, "w")

for n, batch in enumerate(batches, 1):
    t0 = time.time()
    shared._ERRORS.clear()
    exc = None
    ok: list[str] = []
    try:
        df = yf.download(batch, period="10y", auto_adjust=False, group_by="ticker",
                         threads=True, progress=False)
        if len(batch) == 1:
            ok = batch if df["Close"].dropna().size else []
        else:
            level0 = set(df.columns.get_level_values(0)) if not df.empty else set()
            ok = [t for t in batch if t in level0 and df[t]["Close"].dropna().size > 0]
    except Exception as e:  # record exactly, do not hide
        exc = f"{type(e).__name__}: {e}"
        error_types[type(e).__name__] += 1
    errs = dict(shared._ERRORS)
    for msg in errs.values():
        error_types[str(msg).split(":")[0][:80]] += 1
    ok_total += len(ok)
    rec = {"batch": n, "size": len(batch), "ok": len(ok), "seconds": round(time.time() - t0, 1),
           "exception": exc, "errors": errs, "failed": [t for t in batch if t not in ok]}
    results.append(rec)
    print(f"batch {n}/{len(batches)} ok={len(ok)}/{len(batch)} {rec['seconds']}s "
          f"exc={exc} errors={len(errs)} cumulative_ok={ok_total}", file=log, flush=True)
    json.dump({"source": SOURCE, "total": len(tickers), "ok_so_far": ok_total, "elapsed": round(time.time() - start, 1),
               "error_types": error_types, "batches": results}, open(OUT, "w"))
    time.sleep(PAUSE_SECONDS)

print(f"DONE total={len(tickers)} ok={ok_total} elapsed={time.time()-start:.0f}s", file=log, flush=True)
