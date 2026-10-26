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
    assert sorted(q.items()) == [
        (date(2023, 12, 30), 30),
        (date(2024, 3, 30), 35),
        (date(2024, 6, 29), 40),
        (date(2024, 9, 28), 45),
    ]


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
    first = date(2030, 1, 1)  # after all annual facts, so no Q4 is derived
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
    # The newest periods are kept, oldest first.
    assert s["annual"]["end"][0] == "2014-09-28"
    assert s["annual"]["end"][-1] == "2024-09-28"
    assert s["quarterly"]["end"][0] == (first + timedelta(days=91 * 8 + 90)).isoformat()
    assert s["quarterly"]["end"][-1] == (first + timedelta(days=91 * 19 + 90)).isoformat()
    assert s["quarterly"]["end"] == sorted(s["quarterly"]["end"])


def _quarter_rows(values: list[float], first: date = date(2020, 1, 1)) -> list[dict]:
    return [
        fact(
            (first + timedelta(days=91 * i)).isoformat(),
            (first + timedelta(days=91 * i + 90)).isoformat(),
            v,
            "2030-01-01",
        )
        for i, v in enumerate(values)
    ]


def test_build_statements_ttm_prior_one_year_back():
    s = build_statements(companyfacts({REVENUE: _quarter_rows([1, 2, 3, 4, 5, 6, 7, 8])}), FYE)
    assert s["ttm"]["revenue"] == 26
    assert s["ttm_prior"]["revenue"] == 10


def test_instant_uses_closest_value_within_seven_days():
    cash_tag = "CashAndCashEquivalentsAtCarryingValue"
    data = companyfacts(
        {
            "NetIncomeLoss": [fact(*FY, 60, "2024-11-01")],
            cash_tag: [
                fact(None, "2024-09-26", 11, "2024-11-01"),
                fact(None, "2024-10-03", 22, "2024-11-01"),
                fact(None, "2024-09-01", 33, "2024-11-01"),
            ],
        }
    )
    assert build_statements(data, FYE)["annual"]["cash"] == [11]


def test_ttm_is_none_when_data_is_stale():
    old_quarters = {date(2019, 3, 30) + timedelta(days=91 * i): 10 for i in range(4)}
    assert ttm(old_quarters, date(2024, 9, 28), "flow") is None
    assert ttm({date(2024, 1, 1): 5}, date(2024, 9, 28), "instant") is None
    assert ttm({date(2024, 9, 28): 5}, date(2024, 9, 28), "instant") == 5


def test_current_fiscal_year_quarters_from_ytd_without_annual_fact():
    tag = "NetCashProvidedByUsedInOperatingActivities"
    rows = [
        # FY2024 complete: quarters 30, 35, 40, 45
        fact("2023-10-01", "2023-12-30", 30, "2024-02-01"),
        fact("2023-10-01", "2024-03-30", 65, "2024-05-01"),
        fact("2023-10-01", "2024-06-29", 105, "2024-08-01"),
        fact("2023-10-01", "2024-09-28", 150, "2024-11-01"),
        # FY2025 in progress: 3M = 40, 6M = 90, no 10-K yet
        fact("2024-09-29", "2024-12-28", 40, "2025-02-01"),
        fact("2024-09-29", "2025-03-29", 90, "2025-05-01"),
    ]
    q = quarterly_values(_facts({tag: rows}, "operating_cash_flow"))
    assert q[date(2025, 3, 29)] == 50
    assert ttm(q, date(2025, 3, 29), "flow") == 175


def test_weighted_average_shares_are_not_derived_or_summed():
    tag = "WeightedAverageNumberOfDilutedSharesOutstanding"

    def build(quarter_rows: list[dict]) -> dict:
        data = companyfacts({REVENUE: _revenue_rows(), "NetIncomeLoss": [fact(*FY, 60, "2024-11-01")]})
        data["facts"]["us-gaap"][tag] = {"units": {"shares": quarter_rows + [fact(*FY, 1000, "2024-11-01")]}}
        return build_statements(data, FYE)

    # Q4 is not reported on its own, so it stays empty instead of becoming FY - Q1 - Q2 - Q3 = 0.
    no_q4 = build([fact(*Q1, 1000, "2024-02-01"), fact(*Q2, 1000, "2024-05-01"), fact(*Q3, 1000, "2024-08-01")])
    assert no_q4["quarterly"]["shares_diluted"] == [1000, 1000, 1000, None]
    assert no_q4["annual"]["shares_diluted"] == [1000]
    assert no_q4["ttm"]["shares_diluted"] is None  # newest reported quarter is not current

    q4 = ("2024-06-30", "2024-09-28")
    with_q4 = build([fact(*Q2, 1000, "2024-05-01"), fact(*Q3, 1000, "2024-08-01"), fact(*q4, 1000, "2024-11-01")])
    assert with_q4["quarterly"]["shares_diluted"] == [None, 1000, 1000, 1000]
    assert with_q4["ttm"]["shares_diluted"] == 1000


def test_shares_outstanding_uses_cover_page_date_after_period_end():
    data = _normal_data()
    data["facts"]["dei"] = {
        "EntityCommonStockSharesOutstanding": {"units": {"shares": [fact(None, "2024-11-15", 900, "2024-11-15")]}}
    }
    s = build_statements(data, FYE)
    assert s["annual"]["shares_outstanding"] == [900]
    assert s["ttm"]["shares_outstanding"] == 900
