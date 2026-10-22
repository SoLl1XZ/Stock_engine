# Stock Engine M0–M3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fra tomt repo til første offentlige udgave på GitHub Pages. Den har søgning i hele universet og en aktieside med
header, kursgraf, nøgletal, regnskabshistorik og CAGR (spec-milepæl M0–M3).

**Architecture:** Python-pipelinen (`src/stock_engine/`) henter SEC-bulkfiler og kurser fra `yfinance`, beregner pr. ticker
og skriver statisk JSON til `site/data/`. Den statiske side (`site/`) læser `search.json` og én `t/<TICKER>.json` pr. aktie.
GitHub Actions bygger og udgiver `site/` til Pages uden at committe data.

**Tech Stack:** Python 3.11, `httpx`, `pandas` 3.0.6, `numpy` 2.4.6, `pyarrow` 25.0.1, `yfinance` 1.7.0,
`python-dotenv` 1.2.4, `pytest` 9.1.1. Vanilla JS med Chart.js 4.5.1 og `chartjs-adapter-date-fns` 3.0.0 fra jsDelivr.
JS-tests med `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-22-stock-engine-design.md`

**Hvorfor kun M0–M3:** M0's spike afgør, om `yfinance` holder som kursdatakilde. M4–M9 får hver sin plan, når M3 er
udgivet, så de bygger på de rigtige målinger og den rigtige JSON-struktur.

## Global Constraints

- Python 3.11+ i `.venv/`. Afhængigheder fastlåses i `requirements.txt` (`httpx` til den version, pip vælger, plus `-e .`).
- Sprog: UI på engelsk. Kode, navne og commits på engelsk. Dokumentation (`CLAUDE.md`, `docs/`) på dansk.
- SEC: header `User-Agent: Stock Engine 222303744+SoLl1XZ@users.noreply.github.com` på alle kald, højst 10 kald/s (vi bruger 8).
- Ingen netværk i tests. Hentefunktioner tager en `transport` eller en `fetch`-funktion, som tests erstatter.
- `site/data/`, `data/` og `.env` står i `.gitignore` og committes aldrig.
- `FINNHUB_API_KEY` bruges ikke før M4, men `.env.example` skal have linjen fra Task 1.
- Hver `site/data/t/<TICKER>.json` er højst 80 KB. Kurser: daglige punkter de seneste 730 dage, ugentlige (sidste handelsdag i ugen) før det.
- Kurshistorik: 10 år.
- CAGR = `(slut / start) ** (1 / år) − 1`. Hvis start eller slut er ≤ 0, skrives `"n/m"`. Mangler data, skrives `null` (vises som "—").
- Udgivelsen stopper (exit-kode 1, intet skrevet), hvis mere end 20 % af kursopslagene fejler.
- Footer på hver side: kilder (SEC EDGAR, Yahoo Finance via yfinance), dato for opdatering og "Not investment advice."
- Python: type hints og f-strings. JS: følg mønstret fra `macro_dashboard/lib.js` (rene funktioner i `lib.js`, eksporteret med
  `if (typeof module === "object" && module.exports)`).
