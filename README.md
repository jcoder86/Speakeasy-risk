# Speakeasy-risk

Dagelijkse marktrisico-pipeline die een `risk.json` publiceert voor het JanApp-dashboard.
Meet **marktfragiliteit**, voorspelt geen crashes — zie [`Risk_module_design.md`](Risk_module_design.md)
voor de bindende specificatie.

> **Status: fase 1 (fetchers + historische backfill) afgerond.**
> Scoring, validatie en de AI-laag volgen in fase 2 t/m 4.

## Opzet

| Onderdeel | Waar |
|---|---|
| Gewichten, drempels, tickers | `config.yaml` |
| Fetchers (één module per bron) | `src/fetch/` |
| Append-only historie | `data/history/<indicator>.csv` |
| Afgeleide reeksen | `src/derive.py` |
| Status van de laatste run | `state/fetch_status.json` |

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
- **Indicatoren starten op verschillende momenten.** HY OAS begint in 1996, de reële rente
  (en daarmee Excess CAPE Yield) in 2003, margin debt in 1997, RSP in 2003. Met de 10-jaarsregel
  betekent dat: geen kredietstress-pijler vóór 2007 en geen ECY vóór 2013. Dit raakt de
  event-studie van 2000 en wordt in fase 3 expliciet gerapporteerd.
