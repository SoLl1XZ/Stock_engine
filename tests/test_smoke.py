import pytest

from stock_engine import config
from stock_engine.config import SITE_DATA_DIR, sec_user_agent


def test_sec_user_agent_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "test@example.com")
    assert sec_user_agent() == "Stock Engine test@example.com"


def test_sec_user_agent_missing_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    # Point ROOT at an empty dir so a developer's real .env cannot leak into the test.
    monkeypatch.setattr(config, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="SEC_CONTACT_EMAIL"):
        sec_user_agent()


def test_site_data_dir_location() -> None:
    assert SITE_DATA_DIR.parts[-2:] == ("site", "data")