- Commit-beskeder slutter med `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Spørg Erik før: `git push`, oprettelse af GitHub-repo, ændringer uden for `stock_engine/`.

## Review Focus

1. **Tickers med bindestreg, punktum og flere aktieklasser** (BRK-B, "brk.b", GOOG/GOOGL): Søgningen finder dem, og begge
   klasser får deres egen side. Testes i Task 4 (`test_keeps_share_classes`) og Task 12 (`normalizeQuery`).
2. **Regnskabsår, der ikke slutter 31/12, og 52/53-ugers år** (AAPL slutter sidste lørdag i september): Perioderne bliver
   klassificeret og navngivet rigtigt. Testes i Task 6 (`fiscal_label`, varighedsgrænser).
3. **Tal, der er rettet i en senere filing:** Den nyeste filing vinder. Testes i Task 6 (`test_restated_value_uses_latest_filed`).
4. **Ukendt ticker eller ticker uden regnskabsdata:** Siden viser "Ticker not found" eller "No data" pr. sektion og aldrig en
   tom side. Testes i Task 11 (`test_build_ticker_without_facts`) og Task 12 (`parseRoute`), og browsertjekkes i Task 13.
5. **Yahoo fejler for nogle eller alle tickers:** NaN-tickers tælles som fejl, og over 20 % stopper udgivelsen. Testes i
   Task 9 (`test_all_nan_ticker_counts_as_failed`) og Task 11 (`test_main_aborts_on_price_failures`).

---

### Task 1: Projektopsætning

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env.example`, `CLAUDE.md`, `src/stock_engine/__init__.py`,
  `src/stock_engine/config.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: `stock_engine.config` med `ROOT: Path`, `DATA_DIR = ROOT / "data"`, `RAW_DIR = DATA_DIR / "raw"`,
  `CACHE_DIR = DATA_DIR / "cache"`, `SITE_DIR = ROOT / "site"`, `SITE_DATA_DIR = SITE_DIR / "data"`,
  `SEC_USER_AGENT: str` (værdien fra Global Constraints).

- [ ] **Step 1:** `pyproject.toml` som i `backtester` (setuptools, `where = ["src"]`, `testpaths = ["tests"]`), navn `stock_engine`.
- [ ] **Step 2:** `.gitignore`: `.venv/`, `__pycache__/`, `data/`, `site/data/`, `.env`, `spike/out/`. `.env.example`: `FINNHUB_API_KEY=`.
- [ ] **Step 3:** Kør `python3.11 -m venv .venv && .venv/bin/pip install pandas==3.0.6 numpy==2.4.6 pyarrow==25.0.1 yfinance==1.7.0 python-dotenv==1.2.4 pytest==9.1.1 httpx && .venv/bin/pip install -e .`. Skriv de fastlåste versioner i `requirements.txt`.
- [ ] **Step 4:** Skriv `tests/test_smoke.py`: `assert SEC_USER_AGENT.endswith("@users.noreply.github.com")` og `assert SITE_DATA_DIR.parts[-2:] == ("site", "data")`.
- [ ] **Step 5:** Kør `.venv/bin/python -m pytest -q`. Forventet: `2 passed`.
- [ ] **Step 6:** `CLAUDE.md` på dansk: hvad projektet er (2 linjer fra spec'ens afsnit 1), afsnittene Kør, Test (`.venv/bin/python -m pytest -q`, `node --test tests/js/`), Mappestruktur (spec'ens afsnit 3) og link til spec og plan.
- [ ] **Step 7:** Commit `chore: project setup`.

### Task 2: M0-spike, kursdata og SEC-bulk i stor skala (kode smides væk)

**Files:**
- Create: `spike/prices_scale.py`, `spike/sec_bulk.py`, `docs/spike-m0.md`
- `spike/` er engangskode. Kun `docs/spike-m0.md` med målingerne er resultatet.

- [ ] **Step 1:** `spike/prices_scale.py`: hent `https://www.sec.gov/files/company_tickers_exchange.json` (med User-Agent). Filtrér til `exchange in {"NYSE", "Nasdaq"}`. Kør `yf.download(batch, period="10y", auto_adjust=False, group_by="ticker", threads=True, progress=False)` i batches af 100. Log pr. batch: sekunder, antal tickers med mindst én kurs og fejltekster. Skriv JSON til `spike/out/prices.json`.
- [ ] **Step 2:** `spike/sec_bulk.py`: download `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` og `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`. Mål MB og sekunder for hver, og tiden for at læse `CIK0000320193.json` fra zip'en uden at pakke resten ud.
- [ ] **Step 3:** Kør begge lokalt. Notér tal i `docs/spike-m0.md`: antal tickers, succesrate, samlet tid, største fejltyper, zip-størrelser og tider.
- [ ] **Step 4: STOP, spørg Erik:** Må vi oprette det **offentlige** GitHub-repo `stock_engine` og pushe? (Pages er kun gratis med et offentligt repo.) Først efter et ja: tilføj `.github/workflows/spike.yml` (`workflow_dispatch`, ubuntu-latest, Python 3.11, kører `spike/prices_scale.py`, uploader `spike/out/` som artifact), push, kør den og notér tallene fra runneren i `docs/spike-m0.md`.
- [ ] **Step 5: Beslutning (Erik):** Ved en succesrate på 95 % eller mere fra runneren fortsætter vi med `yfinance`. Ellers stopper vi før Task 9, og Erik vælger en anden kilde. Task 3–8 afhænger ikke af valget og kan fortsætte.
- [ ] **Step 6:** Commit `docs: M0 spike results` (kun `docs/spike-m0.md` og `spike/`, ikke `spike/out/`).

### Task 3: SEC-klient

**Files:**
- Create: `src/stock_engine/sec_client.py`, `tests/test_sec_client.py`

**Interfaces:**
- Produces: `class SecClient(transport: httpx.BaseTransport | None = None, max_per_second: float = 8, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic)` med `get_json(url: str) -> dict` og `download(url: str, dest: Path) -> Path`. Hvis status er 429 eller 5xx, prøves der igen 3 gange med pauser på 1, 2 og 4 s (via `sleep`). Derefter kaldes `httpx.HTTPStatusError`.

- [ ] **Step 1: Skriv de fejlende tests** (med `httpx.MockTransport`, fake `sleep` der registrerer pauser, og fake `clock`):
  - `test_sends_user_agent`: Requestens `User-Agent` == `SEC_USER_AGENT`.
  - `test_retries_then_succeeds`: Svarene 503, 503, 200 giver JSON tilbage, og de registrerede backoff-pauser er `[1, 2]`.
  - `test_gives_up_after_three_retries`: Fire gange 503 giver `HTTPStatusError`.
  - `test_rate_limit`: 16 kald med `clock` låst til 0 giver en samlet pausetid ≥ 1.0 s.
  - `test_download_writes_file`: `download` skriver svarets bytes til `dest`.
- [ ] **Step 2:** Kør `.venv/bin/python -m pytest tests/test_sec_client.py -q`. Forventet: FAIL (modulet findes ikke).
- [ ] **Step 3:** Implementér `SecClient`. `download` streamer til en `.part`-fil og omdøber til sidst, så en afbrudt download aldrig ligner en hel fil.
- [ ] **Step 4:** Kør testen. Forventet: `5 passed`.
- [ ] **Step 5:** Commit `feat: SEC client with rate limit and retries`.

### Task 4: Univers og søgeindeks

**Files:**
- Create: `src/stock_engine/universe.py`, `tests/test_universe.py`

**Interfaces:**
- Consumes: `SecClient.get_json`.
- Produces: `@dataclass(frozen=True) Company(ticker: str, name: str, cik: int, exchange: str)`.
  `TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"`.
  `parse_tickers(raw: dict) -> list[Company]` (`raw` = `{"fields": ["cik","name","ticker","exchange"], "data": [[...], ...]}`).
  `search_index(companies: list[Company]) -> list[dict]` → `[{"t": "AAPL", "n": "Apple Inc.", "cik": 320193, "ex": "Nasdaq"}]`, sorteret efter ticker.
  `load_universe(client: SecClient) -> list[Company]`.

