# JanApp Risk Module — Ontwerpdocument

*Marktfragiliteit meten in plaats van crashes voorspellen.*

## 1. Filosofie: waarom géén "Crash Probability Score"

Het eerlijkste vertrekpunt: **de timing van crashes is niet voorspelbaar.** Als een signaal betrouwbaar een crash twee weken vooruit kon zien, zou het weggearbitreerd worden. Daar komt een statistisch probleem bij: er zijn in 40 jaar maar vier à acht echte crash-episodes. Elke "kans op een crash: 23%" die op zo weinig events gekalibreerd is, is schijnprecisie — het getal suggereert een nauwkeurigheid die het datamateriaal fundamenteel niet kan dragen.

Wat wél meetbaar is, is **kwetsbaarheid**: de condities waaronder een willekeurige schok escaleert tot een grote drawdown. De aardbevingsanalogie klopt precies — je voorspelt de beving niet, je meet de spanning op de breuklijn. Dat leidt tot drie ontwerpprincipes:

1. **Twee assen in plaats van één score.** Trage, structurele *fragiliteit* (waardering, leverage, kredietcondities — bepaalt hoe diep het kán gaan) en snelle *stress* (spreads, breadth, vol-structuur — bepaalt of het vuur al brandt) zijn wezenlijk verschillende dingen. Medio 2007: hoge fragiliteit, lage stress. Maart 2020: matige fragiliteit, extreme stress. Eén samengevoegd getal vernietigt precies dit onderscheid — en het onderscheid is het meest actionable inzicht dat het model heeft.
2. **Percentielen in plaats van kansen.** Output is "huidige fragiliteit zit in het 87e percentiel sinds 1990", niet "31% crashkans". Dat is verdedigbaar, uitlegbaar en net zo bruikbaar.
3. **Historische analogen als brug naar intuïtie.** De k meest vergelijkbare historische periodes (in fragiliteit×stress-ruimte) plus wat daarna gebeurde, geeft de gebruiker een gevoel voor de *verdeling* van uitkomsten — inclusief de keren dat er niets gebeurde.

Elke indicator moet aan vier criteria voldoen: een economisch mechanisme (waaróm zou het werken), real-time beschikbaar zonder lookahead, bewijs over meerdere episodes (niet één), en lage overlap met al gekozen indicatoren.

## 2. Wat de vier episodes werkelijk leren

**Dotcom (2000).** Waardering was extreem (CAPE ~44) en breadth divergeerde al vanaf 1998: de advance-decline-lijn en equal-weight-indices piekten ruim vóór de cap-weighted index — de rally werd door steeds minder aandelen gedragen. De rentecurve inverteerde in 2000. Waardering voorspelde de *omvang* van de schade, breadth gaf het bruikbaarste timingsignaal.

**Kredietcrisis (2008).** Hét signaal zat in krediet: high-yield-spreads begonnen zomer 2007 te verwijden, interbancaire stress (TED) liep op, financials presteerden relatief zwak, de curve was in 2006 al geïnverteerd. Cruciale les: **aandelenwaardering was maar matig verhoogd** — een puur waarderingsmodel had 2008 grotendeels gemist. De fragiliteit zat in leverage en krediet, niet in koers/winst.

**COVID (2020).** Geen enkele trage indicator waarschuwde — een exogene schok is per definitie ex ante onzichtbaar. De waarde van het model in 2020 was tweeledig: de snelle stress-laag (vol-termijnstructuur, spreads) bevestigde binnen dagen dat dit geen gewone dip was, én de matige fragiliteit verklaarde correct waarom het herstel zo snel kon zijn. Een model dat claimt COVID te hebben kunnen zien aankomen, is per definitie overfit.

**Rentecorrectie (2022).** Waardering extreem (vooral groeiaandelen), plus een heldere macro-trigger: stijgende reële rentes en een krimpende Fed-balans. Speculatieve froth (SPACs, crypto, verlieslatende tech) en recordgroei in margin debt (2021) waren de fragiliteitssignalen. Trendindicatoren (200-daags gemiddelde) werkten hier uitstekend als drawdown-filter omdat het een slijtende daling was — terwijl diezelfde indicatoren in 2020 te laat waren.

**Cross-episode conclusies.** Geen enkele indicator werkt in alle vier — daarom een gecombineerd model. Krediet is de beste allrounder (2008 vroeg, 2000 en 2022 coincident, 2020 snel bevestigend). Waardering voorspelt omvang, nooit timing. Breadth is het beste vroege marktinterne signaal bij endogene toppen (2000, in mindere mate 2007 en 2021). De curve leidt met 6-18 maanden maar met zulke variabele lags dat hij alleen als regime-context bruikbaar is. En: indicatoren slijten — de put/call-ratio is sinds de 0DTE-optie-explosie (2022+) structureel onbruikbaar geworden. Het model moet indicator-veroudering als gegeven behandelen.

