# Stock Engine – design

> **Dato:** 2026-10-22 · **Status:** Til review hos Erik · **Sti:** `Projects/stock_engine/`

## 1. Formål og beslutninger

En statisk hjemmeside, hvor man søger på navn eller ticker for en amerikansk aktie og får en side med kalender,
regnskabshistorik, nøgletal, CAGR, værdiansættelse, kvalitet, ejerskab, peers, filings og en risikoscore fra 0 til 100.

| Beslutning | Valg (2026-10-22) |
|---|---|
| Formål | Læring og jobsamtale-projekt. Gratis kilder med kildeangivelse er fine. |
| Hosting | Kun statisk side på GitHub Pages. Ingen server. |
| Univers | Alle almindelige aktier på NYSE og Nasdaq (ca. 4.000–6.000). |
| Datakilder | SEC EDGAR (nøglefri), `yfinance`, Finnhub free (nøgle i `.env` og GitHub Secrets). |
| Sprog | Hele UI'et på engelsk. Dokumentation til Erik på dansk. |
| Features | Alle foreslåede features er i scope (se afsnit 6). Bygges i milepæle (afsnit 9). |
| Risikoscore | Percentil mod universet med synlige vægte, så mange faktorer som muligt, kalibreres senere (M9). |
| Uden for scope | Aktier uden for USA (næste udvidelse), realtidskurser, brugerkonti. |

## 2. Datakilder

| Kilde | Hvad | Hvordan | Grænser |
|---|---|---|---|
| SEC `company_tickers_exchange.json` | Univers: ticker, navn, CIK, børs | 1 kald | — |
| SEC `companyfacts.zip` (bulk) | Alle XBRL-regnskabstal | 1 download pr. kørsel | Stor fil (~1 GB pakket ud, måles i M0) |
| SEC `submissions.zip` (bulk) | Filings-liste, SIC-kode, regnskabsår, indberetningskategori | 1 download | — |
| SEC Form 4 | Insiderhandler | Pr. selskab | 10 kald/s, `User-Agent` med kontaktadresse er påkrævet |
| `yfinance` | Daglige kurser (10 år), udbytter, short interest, kursmål | Batches af 100 tickers | Uofficiel. Risiko for blokering (testes i M0) |
| Finnhub free | Earnings-kalender (alle selskaber i ét kald), anbefalinger, earnings surprises | Kalender dagligt. Resten roteres med 1/7 af universet pr. dag | 60 kald/min |

Hvis M0 viser, at `yfinance` ikke holder i denne skala, skal kursdatakilden vælges om, før M2 begynder. Det er et
beslutningspunkt for Erik.

## 3. Arkitektur

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

**Dataflow:** univers → hent (SEC, kurser, Finnhub) → beregn pr. ticker → beregn percentiler på tværs af universet →
skriv JSON → udgiv `site/` til Pages.

**Output:**
- `site/data/search.json`: `[{t, n, cik, ex}]` til søgning i browseren.
- `site/data/t/<TICKER>.json`: alt til én aktieside. Mål: højst 80 KB pr. fil. Kurser gemmes med daglige punkter for
  de seneste 2 år og ugentlige derfra.
- `site/data/meta.json`: tidsstempel pr. kilde, antal tickers, fejl og dækning.

**Kørsel:** GitHub Actions på hverdage kl. 22:30 UTC. Parquet-kurserne og den seneste gode JSON pr. ticker gemmes i
`actions/cache`. `site/` udgives med `upload-pages-artifact` og `deploy-pages`. Data committes ikke, så repoet
forbliver lille. Pages' grænse er 1 GB, og forventet størrelse er 300–500 MB.

## 4. Regnskabsdata

- **Ensretning:** Hver standardpost (fx `revenue`) har en ordnet liste af XBRL-tags. Det første tag med data vinder
  for hver periode. Listen ligger i én tabel i `financials.py`, så nye tags kan tilføjes ét sted.
- **Perioder:** Kvartaler udledes af `frame`/`fp`. Q4 = helår − Q1 − Q2 − Q3 for flowposter (resultat og
  pengestrømme). Balanceposter tages direkte.
- **TTM:** summen af de seneste 4 kvartaler for flowposter og den seneste værdi for balanceposter.
- **CAGR:** `(slut / start) ** (1 / år) − 1`. Ikke defineret, hvis start eller slut er ≤ 0. Så vises "n/m" (not
  meaningful) i stedet for et tal.