- [ ] **Step 1: Skriv de fejlende tests:**
  - `test_keeps_only_nyse_and_nasdaq`: Rækker med `"OTC"`, `"CBOE"` og `None` fjernes.
  - `test_drops_non_common_shares`: `BAC-PL`, `ABC-WT`, `ABC-UN`, `ABC-RT`, `LCIDW`, `ABCDU` og `ABCDR` (5 bogstaver på Nasdaq) fjernes.
  - `test_keeps_share_classes`: `BRK-B`, `GOOG` og `GOOGL` beholdes, også når GOOG og GOOGL har samme CIK.
  - `test_dedupes_ticker`: Står den samme ticker to gange, giver det én `Company`.
  - `test_search_index_shape`: Keys er præcis `{"t", "n", "cik", "ex"}`, og listen er sorteret.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér. Filtreringen er en regex-liste i én konstant `NON_COMMON_PATTERNS` med kommentaren `# shortcut: suffix rules miss some odd listings, replace with an exchange security-type list if one becomes available`.
- [ ] **Step 4:** Kør testen. Forventet: `5 passed`.
- [ ] **Step 5:** Commit `feat: universe and search index from SEC tickers`.

### Task 5: SEC-bulkfiler og selskabsprofil

**Files:**
- Create: `src/stock_engine/fetch_sec.py`, `tests/test_fetch_sec.py`

