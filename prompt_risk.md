# Claude Code-prompts — Risk Module naar productie

Twee prompts. **Prompt A** bouwt de pipeline in de private repo `Speakeasy-risk` (waar dit bestand en het design doc al staan). **Prompt B** integreert het paneel in JanApp (deze repo, ná fase 3a van de renovatie).

---

## Prompt A — pipeline-repo `Speakeasy-risk`

Bouw een dagelijkse marktrisico-pipeline die een `risk.json` publiceert voor mijn dashboard (JanApp). Lees eerst het design doc in deze repo (`Risk_module_design.md`) — dat is de bindende specificatie; deze prompt regelt alleen de uitvoering. Python 3.11+, GitHub Actions cron (dagelijks na US-close), geen server. Werk in vier fasen, commit per fase, stop na elke fase voor review.

Robuustheid: elke run haalt alle ontbrekende dagen sinds de vorige succesvolle run op en verwerkt die — een gemiste of mislukte run leidt dus nooit tot gaten in de historie, en AI-triggers worden over alle ingehaalde dagen geëvalueerd.

### Randvoorwaarden
- Secrets: `FRED_API_KEY` en `ANTHROPIC_API_KEY` als GitHub Secrets. Nooit in code.
- **Elke fetcher mag falen zonder de run te breken.** Bij falen: laatste bekende waarde gebruiken, indicator markeren als `stale` met `as_of`-datum in de output. De run faalt alleen als >50% van de indicatoren stale is.
- Historie is heilig: `data/history/<indicator>.csv` (date,value), append-only, gecommit door de action. Percentielen worden altijd point-in-time berekend (expanderend venster vanaf 1990, minimaal 10 jaar historie voordat een indicator meetelt — indicatoren met kortere historie, zoals VIX3M, tellen pas mee vanaf het moment dat ze 10 jaar data hebben).
- Publicatielags respecteren: margin debt telt mee per publicatiedatum (~1 maand na meetmaand), niet per meetmaand.

### Fase 1 — Fetchers + historische backfill
1. `src/fetch/` met één module per bron, uniforme interface (geeft DataFrame date,value):
   - **FRED** (API, key): `BAMLH0A0HYM2` (HY OAS), `T10Y3M` (curve), `NFCI`, `DFII10` (10j reëel).
   - **Koersen** via yfinance (fallback: Stooq): `^GSPC`, `^VIX`, `^VIX3M`, `SPY`, `RSP` en de 11 sector-ETF's (XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY).
   - **Shiller-dataset** (maandelijkse Excel van econ.yale.edu): CAPE; bereken Excess CAPE Yield met DFII10.
   - **FINRA margin debt** (maandelijks bestand op finra.org): niveau → YoY-groei. Deze bron is fragiel qua formaat — parse defensief, log bij falen.
   - **Top-10-concentratie**: dagelijkse holdings-CSV van IVV (iShares) of SPY (SSGA), som van de 10 grootste gewichten. Ook fragiel — zelfde defensieve aanpak.
2. Bootstrap-commando (`python -m src.main --bootstrap`) dat volledige beschikbare historie ophaalt en de CSV's vult. FRED, Yahoo en Shiller leveren decennia gratis; margin debt-historie zit in het FINRA-bestand zelf.
3. Afgeleide reeksen berekenen en opslaan: VIX/VIX3M-ratio, % sector-ETF's boven eigen 200d MA, RSP/SPY 6m relatieve return, HY OAS 63d-verandering, trendstatus ^GSPC (boven/onder 200d MA + afstand tot 52w-high).

### Fase 2 — Scoring-engine + risk.json
1. `src/score.py`: percentielen (point-in-time), pijlerscores en assen exact volgens de gewichten in het design doc (§5). Regime-kwadrant met hysterese: wissel vereist 5 opeenvolgende dagen over de drempel (drempels: score 60 als "hoog", configureerbaar in `config.yaml`).
2. Analogen (§5): de 20 meest nabije historische maanden in (fragiliteit, stress)-ruimte (euclidisch), met per analoog de forward 12m max-drawdown van de S&P 500. Sluit de 12 maanden vóór "vandaag" uit.
3. Drivers: top-3 indicatoren op |delta_1m| × gewicht, elk met percentiel, delta en een korte NL-notitie uit een template (nog geen LLM).
4. `src/publish.py` schrijft `risk.json` exact volgens het schema in §11 van het design doc, plus `history.csv` (wekelijkse fragility/stress-samples voor de grafiekstrip in JanApp).
5. Unit tests (pytest): percentiel-berekening (expanderend venster, geen lookahead), hysterese-logica, gewicht-som = 1. Sanity-tests op bekende datums na bootstrap: oktober 2008 → Storm, december 2021 → Fragiele rust, april 2020 → Schok of Storm. Falen die: eerst begrijpen waarom, niet de drempels tweaken tot het past.

