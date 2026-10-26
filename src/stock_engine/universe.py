import re
from dataclasses import dataclass

from stock_engine.sec_client import SecClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
EXCHANGES = {"NYSE", "Nasdaq"}

# shortcut: suffix rules miss some odd listings, replace with an exchange security-type list if one becomes available
NON_COMMON_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"-P[A-Z]?$",  # preferred, e.g. BAC-PL
        r"-W[ST]?$",  # warrants
        r"-UN?$",  # units
        r"-RT?$",  # rights
    )
)
# Nasdaq marks 5-letter warrants/units/rights with a W/U/R suffix (LCIDW); NYSE does not.
NASDAQ_FIVE_LETTER_DERIVATIVE = re.compile(r"^[A-Z]{4}[WUR]$")


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    cik: int
    exchange: str


def _is_common(ticker: str, exchange: str) -> bool:
    if any(p.search(ticker) for p in NON_COMMON_PATTERNS):
        return False
    return not (exchange == "Nasdaq" and NASDAQ_FIVE_LETTER_DERIVATIVE.match(ticker))


def parse_tickers(raw: dict) -> list[Company]:
    companies: dict[str, Company] = {}
    for row in raw["data"]:
        record = dict(zip(raw["fields"], row))
        ticker, exchange = record["ticker"], record["exchange"]
        if exchange not in EXCHANGES or not _is_common(ticker, exchange):
            continue
        companies.setdefault(ticker, Company(ticker, record["name"], record["cik"], exchange))
    return list(companies.values())


def search_index(companies: list[Company]) -> list[dict]:
    return [
        {"t": c.ticker, "n": c.name, "cik": c.cik, "ex": c.exchange}
        for c in sorted(companies, key=lambda c: c.ticker)
    ]


def load_universe(client: SecClient) -> list[Company]:
    return parse_tickers(client.get_json(TICKERS_URL))