**Interfaces:**
- Consumes: `SecClient.download`.
- Produces: `COMPANYFACTS_URL`, `SUBMISSIONS_URL` (URL'erne fra Task 2).
  `ensure_bulk(client: SecClient, raw_dir: Path, max_age_hours: float = 20, now: float | None = None) -> tuple[Path, Path]` henter kun filer, der er ældre end `max_age_hours`.
  `read_member(zip_path: Path, cik: int) -> dict | None` læser `f"CIK{cik:010d}.json"`. Mangler filen, gives `None`.
  `company_profile(submissions: dict | None) -> dict` → `{"sic": int | None, "sic_description": str | None, "fiscal_year_end": str | None, "category": str | None}` fra felterne `sic`, `sicDescription`, `fiscalYearEnd` og `category`.

- [ ] **Step 1: Skriv de fejlende tests** (tests bygger en lille zip i `tmp_path`):
  - `test_read_member_found` og `test_read_member_missing_returns_none`.
  - `test_ensure_bulk_skips_fresh_files`: Filer, der er 1 time gamle, giver 0 downloads. Filer, der er 25 timer gamle, giver 2.
  - `test_company_profile_parses_sic`: `{"sic": "3571", ...}` giver `sic == 3571`. Med `None` som input er alle felter `None`.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér med `zipfile.ZipFile` (åbn én gang pr. kald, ingen udpakning af hele filen).
- [ ] **Step 4:** Kør testen. Forventet: `4 passed`.
- [ ] **Step 5:** Commit `feat: SEC bulk files and company profile`.

### Task 6: Regnskabsdata del 1, fakta, perioder og regnskabsår

**Files:**
- Create: `src/stock_engine/metrics/__init__.py`, `src/stock_engine/metrics/financials.py`, `tests/factories.py`, `tests/test_financials_facts.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Fact(start: date | None, end: date, val: float, filed: date)`.
  - `@dataclass(frozen=True) Concept(taxonomy: str, tags: tuple[str, ...], unit: str, kind: Literal["flow", "instant"])`.
  - `CONCEPTS: dict[str, Concept]` med netop disse poster (tags i prioriteret rækkefølge):

    | Post | taxonomy | tags | unit | kind |
    |---|---|---|---|---|
    | revenue | us-gaap | RevenueFromContractWithCustomerExcludingAssessedTax, Revenues, SalesRevenueNet, RevenueFromContractWithCustomerIncludingAssessedTax | USD | flow |
    | gross_profit | us-gaap | GrossProfit | USD | flow |
    | operating_income | us-gaap | OperatingIncomeLoss | USD | flow |
    | net_income | us-gaap | NetIncomeLoss | USD | flow |
    | eps_diluted | us-gaap | EarningsPerShareDiluted | USD/shares | flow |
    | shares_diluted | us-gaap | WeightedAverageNumberOfDilutedSharesOutstanding | shares | flow |
    | operating_cash_flow | us-gaap | NetCashProvidedByUsedInOperatingActivities | USD | flow |
    | capex | us-gaap | PaymentsToAcquirePropertyPlantAndEquipment | USD | flow |
    | dividends_per_share | us-gaap | CommonStockDividendsPerShareDeclared | USD/shares | flow |
    | total_assets | us-gaap | Assets | USD | instant |
    | total_liabilities | us-gaap | Liabilities | USD | instant |
    | stockholders_equity | us-gaap | StockholdersEquity | USD | instant |
    | cash | us-gaap | CashAndCashEquivalentsAtCarryingValue | USD | instant |
    | long_term_debt | us-gaap | LongTermDebtNoncurrent, LongTermDebt | USD | instant |
    | shares_outstanding | dei | EntityCommonStockSharesOutstanding | shares | instant |

  - `extract_facts(companyfacts: dict, item: str) -> list[Fact]`: Inden for ét tag beholdes kun den nyeste `filed` pr. `(start, end)`. På tværs af tags vinder det første tag med data for hver `(start, end)`.
  - `duration_days(f: Fact) -> int`. Konstanterne `QUARTER_DAYS = range(80, 101)` og `ANNUAL_DAYS = range(350, 381)`.
  - `fiscal_label(end: date, fiscal_year_end: str, annual: bool) -> str` → `"FY2024"` eller `"Q1 FY2024"`.
- `tests/factories.py`: `fact(start: str | None, end: str, val: float, filed: str) -> dict` og `companyfacts(items: dict[str, list[dict]], taxonomy: str = "us-gaap", unit: str = "USD") -> dict`, som bygger SEC-formen `{"facts": {taxonomy: {tag: {"units": {unit: [...]}}}}}`.

**Algoritme for `fiscal_label`** (bestemmes ikke af signaturen):
```
candidates = FYE-datoen (MMDD) i årene end.year-1, end.year, end.year+1
fy_end = mindste kandidat >= end - 7 dage        # 52/53-ugers år ender op til ~7 dage fra MMDD
annual -> f"FY{fy_end.year}"
ellers  -> q = 4 - round((fy_end - end).days / 91.3); f"Q{q} FY{fy_end.year}"
```

- [ ] **Step 1: Skriv de fejlende tests:**
  - `test_restated_value_uses_latest_filed`: FY2023 revenue (2022-10-02→2023-09-30) blev indberettet som 400 (filed 2023-11-03) og 405 (filed 2024-11-01). Resultatet er én `Fact` med `val == 405`.
  - `test_first_tag_wins_per_period`: FY2023 under `RevenueFromContract…` = 405 og under `SalesRevenueNet` = 999 giver 405. FY2022 (2021-09-26→2022-10-01) findes kun under `SalesRevenueNet` = 380 og kommer med.
  - `test_instant_fact_has_no_start`: `Assets` uden `start` giver `Fact.start is None`.
  - `test_duration_ranges`: 91 dage ∈ `QUARTER_DAYS`, 98 dage (14-ugers kvartal) ∈ `QUARTER_DAYS`, 182 dage ∉ begge, 364 og 371 ∈ `ANNUAL_DAYS`.
  - `test_fiscal_label`:
    - `(2023-12-30, "0930", False)` → `"Q1 FY2024"`
    - `(2024-03-30, "0930", False)` → `"Q2 FY2024"`
    - `(2024-09-28, "0930", False)` → `"Q4 FY2024"`
    - `(2024-09-28, "0930", True)` → `"FY2024"`
    - `(2024-01-02, "1231", True)` → `"FY2023"`
    - `(2024-03-31, "1231", False)` → `"Q1 FY2024"`
- [ ] **Step 2:** Kør `.venv/bin/python -m pytest tests/test_financials_facts.py -q`. Forventet: FAIL.
- [ ] **Step 3:** Implementér. SEC's dato-strenge parses med `date.fromisoformat`. Tags eller units, der mangler, springes over.
- [ ] **Step 4:** Kør testen. Forventet: `5 passed`.
- [ ] **Step 5:** Commit `feat: XBRL fact extraction and fiscal labels`.

### Task 7: Regnskabsdata del 2, kvartaler, år, TTM og `build_statements`

**Files:**
- Modify: `src/stock_engine/metrics/financials.py`
- Create: `tests/test_financials_statements.py`

**Interfaces:**
- Consumes: alt fra Task 6.
- Produces:
  - `annual_values(facts: list[Fact]) -> dict[date, float]` (perioder i `ANNUAL_DAYS`, nøglen er `end`).
  - `quarterly_values(facts: list[Fact]) -> dict[date, float]` (flowposter, algoritmen nedenfor).
  - `instant_values(facts: list[Fact]) -> dict[date, float]`.
  - `ttm(quarterly: dict[date, float], as_of: date, kind: str) -> float | None`: Flowposter giver summen af de 4 kvartaler, der slutter på eller før `as_of`, men kun hvis der er højst 100 dage mellem hvert kvartal. Ellers `None`. Instant-poster giver den seneste værdi på eller før `as_of`.
  - `build_statements(companyfacts: dict, fiscal_year_end: str) -> dict`:
    ```
    {"annual":    {"end": [iso...], "label": ["FY2015", ...], "<post>": [float|None, ...]},  # højst 11 år, ældste først
     "quarterly": {"end": [...], "label": ["Q1 FY2024", ...], "<post>": [...]},          # højst 12 kvartaler
     "ttm": {"<post>": float|None}, "ttm_prior": {"<post>": float|None},                  # ttm_prior = TTM et år før
     "latest_quarter_end": iso | None}
    ```
    Alle poster fra `CONCEPTS` kommer med, plus `free_cash_flow = operating_cash_flow − capex` (`None`, hvis en af dem mangler).
    Instant-poster i tabellen "annual" og "quarterly" bruger den værdi, hvis `end` ligger højst 7 dage fra periodens `end`.
    Perioderne for "annual" og "quarterly" er foreningen af perioder fra `revenue` og `net_income`.

**Algoritme for `quarterly_values`:**
```
q = {f.end: f.val for f in facts if duration_days(f) in QUARTER_DAYS}
for A in facts med varighed i ANNUAL_DAYS:
    cum = facts med |start - A.start| <= 3 dage og end <= A.end, sorteret efter end     # 3M, 6M, 9M, 12M (YTD i 10-Q)
    for prev, cur i par af ([None] + cum):
        if cur.end not in q and (varighed(cur) - varighed(prev eller 0)) in QUARTER_DAYS:
            q[cur.end] = cur.val - (prev.val hvis prev ellers 0)
    if A.end not in q:
        inside = [v for e, v in q.items() if A.start + 80 dage <= e <= A.end - 80 dage]
        if len(inside) == 3: q[A.end] = A.val - sum(inside)
```
Kommentar i koden: `# shortcut: per-share items (EPS, DPS) are derived by subtraction like flows, slightly off when share count changes within the year`.

- [ ] **Step 1: Skriv de fejlende tests** (fixtures via `tests/factories.py`). "Normal" har FYE `"0930"` og FY2024 = 2023-10-01→2024-09-28:
  - `test_q4_from_annual_minus_three_quarters`: Revenue Q1 = 100 (→2023-12-30), Q2 = 110 (→2024-03-30), Q3 = 120 (→2024-06-29) og FY = 470 giver Q4 (2024-09-28) = 140.
  - `test_quarters_from_ytd_cash_flow`: OCF YTD 3M = 30, 6M = 65, 9M = 105 og 12M = 150 (alle med start 2023-10-01) giver kvartalerne `[30, 35, 40, 45]`.
  - `test_missing_quarter_gives_no_q4_and_no_ttm`: Uden Q2 og uden YTD gælder `2024-09-28 not in quarterly_values(...)`, og `ttm(...) is None`.
  - `test_ttm_flow_and_instant`: TTM for revenue pr. 2024-09-28 == 470. For `cash` med instant-værdierne {2024-06-29: 5, 2024-09-28: 7} er TTM == 7.
  - `test_build_statements_normal`: `annual["label"][-1] == "FY2024"`, `quarterly["label"][-1] == "Q4 FY2024"`, `ttm["revenue"] == 470`, `ttm_prior["revenue"] is None`, og `free_cash_flow` er OCF − capex for FY2024 (150 − 50 = 100).
  - `test_build_statements_bank`: Revenue kun under `Revenues` og ingen `GrossProfit` giver en gross_profit-række med kun `None`, og der kastes ingen fejl.
  - `test_build_statements_loss`: Negativ `net_income` og `eps_diluted` bevares med fortegn.
  - `test_build_statements_caps_lengths`: Med 15 år og 20 kvartaler af data er `len(annual["end"]) == 11` og `len(quarterly["end"]) == 12`.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér funktionerne i `financials.py`.
- [ ] **Step 4:** Kør `.venv/bin/python -m pytest -q`. Forventet: alle tests består.
- [ ] **Step 5:** Commit `feat: quarterly, annual and TTM statements`.

### Task 8: CAGR

**Files:**
- Create: `src/stock_engine/metrics/cagr.py`, `tests/test_cagr.py`

**Interfaces:**
- Consumes: `build_statements(...)["annual"]`.
- Produces:
  - `cagr(start: float | None, end: float | None, years: float) -> float | Literal["n/m"] | None`: `None` når en værdi mangler, `"n/m"` når en af dem er ≤ 0.
  - `HORIZONS = (1, 3, 5, 10)`, `CAGR_ITEMS = ("revenue", "eps_diluted", "free_cash_flow", "dividends_per_share", "book_value_per_share")`.
  - `cagr_table(annual: dict) -> dict[str, dict[str, float | str | None]]` → `{"revenue": {"1": ..., "3": ..., "5": ..., "10": ...}, ...}`. Den seneste årsværdi sammenlignes med værdien `h` pladser tidligere. `book_value_per_share = stockholders_equity / shares_diluted` pr. år.
  - `total_return` tilføjes i Task 10.

- [ ] **Step 1: Skriv de fejlende tests:**
  - `test_cagr_basic`: `cagr(100, 121, 2) == pytest.approx(0.10)`.
  - `test_cagr_not_meaningful`: `cagr(-5, 10, 3) == "n/m"`, og `cagr(10, 0, 3) == "n/m"`.
  - `test_cagr_missing`: `cagr(None, 10, 3) is None`.
  - `test_cagr_table_horizons`: 11 års revenue `[100, 110, ..., 200]` giver `table["revenue"]["10"] == pytest.approx((200/100)**(1/10)-1)`. Med kun 4 år er `"5"` og `"10"` `None`.
  - `test_book_value_per_share`: Equity `[1000, 1100, 1210]` og `shares_diluted` `[10, 10, 10]` giver `book_value_per_share` `"1" == pytest.approx(0.10)` og `"3" is None`.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér.
- [ ] **Step 4:** Kør testen. Forventet: `5 passed`.
- [ ] **Step 5:** Commit `feat: CAGR table`.

### Task 9: Kurs-pipeline med cache (kræver ja fra Task 2, Step 5)

**Files:**
- Create: `src/stock_engine/fetch_prices.py`, `tests/test_fetch_prices.py`

**Interfaces:**
- Produces:
  - `BENCHMARKS = ["SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]`.
  - `FetchFn = Callable[[list[str], date | None], tuple[pd.DataFrame, pd.DataFrame]]`. Den returnerer `(close, adj_close)` i bredt format (DatetimeIndex × tickers). `start=None` betyder 10 år.
  - `yf_fetch: FetchFn`: rigtig implementering med `yf.download(..., auto_adjust=False, group_by="ticker", threads=True, progress=False)`. Den unit-testes ikke.
  - `@dataclass UpdateResult(ok: int, failed: list[str])` med property `failure_ratio: float` (`len(failed) / (ok + len(failed))`, 0 ved tom liste).
  - `update_prices(tickers: list[str], cache_dir: Path, fetch: FetchFn = yf_fetch, batch_size: int = 100) -> UpdateResult`. Den læser og skriver `cache_dir / "close.parquet"` og `cache_dir / "adj_close.parquet"`. Tickers, der ikke er i cachen, hentes med `start=None`. Resten hentes fra den seneste dato i cachen minus 5 dage. Nye rækker overskriver de rækker, der overlapper.
  - `load_prices(cache_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]`.

- [ ] **Step 1: Skriv de fejlende tests** (med en fake `fetch`, der registrerer kald og returnerer små DataFrames):
  - `test_first_run_fetches_full_history`: Tom cache giver kun kald med `start=None`, og parquet-filerne skrives.
  - `test_incremental_run_starts_five_days_back`: Cache til 2026-10-20 giver `start == date(2026, 10, 15)` for kendte tickers og `None` for en ny ticker.
  - `test_overlap_is_overwritten`: Cachens 2026-10-20 = 10, og den nye værdi = 11. Efter kørslen er værdien 11.
  - `test_batches`: 250 tickers med `batch_size=100` giver 3 kald.
  - `test_all_nan_ticker_counts_as_failed`: 10 tickers, hvor 3 kun har NaN, giver `failed` med de 3, `ok == 7` og `failure_ratio == 0.3`.
  - `test_fetch_exception_fails_whole_batch`: Kaster `fetch` en fejl for et batch, ender alle dets tickers i `failed`, og de andre batches fortsætter.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér.
- [ ] **Step 4:** Kør testen. Forventet: `6 passed`.
- [ ] **Step 5:** Kør det rigtigt én gang lokalt for 20 tickers plus `BENCHMARKS` (lille script i en REPL, ikke committet). Notér tiden.
- [ ] **Step 6:** Commit `feat: incremental price cache`.

### Task 10: Kurshistorik, totalafkast og sektor-ETF

**Files:**
- Create: `src/stock_engine/metrics/price_history.py`, `src/stock_engine/sectors.py`, `tests/test_price_history.py`, `tests/test_sectors.py`

**Interfaces:**
- Produces:
  - `downsample(s: pd.Series, today: date) -> pd.Series`: daglige punkter de seneste 730 dage, ellers den sidste handelsdag pr. uge. NaN fjernes.
  - `price_summary(close: pd.Series, shares_outstanding: float | None) -> dict | None` → `{"last": float, "date": iso, "change_pct": float | None, "market_cap": float | None}`. Uden kurser gives `None`. Kommentar: `# shortcut: market cap uses this class's share count only, multi-class companies (GOOG/GOOGL) are understated`.
  - `total_return_cagr(adj_close: pd.Series, years: int) -> float | Literal["n/m"] | None`: Den sidste kurs sammenlignes med den seneste kurs på eller før `sidste dato − years`. Findes den ikke, gives `None`. Bruger `cagr()` fra Task 8.
  - `chart_series(adj_close: pd.Series, today: date) -> dict | None` → `{"dates": [iso...], "adj_close": [float...]}` (efter `downsample`, rundet til 4 betydende cifre).
  - `sector_etf(sic: int | None) -> str | None`. Intervallerne tjekkes i denne rækkefølge, første match vinder, ellers `None`:
    1. XLE: 1300–1399, 2900–2999
    2. XLV: 2830–2836, 3841–3851, 8000–8099
    3. XLK: 3570–3579, 3600–3699, 7370–7379
    4. XLRE: 6500–6553, 6798
    5. XLB: 1000–1499, 2600–2699, 2800–2899, 3300–3399
    6. XLY: 3710–3716, 5200–5999, 7000–7099
    7. XLI: 1500–1799, 3400–3569, 3580–3599, 3720–3799, 4000–4799, 5000–5199
    8. XLC: 4800–4899, 7800–7999
    9. XLU: 4900–4999
    10. XLF: 6000–6799
    11. XLP: 0100–0999, 2000–2199

    Kommentar: `# shortcut: coarse SIC ranges, upgrade to GICS if a free mapping turns up`.

- [ ] **Step 1: Skriv de fejlende tests:**
  - `test_downsample_daily_recent_weekly_old`: 3 års handelsdage giver kun daglige punkter efter `today − 730 d` og højst ét punkt pr. kalenderuge før.
  - `test_price_summary`: Lukkekurserne `[100, 105]` og 1.000 aktier giver `last == 105`, `change_pct == pytest.approx(0.05)` og `market_cap == 105_000`. En tom serie giver `None`.
  - `test_total_return_cagr`: Fra 100 til 121 over præcis 2 år giver `pytest.approx(0.10)` for `years=2` og `None` for `years=5`.
  - `test_sector_etf`: 3571 → XLK, 2834 → XLV, 6022 → XLF, 6798 → XLRE, 1311 → XLE, 9999 → None, None → None.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér. Udvid `cagr_table` med en valgfri parameter `adj_close: pd.Series | None = None`, som tilføjer rækken `total_return`.
- [ ] **Step 4:** Kør `.venv/bin/python -m pytest -q`. Forventet: alle tests består.
- [ ] **Step 5:** Commit `feat: price history, total return and sector ETF`.

### Task 11: Byg JSON til siden

**Files:**
- Create: `src/stock_engine/build.py`, `tests/test_build.py`

**Interfaces:**
- Consumes: `load_universe`, `search_index`, `ensure_bulk`, `read_member`, `company_profile`, `build_statements`, `cagr_table`, `update_prices`, `load_prices`, `BENCHMARKS`, `price_summary`, `chart_series`, `sector_etf`.
- Produces:
  - `build_ticker(company: Company, companyfacts: dict | None, submissions: dict | None, close: pd.Series | None, adj_close: pd.Series | None, today: date) -> dict` med netop dette skema (felterne er `null`, når data mangler):
    ```
    {"ticker", "name", "cik", "exchange", "sic", "sic_description", "fiscal_year_end", "sector_etf",
     "updated": iso, "price": price_summary | null, "chart": chart_series | null,
     "statements": build_statements | null, "cagr": cagr_table | null}
    ```
  - `write_site(out_dir: Path, records: list[dict], search: list[dict], benchmarks: dict, meta: dict) -> None` skriver `t/<TICKER>.json`, `search.json`, `benchmarks.json` (`{"SPY": chart_series, ...}`) og `meta.json`, alle med kompakt JSON (`separators=(",", ":")`).
  - `meta` = `{"updated": iso, "tickers": int, "price_failed": [..], "build_failed": {ticker: fejltekst}, "oversize": [tickers > 80 KB]}`.
  - `main(argv: list[str] | None = None, client: SecClient | None = None, fetch: FetchFn = yf_fetch, today: date | None = None) -> int`. CLI: `python -m stock_engine.build [--tickers AAPL,MSFT]`. Med `--tickers` bygges kun dem (til udvikling), men `search.json` dækker altid hele universet. Exit-kode 1 og ingen skrivning, hvis `failure_ratio > 0.2`. En fejl for én ticker logges i `build_failed`, og en eksisterende fil for den ticker bliver liggende.

- [ ] **Step 1: Skriv de fejlende tests** (fake `SecClient` via `MockTransport`, der serverer en lille ticker-JSON og små zip-filer, plus en fake `fetch`):
  - `test_build_ticker_normal`: Alle top-level keys findes, `statements["ttm"]["revenue"] == 470`, og `sector_etf == "XLK"` for SIC 3571.
  - `test_build_ticker_without_facts`: `companyfacts=None` giver `statements is None` og `cagr is None`, mens `price` stadig er udfyldt.
  - `test_record_under_80kb`: Det fulde normale record med 10 års kurser gemt med `separators=(",", ":")` fylder under 80 KB.
  - `test_main_writes_site`: `main(["--tickers", "ACME"], ...)` giver 0, og `site/data/t/ACME.json`, `search.json`, `benchmarks.json` og `meta.json` findes.
  - `test_main_aborts_on_price_failures`: Når 3 ud af 10 tickers kun har NaN, er exit-koden 1, og der skrives ingen filer.
  - `test_one_ticker_error_does_not_stop_build`: En ticker med ødelagt companyfacts kommer i `meta["build_failed"]`, og de andre skrives.
  - `out_dir` skal kunne overstyres i tests: `main` læser `SITE_DATA_DIR` og `CACHE_DIR` fra `config`, og tests bruger `monkeypatch` med `tmp_path`.
- [ ] **Step 2:** Kør testen. Forventet: FAIL.
- [ ] **Step 3:** Implementér. Læs hver zip én gang pr. kørsel (`zipfile.ZipFile` åbnes i `main` og gives videre) i stedet for at åbne den pr. ticker.
- [ ] **Step 4:** Kør `.venv/bin/python -m pytest -q`. Forventet: alle tests består.
- [ ] **Step 5:** Rigtig kørsel: `.venv/bin/python -m stock_engine.build --tickers AAPL,MSFT,JPM,BRK-B,RIVN`. Tjek, at `AAPL.json`'s seneste FY-omsætning stemmer med AAPL's 10-K, og notér filstørrelser.
- [ ] **Step 6:** Commit `feat: build site JSON`.

### Task 12: `lib.js`, rene funktioner til siden

**Files:**
- Create: `site/lib.js`, `tests/js/lib.test.js`

**Interfaces:**
- Produces (eksporteret som i `macro_dashboard/lib.js`):
  - `normalizeQuery(q: string) -> string`: trim, store bogstaver, `.` og `/` → `-` (`"brk.b"` → `"BRK-B"`).
  - `searchTickers(index: {t, n, cik, ex}[], query: string, limit = 8) -> {t, n, cik, ex}[]`. Rangorden: 1) præcis ticker, 2) ticker der starter med query, 3) et ord i navnet der starter med query (ingen forskel på store og små bogstaver), 4) query et sted i navnet. Ved lighed sorteres efter kortest ticker og derefter alfabetisk. Tom query giver `[]`.
  - `parseRoute(hash: string) -> {view: "home"} | {view: "ticker", ticker: string}`: `""`, `"#"` og `"#/"` giver home. `"#/brk.b"` giver `{view: "ticker", ticker: "BRK-B"}`.
  - `formatMoney(v: number | null) -> string`: `1.234e9` → `"$1.23B"`, `-1.2e9` → `"-$1.20B"`, `5.6e6` → `"$5.60M"`, `950` → `"$950"`, `null` → `"—"`.
  - `formatPct(v: number | string | null) -> string`: `0.1234` → `"12.3%"`, `"n/m"` → `"n/m"`, `null` → `"—"`.
  - `margin(numer: number | null, denom: number | null) -> number | null`: `null`, når en af dem mangler, eller når `denom <= 0`.
  - `yoy(cur: number | null, prev: number | null) -> number | null`: `null`, når `prev` mangler eller `prev <= 0`.
  - `RANGES = ["1M", "6M", "YTD", "1Y", "3Y", "5Y", "10Y"]` og `sliceRange(dates: string[], values: number[], range: string, today: string) -> {dates, values}`.
  - `rebase(values: number[]) -> number[]`: Første værdi bliver 100.

