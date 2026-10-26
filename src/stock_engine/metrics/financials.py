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
    kind: Literal["flow", "instant", "average"]


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
    "shares_diluted": Concept("us-gaap", ("WeightedAverageNumberOfDilutedSharesOutstanding",), "shares", "average"),
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


def annual_values(facts: list[Fact]) -> dict[date, float]:
    return {f.end: f.val for f in facts if f.start is not None and duration_days(f) in ANNUAL_DAYS}


def instant_values(facts: list[Fact]) -> dict[date, float]:
    return {f.end: f.val for f in facts if f.start is None}


def _direct_quarters(flows: list[Fact]) -> dict[date, float]:
    return {f.end: f.val for f in flows if duration_days(f) in QUARTER_DAYS}


def _same_start_groups(flows: list[Fact]) -> list[list[Fact]]:
    """Group facts whose start dates are within 3 days: the 3M/6M/9M/12M year-to-date chain of one fiscal year."""
    groups: list[list[Fact]] = []
    for f in sorted(flows, key=lambda f: (f.start, f.end)):
        if groups and (f.start - groups[-1][-1].start).days <= 3:
            groups[-1].append(f)
        else:
            groups.append([f])
    return groups


def quarterly_values(facts: list[Fact]) -> dict[date, float]:
    flows = [f for f in facts if f.start is not None]
    quarters = _direct_quarters(flows)
    # 10-Q cash flows are year-to-date, so a quarter is the difference between neighbours. This runs for every
    # fiscal year, not only those with a filed 10-K, so the current year's quarters are derived too.
    for group in _same_start_groups(flows):
        cumulative = sorted(group, key=lambda f: f.end)
        for previous, current in zip([None] + cumulative, cumulative):
            span = duration_days(current) - (duration_days(previous) if previous else 0)
            if current.end not in quarters and span in QUARTER_DAYS:
                # shortcut: per-share items (EPS, DPS) are derived by subtraction like flows, slightly off when share count changes within the year
                quarters[current.end] = current.val - (previous.val if previous else 0)
    for annual in (f for f in flows if duration_days(f) in ANNUAL_DAYS):
        if annual.end not in quarters:
            inside = [
                v
                for end, v in quarters.items()
                if annual.start + timedelta(days=80) <= end <= annual.end - timedelta(days=80)
            ]
            if len(inside) == 3:
                quarters[annual.end] = annual.val - sum(inside)
    return quarters


def ttm(values: dict[date, float], as_of: date, kind: str) -> float | None:
    """kind: "flow" sums 4 quarters, "average" takes the latest quarter, "instant" takes the latest balance."""
    if kind == "instant":
        return _pick(values, as_of - timedelta(days=100), as_of + timedelta(days=7), latest=True)
    ends = sorted(end for end in values if end <= as_of)
    # A newest quarter that ended long before as_of means the data is stale, not current.
    if not ends or (as_of - ends[-1]).days > 7:
        return None
    if kind == "average":
        return values[ends[-1]]
    last_four = ends[-4:]
    if len(last_four) < 4:
        return None
    # A gap over 100 days means a quarter is missing, so the sum would not cover a full year.
    if any((b - a).days > 100 for a, b in zip(last_four, last_four[1:])):
        return None
    return sum(values[end] for end in last_four)


def _pick(values: dict[date, float], low: date, high: date, latest: bool) -> float | None:
    ends = [end for end in values if low <= end <= high]
    if not ends:
        return None
    return values[max(ends) if latest else min(ends)]


def _instant_near(values: dict[date, float], end: date) -> float | None:
    close = [d for d in values if abs((d - end).days) <= 7]
    return values[min(close, key=lambda d: abs((d - end).days))] if close else None


def _free_cash_flow(operating_cash_flow: float | None, capex: float | None) -> float | None:
    if operating_cash_flow is None or capex is None:
        return None
    return operating_cash_flow - capex


def build_statements(companyfacts: dict, fiscal_year_end: str) -> dict:
    annual: dict[str, dict[date, float]] = {}
    quarterly: dict[str, dict[date, float]] = {}
    instants: dict[str, dict[date, float]] = {}
    for item, concept in CONCEPTS.items():
        facts = extract_facts(companyfacts, item)
        if concept.kind != "instant":
            annual[item] = annual_values(facts)
            # Weighted averages cannot be derived by subtraction, so only directly reported quarters count.
            quarterly[item] = (
                quarterly_values(facts)
                if concept.kind == "flow"
                else _direct_quarters([f for f in facts if f.start is not None])
            )
        else:
            instants[item] = instant_values(facts)

    def table(ends: list[date], is_annual: bool) -> dict:
        flows = annual if is_annual else quarterly
        result: dict = {
            "end": [end.isoformat() for end in ends],
            "label": [fiscal_label(end, fiscal_year_end, is_annual) for end in ends],
        }
        for item in CONCEPTS:
            if item in flows:
                result[item] = [flows[item].get(end) for end in ends]
            elif item == "shares_outstanding":
                # The dei count is a cover-page figure dated weeks after the period end, so look forward.
                result[item] = [
                    _pick(instants[item], end - timedelta(days=7), end + timedelta(days=120), latest=False)
                    for end in ends
                ]
            else:
                result[item] = [_instant_near(instants[item], end) for end in ends]
        result["free_cash_flow"] = [
            _free_cash_flow(o, c) for o, c in zip(result["operating_cash_flow"], result["capex"])
        ]
        return result

    def ttm_at(as_of: date | None) -> dict:
        result: dict = {}
        for item, concept in CONCEPTS.items():
            if as_of is None:
                result[item] = None
            elif concept.kind != "instant":
                result[item] = ttm(quarterly[item], as_of, concept.kind)
            elif item == "shares_outstanding":
                result[item] = _pick(instants[item], date.min, as_of + timedelta(days=120), latest=True)
            else:
                result[item] = ttm(instants[item], as_of, "instant")
        result["free_cash_flow"] = _free_cash_flow(result["operating_cash_flow"], result["capex"])
        return result

    annual_ends = sorted(set(annual["revenue"]) | set(annual["net_income"]))
    quarter_ends = sorted(set(quarterly["revenue"]) | set(quarterly["net_income"]))
    latest = quarter_ends[-1] if quarter_ends else None
    prior_candidates = [
        e for e in quarter_ends if latest and latest - timedelta(days=380) <= e <= latest - timedelta(days=350)
    ]
    return {
        "annual": table(annual_ends[-11:], True),
        "quarterly": table(quarter_ends[-12:], False),
        "ttm": ttm_at(latest),
        "ttm_prior": ttm_at(prior_candidates[-1] if prior_candidates else None),
        "latest_quarter_end": latest.isoformat() if latest else None,
    }
