from typing import Literal

HORIZONS = (1, 3, 5, 10)
CAGR_ITEMS = ("revenue", "eps_diluted", "free_cash_flow", "dividends_per_share", "book_value_per_share")


def cagr(start: float | None, end: float | None, years: float) -> float | Literal["n/m"] | None:
    if start is None or end is None:
        return None
    # A negative or zero base makes the growth rate meaningless (and the root of a negative ratio complex).
    if start <= 0 or end <= 0:
        return "n/m"
    return (end / start) ** (1 / years) - 1


def _book_value_per_share(equity: float | None, shares: float | None) -> float | None:
    if equity is None or shares is None or shares <= 0:
        return None
    return equity / shares


def _series(annual: dict, item: str) -> list[float | None]:
    if item == "book_value_per_share":
        return [
            _book_value_per_share(e, s)
            for e, s in zip(annual.get("stockholders_equity", []), annual.get("shares_diluted", []))
        ]
    return annual.get(item, [])


def cagr_table(annual: dict) -> dict[str, dict[str, float | str | None]]:
    table: dict[str, dict[str, float | str | None]] = {}
    for item in CAGR_ITEMS:
        values = _series(annual, item)
        table[item] = {
            str(h): cagr(values[-1 - h], values[-1], h) if len(values) > h else None for h in HORIZONS
        }
    return table
