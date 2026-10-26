# M0-spike: yfinance og SEC bulk i stor skala

Målt lokalt (Eriks Mac) den 26. oktober 2026. Koden i `spike/` er engangskode. Rå output ligger i `spike/out/` (ikke committet).

## Kilder

- **Ønsket ticker-univers:** SEC `https://www.sec.gov/files/company_tickers_exchange.json`, filtreret til NYSE + Nasdaq.
- **SEC svarede HTTP 403** (se nedenfor). Spike-scriptet faldt derfor tilbage til Nasdaqs egen symbolliste (`nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt` + `otherlisted.txt`; uden ETF og test-papirer, uden symboler med `$` eller `.`). Universet er alle Nasdaq-noterede symboler (`nasdaqlisted.txt` har ingen børskolonne, så der filtreres ikke på børs) plus kun NYSE-rækkerne fra `otherlisted.txt`.
- **Kurser:** `yf.download(batch, period="10y", auto_adjust=False, group_by="ticker", threads=True)` i batches á 100, 1,5 s pause mellem batches.

## SEC: 403 (vigtigt fund for Task 3-5)

- Forespørgslen sender `User-Agent: Stock Engine 222303744+SoLl1XZ@users.noreply.github.com` (= `stock_engine.config.SEC_USER_AGENT`) og `Accept-Encoding: gzip, deflate`. Verificeret på `r.request.headers`.
- Svar: `403`, `server: AkamaiGHost`, HTML-side med titlen **"SEC.gov | Request Rate Threshold Exceeded"** ("Automated access ... must comply with ... Fair Access guidelines", Reference ID `0.874bc717...`).
- **403 fra SEC.** SEC's svarside siger "Request Rate Threshold Exceeded", men årsagen er ikke fastslået (se nedenfor). Lokalt gælder 403 hele SEC: også `data.sec.gov/submissions/CIK0000320193.json`, `.../companyfacts.zip` og `www.sec.gov/robots.txt` svarer 403.
- Jeg forsøgte efterfølgende med 1 forespørgsel hver 1-2,5 min i ca. 25 min (i alt ~10 enkeltforespørgsler): stadig 403. Ingen omgåelse forsøgt (ingen anden UA, ingen proxy).
- Årsagen er ikke fastslået. Mulige forklaringer: (a) tidligere spike-kørsler fra den døde session ramte grænsen (ukendt hvor mange kald, 12:32-13:08), (b) IP'en er delt eller allerede markeret, (c) blokeringen varer længere end 25 min. Kun SEC kan svare sikkert.
- **Konsekvens:** SEC-bulk (`companyfacts.zip`, `submissions.zip`) er **ikke målt**. Tallene herunder er tomme. Tasks 3-5 bygger på SEC og kan ikke verificeres mod rigtige data, før adgangen er tilbage (blokeringen afventes; ingen omvej forsøges).

## Kurser (yfinance), nasdaqtrader-listen

| Mål | Værdi |
|---|---|
| Tickers i listen | 6.640 |
| Tickers med mindst 1 kurs (bulk-kørsel) | 2.129 |
| **Succesrate, bulk** | **32,1 %** |
| Samlet tid | 781 s (13,0 min) |
| Gennemsnit pr. batch | 10,2 s (67 batches) |
| Batch 1-10 | 992/1000 ok (99,2 %), ca. 7,8 s pr. batch |
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
- Konklusion: resultatet **tyder på**, at fejlene i den lokale bulk-kørsel ikke skyldes manglende data (4.951 linjer med `curl: (7)` forbindelse afvist). Samme kode på Actions-runneren gav ingen kollaps (se nedenfor), så årsagen ser ud til at ligge lokalt frem for i yfinance ved denne skala. Det er ikke bevist: stikprøven er kun 200 sekventielle hentninger (ikke parallelle), og den kørte ca. 2 timer efter bulk-kørslen, så et midlertidigt lokalt eller Yahoo-problem kan ikke udelukkes. Det er uverificeret, hvad "possibly delisted" betyder her: yfinance skriver teksten også for rigtigt manglende data, og jeg har ikke dokumenteret, at den også skrives ved begrænsning.
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

## Actions-runner (26. oktober 2026)

- **Kørsel:** workflow `.github/workflows/spike.yml`, run https://github.com/SoLl1XZ/Stock_engine/actions/runs/40350599806, `ubuntu-latest`. Samme scripts, uændrede.
- **Tickers:** SEC svarede 403 også på runneren, så den samme nasdaqtrader-fallback-liste blev brugt (6.640 symboler).
- **Kurser (yfinance):** 6.639 / 6.640 fik kurs (99,98 %) på 656 s i alt, ca. 8,3 s pr. batch á 100 (67 batches). Ingen batch kollapsede. Den ene fejl var ABOS med `OperationalError('database is locked')` fra yfinances lokale cache, ikke fra Yahoo.
- **Sammenligning:** Det lokale kollaps (32,1 %) ser derfor ud til at hænge sammen med den lokale maskine/IP og ikke med yfinance ved denne skala.
- **SEC bulk:** begge zips svarede 403 efter 0,1 s også fra runneren. Zip-størrelser og tider er stadig ikke målt.
- **SEC-årsag (hypotese, IKKE verificeret):** SEC's 403-side (hentet én gang lokalt) siger kun, at automatisk adgang skal overholde SEC.govs Privacy and Security Policy, og henviser til www.sec.gov/developer (Fair Access). Sidens titel er "Request Rate Threshold Exceeded". Fordi en frisk runner-IP også fik 403 ved de allerførste forespørgsler, er den sandsynlige årsag User-Agent'en (vores noreply-adresse er muligvis ikke accepteret som kontaktadresse), ikke request-raten. Hypotesen er ikke testet.

## Beslutning: afventer Erik

- **Kurser:** kriteriet (≥ 95 % på runneren) er opfyldt (99,98 %). Forbehold: listen indeholder warrants, units og rights, så det er ikke et rent almindelige-aktier-univers. Anbefaling: fortsæt med yfinance (Task 9). Beslutning: afventer Erik.
- **SEC:** blokeret både lokalt og på runneren; skal løses før Task 11's rigtige kørsel. Næste skridt afventer Erik (fx en User-Agent med en rigtig kontaktadresse via miljøvariabel, ikke i koden).
