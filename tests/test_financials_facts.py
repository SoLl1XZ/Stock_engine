from datetime import date, timedelta

import pytest

from stock_engine.metrics.financials import (
    ANNUAL_DAYS,
    CONCEPTS,
    QUARTER_DAYS,
    Fact,
    duration_days,
    extract_facts,
    fiscal_label,
)
from tests.factories import companyfacts, fact

PRIMARY_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_restated_value_uses_latest_filed():
    data = companyfacts(
        {
            PRIMARY_TAG: [
                fact("2022-10-02", "2023-09-30", 400, "2023-11-03"),
                fact("2022-10-02", "2023-09-30", 405, "2024-11-01"),
            ]
        }
    )
    facts = extract_facts(data, "revenue")
    assert len(facts) == 1
    assert facts[0].val == 405


def test_first_tag_wins_per_period():
    data = companyfacts(
        {
            PRIMARY_TAG: [fact("2022-10-02", "2023-09-30", 405, "2024-11-01")],
            "SalesRevenueNet": [
                fact("2022-10-02", "2023-09-30", 999, "2024-11-01"),
                fact("2021-09-26", "2022-10-01", 380, "2022-11-01"),
            ],
        }
    )
    by_end = {f.end: f.val for f in extract_facts(data, "revenue")}
    assert by_end == {date(2023, 9, 30): 405, date(2022, 10, 1): 380}


def test_instant_fact_has_no_start():
    data = companyfacts({"Assets": [fact(None, "2023-09-30", 100, "2023-11-03")]})
    assert extract_facts(data, "total_assets") == [
        Fact(None, date(2023, 9, 30), 100, date(2023, 11, 3))
    ]


def test_missing_item_gives_empty_list():
    assert extract_facts(companyfacts({}), "revenue") == []


def test_duration_ranges():
    def days(n: int) -> int:
        start = date(2024, 1, 1)
        return duration_days(Fact(start, start + timedelta(days=n), 0, date(2025, 1, 1)))

    assert days(91) in QUARTER_DAYS
    assert days(98) in QUARTER_DAYS
    assert days(182) not in QUARTER_DAYS and days(182) not in ANNUAL_DAYS
    assert days(364) in ANNUAL_DAYS
    assert days(371) in ANNUAL_DAYS


def test_concepts_cover_all_items():
    assert len(CONCEPTS) == 15


@pytest.mark.parametrize(
    "end, fye, annual, expected",
    [
        (date(2023, 12, 30), "0930", False, "Q1 FY2024"),
        (date(2024, 3, 30), "0930", False, "Q2 FY2024"),
        (date(2024, 9, 28), "0930", False, "Q4 FY2024"),
        (date(2024, 9, 28), "0930", True, "FY2024"),
        (date(2024, 1, 2), "1231", True, "FY2023"),
        (date(2024, 3, 31), "1231", False, "Q1 FY2024"),
    ],
)
def test_fiscal_label(end, fye, annual, expected):
    assert fiscal_label(end, fye, annual) == expected