## 3. De vijf pijlers

Bewust weinig pijlers met elk 2-4 indicatoren. Meer indicatoren ≠ meer informatie; het vergroot vooral de kans op dubbeltelling en onderhoudslast.

### Fragiliteit-as (traag, structureel)

**Pijler F1 — Waardering** (gewicht 45%)

| Indicator | Meet | Bron | Freq | Waarom |
|---|---|---|---|---|
| Shiller CAPE (percentiel) | Absolute waardering | Shiller-dataset (gratis) | mnd | Beste voorspeller van 10j-rendement én max-drawdown-omvang |
| Excess CAPE Yield | Waardering t.o.v. reële rente | Shiller + FRED (DFII10) | mnd | Corrigeert voor "hoge CAPE is gerechtvaardigd bij lage rente" — het verschil tussen beide vertelt of rente de achilleshiel is (setup van 2022) |

**Pijler F2 — Structurele kredietcondities** (gewicht 30%)

| Indicator | Meet | Bron | Freq | Waarom |
|---|---|---|---|---|
| Rentecurve 10j-3m | Late-cycle-regime | FRED (T10Y3M) | dag | Ging vooraf aan 2000 en 2008; lange variabele lag → klein gewicht, regime-context |
| Chicago Fed NFCI | Brede financiële condities | FRED (NFCI) | week | Samengestelde leverage/funding-maat, professioneel onderhouden, gratis |

**Pijler F3 — Positionering & marktstructuur** (gewicht 25%)

| Indicator | Meet | Bron | Freq | Waarom |
|---|---|---|---|---|
| Margin debt, YoY-groei | Gedwongen-verkoop-potentieel | FINRA (gratis, ~1 mnd lag) | mnd | Extreme groei ging vooraf aan 2000 en 2022; mechanisme (deleveraging-spiraal) is solide |
| Top-10-concentratie S&P 500 | Kwetsbaarheid voor smalle leiderschap | ETF-holdings (IVV/SPY CSV) | week | Hoge concentratie = indexrisico hangt aan weinig namen; nu relevanter dan ooit |

### Stress-as (snel, tactisch)

**Pijler S1 — Volatiliteitsstructuur** (gewicht 35%)

| Indicator | Meet | Bron | Freq | Waarom |
|---|---|---|---|---|
| VIX/VIX3M-ratio | Backwardation = acute angst | Yahoo/Stooq (^VIX, ^VIX3M) | dag | Termijnstructuur is robuuster dan VIX-niveau: inversie betekent dat de markt nú meer vreest dan straks — het betrouwbaarste "het is begonnen"-signaal |
| Trendstatus index (200d MA + afstand tot 52w-high) | Bevestigde downtrend | Yahoo/Stooq | dag | Niet voorspellend, wél het beste filter tegen diepe grinding bears (2000, 2008, 2022) |

**Pijler S2 — Marktbreedte** (gewicht 35%)

| Indicator | Meet | Bron | Freq | Waarom |
|---|---|---|---|---|
| % van 11 S&P-sector-ETF's boven eigen 200d MA | Breedte van de trend | Yahoo/Stooq (11 tickers) | dag | Lichtgewicht proxy voor marktbreedte zonder constituent-data — praktisch gratis en verrassend effectief |
| RSP/SPY relatieve 6m-performance | Equal-weight vs cap-weight divergentie | Yahoo/Stooq | dag | Hét dotcom-signaal: index stijgt, gemiddeld aandeel niet |

**Pijler S3 — Kredietstress** (gewicht 30%)

| Indicator | Meet | Bron | Freq | Waarom |
|---|---|---|---|---|
| HY OAS, niveau | Risicoprijs krediet | FRED (BAMLH0A0HYM2) | dag | Kredietmarkt is de "adult in the room" — prijst stress vaak vóór aandelen |
| HY OAS, 63-daagse verandering | Momentum van verwijding | zelfde serie | dag | De *verandering* was in 2007 informatiever dan het niveau |

## 4. Wat bewust NIET meegaat, en waarom

**Sentiment-surveys (AAII, Fear & Greed).** Geen aantoonbare voorspellende waarde voor staartrisico; mean-reverting ruis op weekbasis. Dit is precies de gimmick-categorie die de opdracht wil vermijden. **Put/call-ratio's.** Structureel gebroken door 0DTE-opties sinds 2022 — schoolvoorbeeld van indicator-veroudering. **Insider-transacties.** Signaal op aandelniveau, zwak op indexniveau, en goede data zit achter betaalmuren. **Fondsstromen.** Gemengd bewijs, slechte gratis databeschikbaarheid. **Macro-releases (ISM, werkloosheid/Sahm).** De markt is zelf een van de beste leading indicators van de economie; macrodata toevoegen importeert vooral lag en dubbeltelt met curve en krediet. **M2/"Fed net liquidity".** Populair op fintwit, causaal wankel, relatie instabiel na 2020. **Buffett-indicator (marktkap/BBP).** Vrijwel perfect gecorreleerd met CAPE — pure dubbeltelling. **Technische patronen (Hindenburg Omen e.d.).** Datamining zonder mechanisme.

