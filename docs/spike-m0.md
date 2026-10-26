# M0-spike: yfinance og SEC bulk i stor skala

Målt lokalt (Eriks Mac, IP 37.96.x.x) den 26. oktober 2026. Koden i `spike/` er engangskode. Rå output ligger i `spike/out/` (ikke committet).

## Kilder

- **Ønsket ticker-univers:** SEC `https://www.sec.gov/files/company_tickers_exchange.json`, filtreret til NYSE + Nasdaq.
- **SEC svarede HTTP 403** (se nedenfor). Spike-scriptet faldt derfor tilbage til Nasdaqs egen symbolliste (`nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt` + `otherlisted.txt`, kun NYSE-rækker, uden ETF og test-papirer, uden symboler med `$` eller `.`).
- **Kurser:** `yf.download(batch, period="10y", auto_adjust=False, group_by="ticker", threads=True)` i batches á 100, 1,5 s pause mellem batches.

## SEC: 403 (vigtigt fund for Task 3-5)

- Forespørgslen sender `User-Agent: Stock Engine 222303744+SoLl1XZ@users.noreply.github.com` (= `stock_engine.config.SEC_USER_AGENT`) og `Accept-Encoding: gzip, deflate`. Verificeret på `r.request.headers`.
- Svar: `403`, `server: AkamaiGHost`, HTML-side med titlen **"SEC.gov | Request Rate Threshold Exceeded"** ("Automated access ... must comply with ... Fair Access guidelines", Reference ID `0.874bc717...`).
- Det er altså en **rate-/adgangsblokering af vores IP hos SEC**, ikke en manglende header. Blokeringen gælder hele SEC: også `data.sec.gov/submissions/CIK0000320193.json`, `.../companyfacts.zip` og `www.sec.gov/robots.txt` svarer 403.
- Jeg forsøgte efterfølgende med 1 forespørgsel hver 1-2,5 min i ca. 25 min (i alt ~10 enkeltforespørgsler): stadig 403. Ingen omgåelse forsøgt (ingen anden UA, ingen proxy).
- Årsagen er ikke fastslået. Mulige forklaringer: (a) tidligere spike-kørsler fra den døde session ramte grænsen (ukendt hvor mange kald, 12:32-13:08), (b) IP'en er delt eller allerede markeret, (c) blokeringen varer længere end 25 min. Kun SEC kan svare sikkert.
- **Konsekvens:** SEC-bulk (`companyfacts.zip`, `submissions.zip`) er **ikke målt**. Tallene herunder er tomme. Tasks 3-5 bygger på SEC og kan ikke verificeres mod rigtige data, før adgangen er tilbage (prøv igen senere/fra anden forbindelse, fx Actions-runneren).

## Kurser (yfinance), nasdaqtrader-listen

| Mål | Værdi |
|---|---|
| Tickers i listen | 6.640 |
| Tickers med mindst 1 kurs (bulk-kørsel) | 2.129 |
| **Succesrate, bulk** | **32,1 %** |
| Samlet tid | 781 s (13,0 min) |
| Gennemsnit pr. batch | 10,2 s (67 batches) |
| Batch 1-10 | 992/1000 ok (99,2 %), ca. 7,5 s pr. batch |
| Batch 11-67 | 1.137/5.640 ok (20,2 %), batch 12-16: 0/500 |

Mønstret er skarpt: de første ~1.000 tickers går fint, derefter bryder det sammen. Se retry-forsøget nedenfor.

### Fejltyper (fra `spike/out/prices.stdout`, antal fejllinjer fra yfinance)

| Fejl | Antal |
|---|---|
| `curl: (7) Failed to connect to query2.finance.yahoo.com:443` (forbindelsen afvist) | 4.951 |
| `possibly delisted; no price data found (period=10y)` | 4.567 |
| `curl: (28)` timeout | 22 |
| `curl: (35)` TLS-fejl | 1 |
| `OperationalError('database is locked')` (yfinances lokale cache, parallelle tråde) | 1 |

Tallene overlapper (yfinance logger flere linjer pr. ticker), og i alt fejlede 4.511 tickers. Bemærk: `shared._ERRORS` var tom i alle batches (`errors=0`, `exc=None`), så scriptets egen fejltælling i `prices.json` er tom. Fejlene findes kun i stdout. Det er en svaghed i spike-koden, ikke et mål for kvaliteten.

### Retry-forsøg (`spike/retry_sample.py`)

- 200 tilfældige af de 4.511 fejlede tickers, hentet **én ad gangen** (`threads=False`, 0,3 s pause).
- **Genfundet: 200/200 (100 %)** på 142 s (0,7 s pr. ticker).
- Konklusion: fejlene i bulk-kørslen er **ikke manglende data**, men Yahoo, der afviser/begrænser parallelle forespørgsler (curl 7 = forbindelse afvist, plus "possibly delisted", som yfinance også skriver ved begrænsning). Ud fra stikprøven er den reelle succesrate tæt på 100 % af de tickers, der faktisk har kurser, men det er kun målt på 200 tickers.
- Hele universet sekventielt: 6.640 x 0,7 s ≈ 78 min. Det skal tages med i beslutningen om kørselstid i Actions.

### Universet er forurenet

Nasdaqtrader-listen indeholder papirer, der ikke er almindelige aktier: mindst 476 af de fejlede er 5-bogstavs symboler, der slutter på W/R/U (warrants, rights, units, fx `BNAIW`, `BPACR`, `BSBR`). Succesraten på "almindelige aktier" kan derfor ikke opgøres rigtigt uden SEC-filen. Den kan **ikke beregnes på SEC-universet**, og antal SEC-tickers, der ikke er i nasdaqtrader-listen, er **ukendt**, fordi SEC-filen ikke kunne hentes.

## SEC bulk-zips

| Mål | companyfacts.zip | submissions.zip |
|---|---|---|
| HTTP-status | 403 (0,2 s) | 403 (0,2 s) |
| Størrelse (MB) | ikke målt | ikke målt |
| Download-tid | ikke målt | ikke målt |
| Læsetid `CIK0000320193.json` fra zip | ikke målt | ikke målt |
| Udpakket størrelse (infolist) | ikke målt | ikke målt |

`data/raw/` er tom. `spike/sec_bulk.py` er uændret og kan køres igen, når SEC-adgangen er tilbage.

## Actions-runner (afventer Eriks ok)

Ikke målt. Kræver et offentligt GitHub-repo, `spike.yml` og et push, og det må ikke ske uden Eriks ja (Task 2, trin 4). Runneren er også den oplagte måde at teste SEC-adgangen på fra en anden IP.

## Beslutning: afventer Erik

Anbefaling (ét udsagn): Lokalt ligger bulk-succesraten på 32 % og dermed langt under 95 %-kravet, men retry-stikprøven (200/200) peger på throttling, ikke dårlig datadækning. Mål derfor på Actions-runneren med **lavere parallelitet** (fx `threads=False` eller små batches) før valget af kilde, og vent med Task 9, til det tal er kendt.