## 5. Risikoscore

**Metode:** For hver faktor beregnes aktiens percentil blandt alle aktier med data (0 = laveste risiko). Gruppens score
er gennemsnittet af dens faktorer. Den samlede score er det vægtede gennemsnit af grupperne og går fra 0 til 100, hvor
100 er højest risiko.

| Gruppe | Vægt | Faktorer |
|---|---|---|
| Markedsrisiko | 20 % | Volatilitet 1 år, downside-volatilitet, beta mod SPY, max drawdown 5 år, afstand til 52-ugers top, CVaR 95 %, idiosynkratisk volatilitet |
| Likviditet og størrelse | 10 % | Markedsværdi, gns. daglig omsætning i $, short interest i % af free float, days to cover |
| Finansiel styrke | 20 % | Nettogæld/EBITDA, rentedækning, current ratio, Altman Z, cash runway |
| Indtjeningskvalitet | 15 % | Udsving i omsætningsvækst, underskudsår ud af 10, Piotroski F, accruals, FCF/nettoresultat, Beneish M, stabilitet i bruttomargin |
| Udvanding og governance | 10 % | Vækst i aktieantal 3 år, aktiebaseret løn/omsætning, insiders' nettosalg 6 mdr., regnskabsomgørelser (8-K item 4.02, 5 år) |
| Værdiansættelse | 10 % | P/E, EV/EBITDA og P/FCF som percentil af egen 10-års historik, implicit vækst i reverse DCF minus historisk vækst |
| Vækstudsigt | 10 % | Omsætnings-CAGR 3/5 år, accelererende vækst, analytikeranbefalinger, earnings surprises (4 kvt.), upside til kursmål. Høj værdi giver lavere risiko |
| Begivenhedsrisiko | 5 % | Dage til næste regnskab, gns. absolut kursudsving på tidligere regnskabsdage |

**Regler:**
- Retningen er fastlagt pr. faktor i én tabel i `risk.py` (fx giver høj markedsværdi lavere risiko).
- **Finansielle selskaber** (SIC 6000–6799): nettogæld/EBITDA, current ratio og Altman Z udelades.
- **Manglende faktor:** Vægten fordeles på de øvrige faktorer i gruppen. En gruppe uden faktorer fordeles på de
  øvrige grupper.
- **Dækning** vises som fx "31/38 factors". Er dækningen under 50 %, vises der ingen score, kun "insufficient data".
- **Negativ nævner** (underskud i P/E, EBITDA ≤ 0 i nettogæld/EBITDA): faktoren sættes til percentil 100.
- Vægtene er et første bud og ikke valideret. Siden siger det, og at scoren ikke er en forudsigelse af kursen.
- **M9 kalibrering:** Test scorens rangorden mod de faktiske max drawdowns de følgende 12 måneder (Spearman-korrelation)
  på historiske tidspunkter, og justér vægtene, hvis det giver en bedre rangorden.

## 6. Aktiesiden

URL: `#/AAPL`. Søgning med Cmd/Ctrl+K: præfiks-match på ticker først, derefter ord i navnet. Sektioner oppefra:

1. **Header:** navn, ticker, børs, sektor, kurs, dagens ændring, markedsværdi, risiko-badge og ☆ watchlist (`localStorage`).
2. **Kursgraf:** 1M, 6M, YTD, 1Y, 3Y, 5Y og 10Y. Kan sammenlignes med SPY og sektor-ETF'en, alle omregnet til 100 ved start.
3. **Kalender:** næste regnskab (bekræftet eller estimeret), ex-dividende- og udbetalingsdato, beregnede 10-Q/10-K-frister
   (ud fra regnskabsår og indberetningskategori) og forventet generalforsamling (sidste DEF 14A + 1 år). Eksport som `.ics`.
4. **Nøgletal:** seneste kvartal, TTM og seneste regnskabsår. Omsætning, brutto-, drifts- og nettomargin, EPS og FCF, med ændring fra året før.
5. **Regnskabshistorik:** 10 år eller 12 kvartaler for resultatopgørelse, balance og pengestrømme, som tabel og grafer.
6. **CAGR:** omsætning, EPS, FCF, udbytte pr. aktie, egenkapital pr. aktie og totalafkast over 1, 3, 5 og 10 år.
7. **Værdiansættelse:** P/E, EV/EBITDA og P/FCF med percentilbånd (10/50/90) mod egen historik. Reverse DCF med skydere
   for diskonteringsrente og terminalvækst.