## 5. Scoring en weging

Per indicator: **percentiel binnen een expanderend historisch venster** vanaf 1990 (minimaal 10 jaar historie voordat een indicator meetelt). Percentielen in plaats van z-scores: robuust tegen fat tails en tegen structurele niveauverschuivingen (CAPE is structureel hoger dan in 1950 — het venster verwerkt dat geleidelijk).

Pijlerscore = gewogen gemiddelde van de indicator-percentielen (gewichten binnen pijler gelijk, tenzij hierboven anders vermeld). Daarna:

- **Fragiliteit (0-100)** = 0,45·F1 + 0,30·F2 + 0,25·F3
- **Stress (0-100)** = 0,35·S1 + 0,35·S2 + 0,30·S3

**De gewichten zijn beredeneerd, niet geoptimaliseerd — en dat is een feature.** Gewichten fitten op vier crash-events is gegarandeerd overfitting. In plaats daarvan: sensitiviteitsanalyse (elk gewicht ±50% variëren) en eisen dat de regime-classificatie daar grotendeels ongevoelig voor is. Als de conclusie omslaat bij een kleine gewichtswijziging, is het signaal te zwak om te rapporteren.

**Regime-kwadrant** (met hysterese: een regimewissel vereist 5 opeenvolgende dagen over de drempel, anders flippert het dagelijks):

| | Stress laag | Stress hoog |
|---|---|---|
| **Fragiliteit laag** | Kalm | Schok (2020-type: diep maar historisch vaak snel herstel) |
| **Fragiliteit hoog** | Fragiele rust (2007, 2021: stapelend risico) | Storm (2008, 2022: beide assen actief) |

**Analoge-periodes-uitvoer** in plaats van een kansgetal: zoek de 20 meest nabije historische maanden in (fragiliteit, stress)-ruimte en toon de verdeling van de daaropvolgende 12-maands max-drawdowns. "In de 20 meest vergelijkbare periodes was de mediane max-drawdown in het jaar erna −7%, de slechtste −44%" is eerlijk, uitlegbaar en informatiever dan elke pseudo-kans.

## 6. Leading / coincident / lagging

| Indicator | Karakter | Typische lead |
|---|---|---|
| CAPE / ECY | Leading voor omvang, nutteloos voor timing | jaren |
| Rentecurve | Leading, onbetrouwbare lag | 6-18 mnd |
| Margin debt | Leading (publicatielag 1 mnd) | 6-12 mnd |
| NFCI, concentratie | Traag coincident | — |
| Breadth (sectoren, RSP/SPY) | Leading bij endogene toppen | 3-12 mnd |
| HY OAS (verandering) | Kort leading tot coincident | 0-3 mnd |
| VIX-termijnstructuur | Coincident | dagen |
| Trendstatus (200d MA) | Lagging maar bevestigend | −1 à −2 mnd |

Deze mix is een bewuste keuze: de leading-indicatoren zetten de fragiliteit-as, de coincident/lagging-indicatoren maken de stress-as betrouwbaar. Een model met alléén leading indicatoren geeft jarenlang vals alarm; met alléén coincident indicatoren ben je altijd te laat.

## 7. Dubbeltelling voorkomen

Drie mechanismen, in oplopende zwaarte: (1) **verwante indicatoren zitten in dezelfde pijler** en verdelen daar één gewicht — HY-niveau en HY-verandering kunnen samen nooit meer dan 30% van de stress-as vullen; (2) **één indicator per informatiebron**: geen Buffett-indicator naast CAPE, geen VIX-niveau naast de termijnstructuur, geen ISM naast de curve; (3) bij validatie de **paarsgewijze correlatie van pijlerscores** rapporteren — komt een paar structureel boven ~0,8 uit, dan worden de pijlers samengevoegd. Bewust géén PCA: dat scoort beter op papier maar maakt het model onuitlegbaar en onhoudbaar — precies wat dit dashboard niet moet zijn.

## 8. Historische validatie

