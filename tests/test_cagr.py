import pytest

from stock_engine.metrics.cagr import cagr, cagr_table


def test_cagr_basic():
    assert cagr(100, 121, 2) == pytest.approx(0.10)


def test_cagr_not_meaningful():
    assert cagr(-5, 10, 3) == "n/m"
    assert cagr(10, 0, 3) == "n/m"


def test_cagr_missing():
    assert cagr(None, 10, 3) is None


def test_cagr_table_horizons():
    annual = {"revenue": [float(100 + 10 * i) for i in range(11)]}
    table = cagr_table(annual)
    assert table["revenue"]["10"] == pytest.approx((200 / 100) ** (1 / 10) - 1)
    assert table["revenue"]["1"] == pytest.approx(200 / 190 - 1)

    short = cagr_table({"revenue": [100.0, 110.0, 120.0, 130.0]})
    assert short["revenue"]["3"] == pytest.approx((130 / 100) ** (1 / 3) - 1)
    assert short["revenue"]["5"] is None
    assert short["revenue"]["10"] is None


def test_book_value_per_share():
    annual = {"stockholders_equity": [1000.0, 1100.0, 1210.0], "shares_diluted": [10.0, 10.0, 10.0]}
    table = cagr_table(annual)
    assert table["book_value_per_share"]["1"] == pytest.approx(0.10)
    assert table["book_value_per_share"]["3"] is None