8. **Kvalitet:** ROIC og marginer over tid, Piotroski F (0–9), Altman Z (med zoner) og Beneish M (med tærskel), hver med
   en forklaring på én linje.
9. **Risikoscore:** måler, søjle pr. gruppe, hver faktor kan foldes ud med værdi, percentil og retning, og en ansvarsfraskrivelse.
10. **Ejerskab:** insiderhandler (12 mdr.), aktieantal over tid og tilbagekøb i $.
11. **Peers:** op til 10 selskaber med samme SIC-kode og nærmeste markedsværdi. Tabellen kan sorteres.
12. **Filings:** de seneste 20 af typerne 8-K, 10-Q, 10-K og DEF 14A med links til SEC.
13. **Footer:** kilder, opdateringstidspunkt og "Not investment advice".

Ekstra sider: **Watchlist** (`#/watchlist`) og **Data status** (`#/status`, læser `meta.json`).

## 7. Fejlhåndtering

- Hver ticker behandles for sig. En fejl logges i `meta.json`, og den seneste gode JSON fra cachen bruges.
- Fejler over 20 % af kursopslagene (sandsynligvis en blokering), stopper udgivelsen, og den forrige version bliver online.
- Hver sektion på siden viser "No data", hvis dens felt mangler. Én tom sektion må aldrig vælte hele siden.
- Alle kald til SEC sender `User-Agent` med Eriks noreply-adresse og holder sig under 10 kald/s.
- Finnhub-nøglen læses fra miljøvariablen `FINNHUB_API_KEY` (lokalt `.env` i `.gitignore`, i Actions et secret).
  Mangler nøglen, springes Finnhub-felterne over, og resten bygges stadig.

## 8. Test

- **pytest** med fixtures (små udsnit af companyfacts og kurser) for tre slags selskaber: almindeligt (AAPL), bank og
  et med underskud. Hver beregning (CAGR, Q4-udledning, TTM, Piotroski, Altman, Beneish, percentiler, omfordeling af
  vægte, regel for negativ nævner) testes mod tal, der er regnet i hånden.
- **Ingen netværk i tests.** Hentemodulerne testes med gemte svar.
- **`node --test`** for søgning, talformatering og `.ics`-generering.
- **Browsertjek** i hver milepæl med siden: mindst AAPL, en lille aktie, en bank og et selskab med underskud, ved 375 px og 1280 px bredde.

## 9. Milepæle

| # | Milepæl | Færdig når (kort) |
|---|---|---|
| M0 | Opsætning + spike | Repo, `CLAUDE.md`, `.venv`. Målt: yfinance-succesrate og tid for ~5.000 tickers, størrelse og tid for `companyfacts.zip` |
| M1 | Univers + SEC-regnskaber | `search.json` findes. `financials.py` giver korrekte kvartaler, TTM og år for de 3 fixtures |
| M2 | Kurs-pipeline | Parquet-cache for hele universet med inkrementel opdatering |
| M3 | Første side | Søgning, header, kursgraf, nøgletal, historik og CAGR. Første udgivelse på Pages |
| M4 | Kalender | Finnhub + beregnede frister + `.ics` |
| M5 | Værdiansættelse + kvalitet | Sektion 7 og 8 med tests |
| M6 | Ejerskab, filings, peers, watchlist | Sektion 10–12 og watchlist-siden |
| M7 | Risikoscore | Score og opdeling for hele universet |
| M8 | Drift | Daglig kørsel i Actions, Data status, `portfolio.json` synlig |
| M9 | Kalibrering | Spearman-test af scoren mod drawdowns og eventuelt nye vægte |

## 10. Risici og åbne punkter

- **yfinance i stor skala** er usikker. Det afgøres i M0.
- **Kvaliteten af XBRL-data** varierer for små selskaber. Der vil være huller, og de vises som "No data" i stedet for at blive gættet.
- **Pages' grænse på 1 GB**: Filstørrelsen måles i M3. Er den for stor, skæres prishistorikken ned.
- **Finnhub's free tier** kan ændre sig. Siden virker uden Finnhub-felterne.
- **Analytikerdata og kursmål** fra yfinance/Finnhub er uofficielle og må kun vises med kildeangivelse.
