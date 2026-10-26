from datetime import date, timedelta

from stock_engine.metrics.financials import build_statements, quarterly_values, ttm, extract_facts
from tests.factories import companyfacts, fact

REVENUE = "RevenueFromContractWithCustomerExcludingAssessedTax"
FYE = "0930"

# FY2024 = 2023-10-01 -> 2024-09-28 (52/53-week year, 364 days)
Q1 = ("2023-10-01", "2023-12-30")
Q2 = ("2023-12-31", "2024-03-30")
Q3 = ("2024-03-31", "2024-06-29")
FY = ("2023-10-01", "2024-09-28")


def _facts(rows: dict[str, list[dict]], item: str = "revenue"):
    return extract_facts(companyfacts(rows), item)


def _revenue_rows(include_q2: bool = True) -> list[dict]:
    rows = [
        fact(*Q1, 100, "2024-02-01"),
        fact(*Q3, 120, "2024-08-01"),
        fact(*FY, 470, "2024-11-01"),
    ]
    if include_q2:
        rows.append(fact(*Q2, 110, "2024-05-01"))
    return rows


def test_q4_from_annual_minus_three_quarters():
    q = quarterly_values(_facts({REVENUE: _revenue_rows()}))
    assert q[date(2024, 9, 28)] == 140


def test_quarters_from_ytd_cash_flow():
    tag = "NetCashProvidedByUsedInOperatingActivities"
    rows = [
        fact("2023-10-01", "2023-12-30", 30, "2024-02-01"),
        fact("2023-10-01", "2024-03-30", 65, "2024-05-01"),
        fact("2023-10-01", "2024-06-29", 105, "2024-08-01"),
        fact("2023-10-01", "2024-09-28", 150, "2024-11-01"),
    ]
    q = quarterly_values(_facts({tag: rows}, "operating_cash_flow"))
    assert list(q.values()) == [30, 35, 40, 45]


def test_missing_quarter_gives_no_q4_and_no_ttm():
    q = quarterly_values(_facts({REVENUE: _revenue_rows(include_q2=False)}))
    assert date(2024, 9, 28) not in q
    assert ttm(q, date(2024, 9, 28), "flow") is None


def test_ttm_flow_and_instant():
    q = quarterly_values(_facts({REVENUE: _revenue_rows()}))
    assert ttm(q, date(2024, 9, 28), "flow") == 470
    cash = {date(2024, 6, 29): 5, date(2024, 9, 28): 7}
    assert ttm(cash, date(2024, 9, 28), "instant") == 7


def _normal_data() -> dict:
    return companyfacts(
        {
            REVENUE: _revenue_rows(),
            "NetIncomeLoss": [fact(*FY, 60, "2024-11-01")],
            "NetCashProvidedByUsedInOperatingActivities": [fact(*FY, 150, "2024-11-01")],
            "PaymentsToAcquirePropertyPlantAndEquipment": [fact(*FY, 50, "2024-11-01")],
            "GrossProfit": [fact(*FY, 200, "2024-11-01")],
        }
    )


def test_build_statements_normal():
    s = build_statements(_normal_data(), FYE)
    assert s["annual"]["label"][-1] == "FY2024"
    assert s["quarterly"]["label"][-1] == "Q4 FY2024"
    assert s["latest_quarter_end"] == "2024-09-28"
    assert s["ttm"]["revenue"] == 470
    assert s["ttm_prior"]["revenue"] is None
    assert s["annual"]["free_cash_flow"][-1] == 100
    assert s["annual"]["gross_profit"][-1] == 200
    assert "free_cash_flow" in s["ttm"] and "shares_outstanding" in s["ttm_prior"]


def test_build_statements_bank():
    data = companyfacts({"Revenues": [fact(*FY, 470, "2024-11-01")]})
    s = build_statements(data, FYE)
    assert s["annual"]["revenue"] == [470]
    assert s["annual"]["gross_profit"] == [None]


def test_build_statements_loss():
    data = companyfacts({"NetIncomeLoss": [fact(*FY, -25, "2024-11-01")]})
    data["facts"]["us-gaap"]["EarningsPerShareDiluted"] = {
        "units": {"USD/shares": [fact(*FY, -0.5, "2024-11-01")]}
    }
    s = build_statements(data, FYE)
    assert s["annual"]["net_income"] == [-25]
    assert s["annual"]["eps_diluted"] == [-0.5]


def test_build_statements_caps_lengths():
    annual = [
        fact(f"{y - 1}-10-01", f"{y}-09-28", 100 + y, f"{y}-11-01") for y in range(2010, 2025)
    ]
    first = date(2020, 1, 1)
    quarters = [
        fact(
            (first + timedelta(days=91 * i)).isoformat(),
            (first + timedelta(days=91 * i + 90)).isoformat(),
            10 + i,
            "2025-01-01",
        )
        for i in range(20)
    ]
    s = build_statements(companyfacts({REVENUE: annual + quarters}), FYE)
    assert len(s["annual"]["end"]) == 11
    assert len(s["quarterly"]["end"]) == 12
    assert s["annual"]["end"] == sorted(s["annual"]["end"])
