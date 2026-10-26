"""Spike: re-download a random sample of tickers that failed in the bulk run, one at a time."""
import json, logging, random, time, io
import yfinance as yf

buf = io.StringIO()
h = logging.StreamHandler(buf); logging.getLogger("yfinance").addHandler(h)
d = json.load(open("spike/out/prices.json"))
failed = [t for b in d["batches"] for t in b["failed"]]
random.seed(1)
sample = random.sample(failed, 200)
t0 = time.time(); ok = []
for t in sample:
    df = yf.download(t, period="10y", auto_adjust=False, progress=False, threads=False)
    if df["Close"].dropna().size: ok.append(t)
    time.sleep(0.3)
print(f"failed total={len(failed)} sample=200 recovered={len(ok)} seconds={time.time()-t0:.0f}")
print("not recovered (first 40):", [t for t in sample if t not in ok][:40])
msgs = {}
for line in buf.getvalue().splitlines():
    if "possibly delisted" in line or "Error" in line or "rate" in line.lower():
        key = line.split(":", 1)[-1][:90]; msgs[key] = msgs.get(key, 0) + 1
print(sorted(msgs.items(), key=lambda x: -x[1])[:5])