- [ ] **Step 1: Skriv de fejlende tests** for hver funktion med værdierne ovenfor. Til `searchTickers` bruges indekset `[AAPL "Apple Inc.", APP "AppLovin Corp", BRK-B "Berkshire Hathaway Inc.", GOOG "Alphabet Inc.", GOOGL "Alphabet Inc.", MAPL "Maple Leaf"]`, og testene er:
  - `"app"` → første resultat er `APP`, og `AAPL` er ikke med før `APP`.
  - `"apple"` → `AAPL` står først.
  - `"alpha"` → `GOOG` og derefter `GOOGL`.
  - `"brk.b"` → `BRK-B`.
  - `""` → `[]`.
  - `sliceRange` med `"YTD"` og `today = "2026-10-22"` giver kun datoer fra 2026-01-01.
- [ ] **Step 2:** Kør `node --test tests/js/`. Forventet: FAIL.
- [ ] **Step 3:** Implementér.
- [ ] **Step 4:** Kør `node --test tests/js/`. Forventet: alle tests består.
- [ ] **Step 5:** Commit `feat: pure page helpers with tests`.

### Task 13: Siden, søgning og aktiesidens sektioner

**Files:**
- Create: `site/index.html`, `site/app.js`, `site/style.css`

**Interfaces:**
- Consumes: `lib.js` (Task 12) og JSON-skemaet fra Task 11.
- Produces: Den side, der udgives i Task 14.

