# Speakeasy-risk

Dagelijkse marktrisico-pipeline die een `risk.json` publiceert voor het JanApp-dashboard.
Meet **marktfragiliteit**, voorspelt geen crashes — zie [`Risk_module_design.md`](Risk_module_design.md)
voor de bindende specificatie.

> **Status: fase 3 (validatierapport) afgerond.**
> Zie [`VALIDATION.md`](VALIDATION.md) — daarop wordt beoordeeld of de module live gaat.
> AI-laag + workflow (fase 4) volgen.

## Opzet

| Onderdeel | Waar |
|---|---|
| Gewichten, drempels, tickers | `config.yaml` |
| Fetchers (één module per bron) | `src/fetch/` |
| Append-only historie | `data/history/<indicator>.csv` |
| Afgeleide reeksen | `src/derive.py` |
| Scoring (percentielen, regime, analogen) | `src/score.py` |
| Publicatie (`risk.json`, `history.csv`) | `src/publish.py` |
| Status van de laatste run | `state/fetch_status.json` |

Scoren gebeurt met point-in-time percentielen: een expanderend venster over de volledige
eigen historie van elke indicator (CAPE terug tot 1881, NFCI tot 1971), nooit met data van
later. Regimes worden vanaf 1990 berekend, met dubbele hysterese op de drempel van 60:
een wissel vereist 5 opeenvolgende dagen in het nieuwe kwadrant, en een as die "hoog" is
geworden valt pas terug onder 55 (Schmitt-trigger — anders flippert het label op weekschaal
rond de drempel, zoals medio 2022). Valt een indicator of pijler uit (te jong, bron stuk),
dan hernormaliseren de gewichten over wat er wél is.

Valideren: `python -m src.validate` genereert [`VALIDATION.md`](VALIDATION.md) —
event-studies, false positives, baselines, correlaties en sensitiviteit, alles point-in-time.

## Lokaal draaien

In PowerShell, in de map `C:\Users\janko\Documents\Speakeasy-risk`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Zet daarna je FRED-key in een `.env`-bestand in dezelfde map (staat in `.gitignore`, komt dus
nooit in de repo):

```
FRED_API_KEY=jouw_key_hier
```

Laad die key in je PowerShell-sessie en draai de bootstrap:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { Set-Item "env:$($matches[1].Trim())" $matches[2].Trim() } }
.\.venv\Scripts\python.exe -m src.main --bootstrap
```

Daarna volstaat een incrementele run:

```powershell
.\.venv\Scripts\python.exe -m src.main
```

Tests draaien (ook in dezelfde map):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Databronnen en hun houdbaarheid

Vier van de zes bronnen zijn gratis maar niet contractueel betrouwbaar. Elke fetcher mag falen
zonder de run te breken: dan blijft de laatst bekende waarde staan en wordt de indicator als
`stale` gemarkeerd. De run faalt pas als meer dan de helft van de meetellende indicatoren stale is.

| Bron | Stabiliteit | Aanpak |
|---|---|---|
| FRED (API) | stabiel | officiële API, key vereist |
| Yahoo (yfinance) | wisselvallig | defensieve kolomafhandeling, Stooq als fallback |
| Shiller CAPE | URL wijzigt maandelijks | link wordt van `shillerdata.com` geschraapt; Yale-URL als vangnet |
| FINRA margin debt | pagina verhuist | link wordt van de FINRA-pagina geschraapt, kolommen op inhoud herkend |
| ETF-holdings | formaat wijzigt | SSGA/SPY primair, iShares/IVV als fallback |

## Bekende beperkingen (bewust, geen bugs)

- **Top-10-concentratie heeft geen historie.** Holdings-bestanden geven alleen de stand van
  vandaag; er is geen gratis archief. De reeks begint bij de eerste run en telt onder de
  10-jaarsregel uit het design doc dus pas over tien jaar mee in de scoring. Tot die tijd rust
  pijler F3 volledig op margin debt.
- **Percentielvensters gebruiken de huidige datavintage.** FRED reviseert NFCI; die revisies
  zijn niet gratis als vintage beschikbaar. De store is daarom append-only: een eenmaal
  vastgelegde waarde blijft staan, zodat de historie vanaf nu wél echt point-in-time is.
- **Indicatoren starten op verschillende momenten.** De reële rente (en daarmee Excess CAPE
  Yield) begint in 2003, margin debt in 1997, RSP in 2003, VIX3M in 2006. Met de 10-jaarsregel
  betekent dat o.a.: geen ECY vóór 2013, geen VIX-ratio vóór 2016 en geen sectorbreedte vóór
  2009. Gewichten hernormaliseren dan; welke onderdelen wanneer meetelden wordt in fase 3
  gerapporteerd.
- **HY OAS is bij FRED afgeknot tot ~3 jaar** (ICE-licentie, ook via ALFRED dicht; geverifieerd
  juli 2026). De kredietstress-pijler scoort daarom op de Moody's Baa-spread (BAA10Y, volledig
  sinds 1986) — zelfde mechanisme, wél valideerbaar over alle vier de episodes. HY OAS wordt
  blijvend verzameld en kan na tien jaar eigen historie terugkeren.
- **De rentecurve wordt gescoord op zijn diepste stand van de afgelopen 18 maanden**, niet op
  het dagniveau. De curve leidt met 6-18 maanden (design doc §6); het dagniveau keert in een
  crisis om zodra paniekverlagingen de curve steil maken — oktober 2008 stond daardoor op
  risicopercentiel 1, precies terwijl het risico van de 2006-07-inversie zich materialiseerde.
