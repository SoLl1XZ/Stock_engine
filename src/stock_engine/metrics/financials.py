from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

QUARTER_DAYS = range(80, 101)
ANNUAL_DAYS = range(350, 381)


@dataclass(frozen=True)
class Fact:
    start: date | None  # None for instant (balance sheet) facts
    end: date
    val: float
    filed: date


@dataclass(frozen=True)
class Concept:
    taxonomy: str
    tags: tuple[str, ...]  # in priority order
    unit: str
    kind: Literal["flow", "instant"]


def _flow(*tags: str, unit: str = "USD") -> Concept:
    return Concept("us-gaap", tags, unit, "flow")


def _instant(*tags: str, taxonomy: str = "us-gaap", unit: str = "USD") -> Concept:
    return Concept(taxonomy, tags, unit, "instant")


CONCEPTS: dict[str, Concept] = {
    "revenue": _flow(
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ),
    "gross_profit": _flow("GrossProfit"),
    "operating_income": _flow("OperatingIncomeLoss"),
    "net_income": _flow("NetIncomeLoss"),
    "eps_diluted": _flow("EarningsPerShareDiluted", unit="USD/shares"),
    "shares_diluted": _flow("WeightedAverageNumberOfDilutedSharesOutstanding", unit="shares"),
    "operating_cash_flow": _flow("NetCashProvidedByUsedInOperatingActivities"),
    "capex": _flow("PaymentsToAcquirePropertyPlantAndEquipment"),
    "dividends_per_share": _flow("CommonStockDividendsPerShareDeclared", unit="USD/shares"),
    "total_assets": _instant("Assets"),
    "total_liabilities": _instant("Liabilities"),
    "stockholders_equity": _instant("StockholdersEquity"),
    "cash": _instant("CashAndCashEquivalentsAtCarryingValue"),
    "long_term_debt": _instant("LongTermDebtNoncurrent", "LongTermDebt"),
    "shares_outstanding": _instant("EntityCommonStockSharesOutstanding", taxonomy="dei", unit="shares"),
}


def _parse(row: dict) -> Fact:
    start = date.fromisoformat(row["start"]) if row.get("start") else None
    return Fact(start, date.fromisoformat(row["end"]), row["val"], date.fromisoformat(row["filed"]))


def extract_facts(companyfacts: dict, item: str) -> list[Fact]:
    concept = CONCEPTS[item]
    taxonomy = companyfacts.get("facts", {}).get(concept.taxonomy, {})
    chosen: dict[tuple[date | None, date], Fact] = {}
    for tag in concept.tags:
        rows = taxonomy.get(tag, {}).get("units", {}).get(concept.unit, [])
        latest: dict[tuple[date | None, date], Fact] = {}
        for fact in map(_parse, rows):
            key = (fact.start, fact.end)
            # Restatements are re-filed, so the newest filing holds the current value.
            if key not in latest or fact.filed > latest[key].filed:
                latest[key] = fact
        for key, fact in latest.items():
            chosen.setdefault(key, fact)
    return sorted(chosen.values(), key=lambda f: (f.end, f.start or date.min))


def duration_days(f: Fact) -> int:
    if f.start is None:
        raise ValueError("instant fact has no duration")
    return (f.end - f.start).days


def fiscal_label(end: date, fiscal_year_end: str, annual: bool) -> str:
    month, day = int(fiscal_year_end[:2]), int(fiscal_year_end[2:])
    candidates = [date(year, month, day) for year in (end.year - 1, end.year, end.year + 1)]
    # 52/53-week years end up to ~7 days before/after the nominal MMDD.
    fy_end = min(c for c in candidates if c >= end - timedelta(days=7))
    if annual:
        return f"FY{fy_end.year}"
    quarter = 4 - round((fy_end - end).days / 91.3)
    return f"Q{quarter} FY{fy_end.year}"
