from stock_engine.config import SEC_USER_AGENT, SITE_DATA_DIR


def test_sec_user_agent_is_noreply_address() -> None:
    assert SEC_USER_AGENT.endswith("@users.noreply.github.com")


def test_site_data_dir_location() -> None:
    assert SITE_DATA_DIR.parts[-2:] == ("site", "data")