1. **Point-in-time dataset** bouwen vanaf 1990 (waar mogelijk eerder), met expanderende percentiel-vensters en publicatielags gerespecteerd (margin debt op publicatiedatum, niet meetdatum). Geen enkel datapunt uit de toekomst.
2. **Event-studies** rond de vier episodes: venster van 24 maanden vóór tot 12 maanden na de top; per pijler vastleggen wanneer die begon te signaleren.
3. **False-positive-set, even belangrijk:** 1998 (LTCM), 2011 (eurocrisis), 2015-16, Q4 2018, maart 2023 (bankenstress). Een goed fragiliteitsmodel mág daar verhoogde stress tonen — het moet die episodes alleen niet als 2008 classificeren. Hit-rate én vals-alarm-gedrag worden beide gerapporteerd.
4. **Baseline-toets:** het samengestelde model moet aantoonbaar beter drawdown-risico rangschikken dan drie simpele baselines — HY OAS alleen, 200d-MA-regel alleen, VIX>30-regel alleen. Verslaat het die niet, dan verdient de complexiteit zijn plek niet en wordt het model versimpeld.
5. **Eerlijke rapportage van n.** Met vier grote events is elke kwantitatieve metric indicatief; de validatie is uiteindelijk narratief ("wat zei het model in september 2007?") plus kalibratie van de analoge-periodes-uitvoer.

## 9. Dashboard-output (JanApp)

Bovenaan het **regime-badge** (Kalm / Fragiele rust / Storm / Schok) met twee compacte meters: fragiliteit- en stress-percentiel. Daaronder de **drivers**: zes pijlerbalken met een pijl voor de 1-maands verandering, en de top-3 "wat drijft dit beeld" in één zin per stuk. Dan de **historische strip**: beide assen als tijdreeks sinds 1990 met gearceerde crisisperiodes — dit bouwt meer vertrouwen dan welk getal ook, omdat de gebruiker zelf ziet hoe het model zich bij 2008 en 2020 gedroeg. Onderaan het **analogen-paneel**: de meest vergelijkbare historische periodes met wat er daarna gebeurde. Nergens een "crashkans"-percentage.

## 10. AI-laag

Claude genereert alleen tekst **wanneer er iets verandert**: een regimewissel, een pijler die >15 percentielpunten in een maand beweegt, of een indicator die een historisch extreem bereikt. Anders volstaat een wekelijkse synthese van drie zinnen. Dagelijkse AI-boilerplate ("de markt bleef vandaag stabiel...") traint de gebruiker om de module te negeren.

Harde regel voor de prompt: **de AI legt data uit, voorspelt nooit.** Format: wat veranderde, welke onderliggende indicator dat dreef, welke historische parallel relevant is — in het Nederlands, warm-zakelijk, drie tot vijf zinnen. Maandelijks optioneel een langere "stand van de breuklijn"-synthese.

## 11. Implementatie

Zelfde patroon als `janapp-feed`: een aparte repo/workflow (GitHub Actions, dagelijkse cron na US-close, ~22:15 ET) die een `risk.json` publiceert die JanApp via een `RISK_URL` inleest — identiek aan het FEED_URL-mechanisme. Historie als CSV in de repo (append-only), zodat de point-in-time-eigenschap gratis geborgd is.

Databronnen: FRED API (gratis key: HY OAS, curve, NFCI, reële rente), Yahoo Finance/Stooq (indices, VIX-futures-indices, 13 ETF-tickers), Shiller-dataset (maandelijkse download), FINRA margin debt (maandelijks bestand). Alles gratis; LLM-kosten verwaarloosbaar door de alleen-bij-verandering-regel. Rekenwerk is triviaal (percentielen over ~9.000 dagrijen) — de run duurt minuten.

`risk.json`-schema:

```json
{
  "generated_at": "ISO-8601",
  "regime": "fragile_calm",
  "regime_since": "2026-05-12",
  "fragility": {"score": 78, "pillars": {"valuation": 91, "credit_slow": 62, "positioning": 74}},
  "stress": {"score": 31, "pillars": {"volatility": 22, "breadth": 44, "credit_fast": 28}},
  "drivers": [{"indicator": "cape", "percentile": 93, "delta_1m": 2, "note_nl": "…"}],
  "analogs": [{"period": "1999-11", "fwd_12m_max_dd": -0.28}],
  "ai_summary_nl": "…of null als er niets veranderde",
  "history_url": "…csv"
}
```

## 12. Eerlijke beperkingen

Exogene schokken (pandemie, oorlog) zijn ex ante onzichtbaar — het model meet brandbaarheid, niet bliksem. Indicatoren slijten; jaarlijkse herijking (werkt de termijnstructuur-ratio nog zoals verwacht?) hoort bij het onderhoud. Het model is US-centrisch (S&P 500 als kern) — verdedigbaar omdat wereldwijde crashes vrijwel altijd via de VS lopen en de watchlist US-heavy is, maar een AEX-satellietscore kan later. En de belangrijkste: dit is een *awareness*-instrument, geen handelssignaal. De juiste gebruiksverwachting is dat het je één keer per paar jaar behoedt voor zelfgenoegzaamheid, en de rest van de tijd bevestigt dat er weinig aan de hand is.
