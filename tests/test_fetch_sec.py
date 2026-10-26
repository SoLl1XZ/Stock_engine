import json
import os
import zipfile
from pathlib import Path

from stock_engine.fetch_sec import company_profile, ensure_bulk, read_member

HOUR = 3600
NOW = 1_000_000_000.0


class FakeClient:
    def __init__(self) -> None:
        self.downloaded: list[str] = []

    def download(self, url: str, dest: Path) -> Path:
        self.downloaded.append(url)
        dest.write_bytes(b"zip")
        return dest


def make_zip(path: Path, members: dict[str, dict]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, content in members.items():
            z.writestr(name, json.dumps(content))
    return path


def age_file(path: Path, hours: float) -> None:
    os.utime(path, (NOW - hours * HOUR, NOW - hours * HOUR))


def test_read_member_found(tmp_path: Path) -> None:
    zip_path = make_zip(tmp_path / "a.zip", {"CIK0000320193.json": {"name": "Apple"}})
    assert read_member(zip_path, 320193) == {"name": "Apple"}


def test_read_member_accepts_open_zipfile(tmp_path: Path) -> None:
    zip_path = make_zip(tmp_path / "a.zip", {"CIK0000320193.json": {"name": "Apple"}})
    with zipfile.ZipFile(zip_path) as z:
        assert read_member(z, 320193) == {"name": "Apple"}
        assert read_member(z, 320193) == {"name": "Apple"}  # still open after first call


def test_read_member_missing_returns_none(tmp_path: Path) -> None:
    zip_path = make_zip(tmp_path / "a.zip", {"CIK0000320193.json": {}})
    assert read_member(zip_path, 1) is None


def test_ensure_bulk_skips_fresh_and_refetches_stale(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    client = FakeClient()
    facts, subs = ensure_bulk(client, raw_dir, now=NOW)  # missing -> stale
    assert (facts.name, subs.name) == ("companyfacts.zip", "submissions.zip")
    assert len(client.downloaded) == 2

    client.downloaded.clear()
    age_file(facts, 1)
    age_file(subs, 1)
    ensure_bulk(client, raw_dir, now=NOW)
    assert client.downloaded == []

    age_file(facts, 25)
    age_file(subs, 25)
    ensure_bulk(client, raw_dir, now=NOW)
    assert len(client.downloaded) == 2


def test_company_profile_parses_sic() -> None:
    raw = {"sic": "3571", "sicDescription": "Electronic Computers", "fiscalYearEnd": "0926", "category": "Large accelerated filer"}
    assert company_profile(raw) == {
        "sic": 3571,
        "sic_description": "Electronic Computers",
        "fiscal_year_end": "0926",
        "category": "Large accelerated filer",
    }
    empty = {"sic": None, "sic_description": None, "fiscal_year_end": None, "category": None}
    assert company_profile(None) == empty
    assert company_profile({"sic": "", "sicDescription": ""}) == empty
