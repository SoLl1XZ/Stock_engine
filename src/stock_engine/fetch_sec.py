import json
import time
import zipfile
from pathlib import Path

from stock_engine.sec_client import SecClient

COMPANYFACTS_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
SUBMISSIONS_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"


def ensure_bulk(
    client: SecClient, raw_dir: Path, max_age_hours: float = 20, now: float | None = None
) -> tuple[Path, Path]:
    """Download each bulk zip unless it is younger than max_age_hours; returns (companyfacts, submissions)."""
    now = time.time() if now is None else now
    # The client does not create parent directories.
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for url, name in ((COMPANYFACTS_URL, "companyfacts.zip"), (SUBMISSIONS_URL, "submissions.zip")):
        path = raw_dir / name
        # A missing file counts as stale.
        stale = not path.exists() or now - path.stat().st_mtime > max_age_hours * 3600
        if stale:
            client.download(url, path)
        paths.append(path)
    return paths[0], paths[1]


def read_member(source: Path | zipfile.ZipFile, cik: int) -> dict | None:
    """Read one company's JSON from a bulk zip. An open ZipFile is left open for the caller."""
    if isinstance(source, zipfile.ZipFile):
        return _read_from(source, cik)
    with zipfile.ZipFile(source) as z:
        return _read_from(z, cik)


def _read_from(z: zipfile.ZipFile, cik: int) -> dict | None:
    try:
        with z.open(f"CIK{cik:010d}.json") as f:
            return json.load(f)
    except KeyError:
        return None


def company_profile(submissions: dict | None) -> dict:
    data = submissions or {}
    sic = data.get("sic")
    return {
        "sic": int(sic) if sic else None,
        "sic_description": data.get("sicDescription") or None,
        "fiscal_year_end": data.get("fiscalYearEnd") or None,
        "category": data.get("category") or None,
    }
