"""M0 spike: download SEC bulk zips, measure size/time and single-file read. Throwaway code."""
import json
import time
import zipfile

import httpx

from stock_engine.config import RAW_DIR, sec_user_agent

URLS = {
    "companyfacts": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
}
RAW_DIR.mkdir(parents=True, exist_ok=True)
out: dict = {}
for name, url in URLS.items():
    path = RAW_DIR / f"{name}.zip"
    t0 = time.time()
    status = None
    with httpx.stream("GET", url, headers={"User-Agent": sec_user_agent()}, timeout=600,
                      follow_redirects=True) as r:
        status = r.status_code
        if r.status_code == 200:
            with open(path, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
    secs = time.time() - t0
    rec = {"url": url, "status": status, "download_seconds": round(secs, 1)}
    if status == 200:
        rec["zip_mb"] = round(path.stat().st_size / 1e6, 1)
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            rec["files"] = len(infos)
            rec["unzipped_mb"] = round(sum(i.file_size for i in infos) / 1e6, 1)
            t1 = time.time()
            member = "CIK0000320193.json"
            data = json.loads(z.read(member))
            rec["read_apple_seconds"] = round(time.time() - t1, 3)
            rec["apple_json_kb"] = round(z.getinfo(member).file_size / 1e3, 1)
    out[name] = rec
    print(name, rec, flush=True)
json.dump(out, open("spike/out/sec_bulk.json", "w"), indent=2)