### Fase 3 — Validatierapport
`python -m src.validate` genereert `VALIDATION.md` volgens §8 van het design doc: event-studies rond 2000/2008/2020/2022 (venster −24m/+12m, per pijler het eerste signaalmoment), de false-positive-set (1998, 2011, 2015-16, Q4 2018, maart 2023), de drie baseline-vergelijkingen (HY OAS alleen, 200d-MA-regel, VIX>30), paarsgewijze pijlercorrelaties, en de gewicht-sensitiviteit (±50% per gewicht → % dagen waarop het regime verandert). Presenteer resultaten neutraal — ook waar het model tegenvalt. Dit rapport is een deliverable, geen formaliteit: ik beoordeel hierop of de module live gaat.

### Fase 4 — AI-laag + workflow
1. `src/summarize.py`: Claude-call (model `claude-sonnet-latest` equivalent) alléén bij een trigger: regimewissel, pijler beweegt >15 percentielpunten in een maand, of een indicator bereikt >95e/<5e percentiel. Anders op maandag een synthese van 3 zinnen; overige dagen `ai_summary_nl: null`. Systemprompt-kern: *"Je legt data uit, je voorspelt nooit. Geen koersdoelen, geen advies, geen hype. NL, warm-zakelijk, 3-5 zinnen: wat veranderde, welke indicator dat dreef, welke historische parallel relevant is."*
2. `.github/workflows/risk.yml`: cron `30 5 * * 1-6` (dagelijks na US-close, ma-za), stappen: fetch (incl. inhaal van gemiste dagen) → score → summarize → commit `risk.json` + `history.csv` + `data/history/`. Plus `workflow_dispatch` met input `bootstrap: true`.
3. `README.md`: secrets aanmaken, bootstrap-run draaien, validatie draaien, `RISK_URL` voor JanApp = raw-URL van `risk.json`.

### Repo-structuur
```
Speakeasy-risk/
  Risk_module_design.md
  prompt_risk.md
  config.yaml               (gewichten, drempels, hysterese-dagen, tickers)
  .github/workflows/risk.yml
  src/ (main.py, fetch/, score.py, validate.py, summarize.py, publish.py)
  data/history/*.csv
  risk.json
  history.csv
  VALIDATION.md
  tests/
  requirements.txt (httpx, pandas, yfinance, anthropic, pyyaml, pytest, openpyxl)
```

---

## Prompt B — JanApp-integratie (deze repo)

Voeg een Risk-paneel toe aan JanApp. Lees `docs/RISK_MODULE_DESIGN.md` §9 voor het gewenste eindbeeld. Randvoorwaarden ongewijzigd: vanilla JS, geen framework, geen build-step, geen chart-libraries — de grafiekstrip wordt inline SVG.

1. **Backend:** env `RISK_URL` (raw-URL van risk.json) en `RISK_HISTORY_URL`. `GET /api/risk` proxyt beide, server-side cache 30 minuten, nette lege respons (`{available: false}`) als de env ontbreekt of de fetch faalt.
2. **UI** — een kaart bovenin de feed-kolom (desktop) / bovenaan de Feed-tab (mobiel), inklapbaar:
   - Regime-badge met kleur (Kalm groen, Fragiele rust amber, Schok oranje, Storm rood) + "sinds {regime_since}".
   - Twee horizontale percentiel-meters (fragiliteit, stress) met de zes pijlerbalken eronder, elk met delta-pijl (1m).
   - Historische strip: fragility- en stress-lijnen uit history.csv als SVG-sparkline (~sinds 1990), met gearceerde banden voor 2000-02, 2007-09, 2020, 2022.
   - Analogen: compacte lijst "meest vergelijkbare periodes" met forward-drawdown.
   - `ai_summary_nl` als tekstblok, alleen indien niet null. Stale-indicatoren tonen een ⚠ met as-of-datum in een tooltip.
   - Onderaan één vaste regel: *"Meet kwetsbaarheid, voorspelt geen crashes."*
3. **Definition of done:** werkt lokaal met `npm run dev` en een test-fixture (`public/fixtures/risk.sample.json` meeleveren, gebruikt als `RISK_URL` ontbreekt in dev-modus); geen console-errors; beide schermformaten getest; bestaande functionaliteit onaangetast.