- [ ] **Step 1:** `index.html`: Indlæser Chart.js 4.5.1 og date-fns-adapteren 3.0.0 (de samme URL'er som macro_dashboard), og derefter `lib.js` og `app.js`. Siden har header med søgefelt, `<main id="view">` og en footer med teksten fra Global Constraints. Footerens dato kommer fra `meta.json`.
- [ ] **Step 2:** `app.js`, søgning: `search.json` hentes én gang. Cmd/Ctrl+K fokuserer søgefeltet. ↑/↓/Enter vælger, og Esc lukker. Et valg sætter `location.hash = "#/TICKER"`.
- [ ] **Step 3:** `app.js`, routing på `hashchange` via `parseRoute`. Home viser søgefeltet og en kort introduktion. Ticker-visningen henter `data/t/<TICKER>.json`. Ved 404 eller en ticker, der ikke er i `search.json`, vises "Ticker not found" med søgefeltet.
- [ ] **Step 4:** Ticker-visningen renderer følgende. Hver sektion viser "No data", hvis feltet er `null`, og fejl i én sektion fanges, så de andre stadig vises.
  - **Header:** navn, ticker, børs, `sic_description`, kurs, ændring og markedsværdi.
  - **Kursgraf:** `RANGES`-knapper (standard 1Y), afkrydsning af "S&P 500 (SPY)" og sektor-ETF'en (fra `benchmarks.json`, alle rebased) og y-akse-label "Total return, rebased to 100".
  - **Nøgletal:** tre kolonner, nemlig seneste kvartal, TTM og seneste FY. Rækkerne er revenue, gross/operating/net margin, diluted EPS og FCF. YoY bruger kvartalet 4 pladser før, `ttm_prior` og året før.
  - **Regnskabshistorik:** skift mellem Annual og Quarterly samt en tabel for hvert af Income, Balance og Cash flow. Over tabellen er der et søjlediagram med revenue og net income.
  - **CAGR:** tabel med `CAGR_ITEMS` + total return × 1/3/5/10 år, formateret med `formatPct`.
- [ ] **Step 5:** `style.css`: lyst og mørkt tema via `prefers-color-scheme` og ingen vandret scroll ved 375 px (tabeller scroller inde i deres egen boks).
- [ ] **Step 6: Lokal preview. Spørg Erik først**, fordi `~/Documents/Code/.claude/launch.json` ligger uden for projektet. Tilføj en konfiguration `stock_engine`, der kører `python3 -m http.server 8124 --directory .../stock_engine/site`.
- [ ] **Step 7: Browsertjek** på data fra Task 11, Step 5, ved 1280 og 375 px:
  - **AAPL:** alle sektioner, og graf-ranges skifter.
  - **JPM:** gross margin "—", ingen fejl i konsollen.
  - **RIVN:** negative tal har fortegn, og EPS-CAGR viser "n/m".
  - **BRK-B:** "brk.b" i søgningen finder den.
  - **`#/ZZZZ`:** "Ticker not found".
  - Konsollen er uden fejl i alle tilfælde.
- [ ] **Step 8:** Commit `feat: search and company page`.

### Task 14: Første udgivelse via GitHub Actions og Pages

**Files:**
- Create: `.github/workflows/build.yml`
- Modify: `CLAUDE.md` (kør, udgiv, URL), `../STATUS.md` (ny række for stock_engine; **spørg Erik**, fordi filen ligger uden for projektet)

- [ ] **Step 1:** `build.yml`: `on: workflow_dispatch`, ubuntu-latest, Python 3.11, `pip install -r requirements.txt`.
  - `actions/cache` på `data/cache` og `site/data/t` med key `prices-${{ github.run_id }}` og `restore-keys: prices-`.
  - Derefter tests (`pytest -q` og `node --test tests/js/`) og `python -m stock_engine.build`.
  - Til sidst `actions/upload-pages-artifact` (path `site`) og `actions/deploy-pages` med `permissions: pages: write, id-token: write`.
  - Den daglige plan kommer først i M8.
- [ ] **Step 2: STOP, spørg Erik:** Må vi pushe, og vil du sætte Pages til "GitHub Actions" under repoets Settings → Pages? (Det er en indstilling på din konto, så den sætter du selv.)
- [ ] **Step 3:** Kør workflowet manuelt. Notér tid, antal tickers, `price_failed`, `build_failed`, `oversize` og den samlede størrelse af `site/` fra loggen.
- [ ] **Step 4:** Browsertjek af den udgivne URL med samme liste som Task 13, Step 7.
- [ ] **Step 5:** Opdatér `CLAUDE.md` med URL, kør- og udgivelseskommandoer og de målte tal. Commit `ci: build and deploy to GitHub Pages` og push (med det ja, du fik i Step 2).

---

## Efter M3

Lav en ny plan for M4–M5 (kalender, værdiansættelse, kvalitet) ud fra de målte filstørrelser, køretider og `meta.json`.
`portfolio.json` forbliver `"hidden": true` indtil M8.
