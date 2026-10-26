# CLAUDE.md – Stock Engine

## Hvad projektet er

En statisk hjemmeside, hvor man søger på navn eller ticker for en amerikansk aktie og får en side med kalender,
regnskabshistorik, nøgletal, CAGR, værdiansættelse, kvalitet, ejerskab, peers, filings og en risikoscore fra 0 til 100.
Siden bygges af en Python-pipeline fra SEC EDGAR, yfinance og Finnhub og hostes som ren statisk side på GitHub Pages.

## Kør

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt     # pakker + projektet selv (-e .)
cp .env.example .env                          # FINNHUB_API_KEY bruges først fra M4
```

Udfyld `SEC_CONTACT_EMAIL` i `.env` (SEC kræver en rigtig kontaktadresse); i GitHub som secret `SEC_CONTACT_EMAIL`.

## Test

```bash
.venv/bin/python -m pytest -q
node --test tests/js/
```

Tests må ikke bruge netværk. Hentefunktioner tager en `transport` eller en `fetch`-funktion, som tests erstatter.

## Mappestruktur

```
stock_engine/
  src/stock_engine/
    universe.py        # SEC-tickerliste -> univers + search.json
    fetch_sec.py       # companyfacts.zip, submissions.zip, Form 4
    fetch_prices.py    # yfinance i batches, inkrementelt mod parquet-cache
    fetch_finnhub.py   # kalender + roterende anbefalinger/surprises
    metrics/
      financials.py    # ensretning af XBRL-poster, Q4 = FY − Q1..Q3, TTM
      cagr.py
      valuation.py     # multipler, percentil mod egen historik, reverse DCF
      quality.py       # ROIC, Piotroski F, Altman Z, Beneish M
      calendar.py      # kommende begivenheder + beregnede frister
      ownership.py     # insiderhandler, aktieantal, tilbagekøb
      peers.py         # samme SIC-kode, nærmeste markedsværdi
      risk.py          # faktorer -> percentiler -> grupper -> 0..100
    build.py           # skriver site/data/
  site/
    index.html, app.js, style.css   # Chart.js fra CDN
    data/                           # genereres, committes aldrig
  tests/               # pytest + node --test
  .github/workflows/daily.yml
```

`data/`, `site/data/` og `.env` står i `.gitignore` og committes aldrig.

## Links

- Spec: `docs/superpowers/specs/2026-10-22-stock-engine-design.md`
- Plan: `docs/superpowers/plans/2026-10-22-stock-engine-m0-m3.md`
