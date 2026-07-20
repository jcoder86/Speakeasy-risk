# Validatierapport — JanApp Risk Module

Gegenereerd: 2026-07-20 · reproduceerbaar via `python -m src.validate` · alles point-in-time.

Met vier grote events is elke kwantitatieve metric indicatief; dit rapport is
narratief plus kalibratie, geen bewijs (design doc §8.5).

## 1. Databeschikbaarheid (eerlijke n)

Percentielen gebruiken de volledige eigen historie van elke indicator, maar een
indicator telt pas mee na tien jaar eigen data. Daardoor draait niet elke episode
op dezelfde set — onderstaande tabel is de leeswijzer bij alles hierna.

| Indicator | telt mee vanaf |
|---|---|
| `cape` | 1990-01-01 |
| `excess_cape_yield` | 2013-01-07 |
| `yield_curve_18m_min` | 1993-07-06 |
| `nfci` | 1990-01-01 |
| `margin_debt_yoy` | 2008-02-25 |
| `vix_ratio` | 2016-07-18 |
| `trend_stress` | 1990-12-31 |
| `sectors_above_200dma` | 2009-10-07 |
| `rsp_spy_6m` | 2013-10-29 |
| `baa_spread` | 1996-01-02 |
| `baa_spread_63d` | 1996-04-04 |

Gevolgen: de dotcom-episode draait zonder positionering, breedte en VIX-structuur;
2008 mist breedte en VIX-structuur; ECY doet pas vanaf 2013 mee. HY OAS is bij FRED
afgeknot tot ~3 jaar historie (ICE-licentie); kredietstress scoort daarom op de
Moody's Baa-spread (volledig sinds 1986).

## 2. Event-studies (venster −24m / +12m rond de top)

"Eerste signaal" = de eerste dag binnen het venster waarop een pijler ≥ 60 stond.

### Dotcom (2000) — top 2000-03-24

Max-drawdown S&P 500 in de 12 maanden na de top: **-27%**.

| Pijler | eerste signaal (≥60) | piek in venster |
|---|---|---|
| Waardering (F1) | 1998-03-24 (-24m) | 100 |
| Kredietcondities (F2) | 1998-08-28 (-19m) | 75 |
| Positionering (F3) | geen data | geen data |
| Volatiliteit (S1) | 1998-08-03 (-19m) | 100 |
| Breedte (S2) | geen data | geen data |
| Kredietstress (S3) | 1998-04-02 (-23m) | 98 |

Assen op de topdag: fragiliteit 85, stress 45. Regime op de topdag: **Fragiele rust**.

Regimeverloop in het venster:

- 1998-03-24: Fragiele rust
- 1998-08-10: Storm
- 1998-12-25: Fragiele rust
- 1999-08-04: Storm
- 1999-11-17: Fragiele rust
- 2000-02-24: Storm
- 2000-03-23: Fragiele rust
- 2000-04-05: Storm
- 2000-07-18: Fragiele rust
- 2000-07-28: Storm

### Kredietcrisis (2008) — top 2007-10-09

Max-drawdown S&P 500 in de 12 maanden na de top: **-42%**.

| Pijler | eerste signaal (≥60) | piek in venster |
|---|---|---|
| Waardering (F1) | 2005-10-10 (-24m) | 94 |
| Kredietcondities (F2) | 2007-04-13 (-6m) | 88 |
| Positionering (F3) | — | 52 |
| Volatiliteit (S1) | 2005-10-10 (-24m) | 100 |
| Breedte (S2) | geen data | geen data |
| Kredietstress (S3) | 2005-11-22 (-23m) | 100 |

Assen op de topdag: fragiliteit 86, stress 47. Regime op de topdag: **Fragiele rust**.

Regimeverloop in het venster:

- 2005-10-10: Fragiele rust
- 2005-10-18: Storm
- 2005-11-16: Fragiele rust
- 2007-08-01: Storm
- 2007-10-05: Fragiele rust
- 2007-10-25: Storm

### COVID (2020) — top 2020-02-19

Max-drawdown S&P 500 in de 12 maanden na de top: **-34%**.

| Pijler | eerste signaal (≥60) | piek in venster |
|---|---|---|
| Waardering (F1) | 2018-02-19 (-24m) | 87 |
| Kredietcondities (F2) | 2019-08-14 (-6m) | 82 |
| Positionering (F3) | 2018-02-19 (-24m) | 90 |
| Volatiliteit (S1) | 2018-02-19 (-24m) | 99 |
| Breedte (S2) | 2018-02-19 (-24m) | 98 |
| Kredietstress (S3) | 2018-05-29 (-21m) | 99 |

Assen op de topdag: fragiliteit 60, stress 45. Regime op de topdag: **Kalm**.

Regimeverloop in het venster:

- 2018-02-19: Fragiele rust
- 2018-03-23: Storm
- 2018-05-16: Fragiele rust
- 2018-06-27: Storm
- 2018-07-12: Fragiele rust
- 2018-10-16: Storm
- 2019-01-31: Schok
- 2019-02-26: Kalm
- 2019-05-29: Schok
- 2019-06-24: Kalm
- 2019-08-08: Schok
- 2019-09-10: Kalm
- 2019-10-08: Schok
- 2019-10-17: Kalm
- 2020-02-28: Storm
- 2020-04-10: Schok
- 2020-07-23: Kalm
- 2020-10-30: Storm
- 2020-11-09: Fragiele rust

### Rentecorrectie (2022) — top 2022-01-03

Max-drawdown S&P 500 in de 12 maanden na de top: **-25%**.

| Pijler | eerste signaal (≥60) | piek in venster |
|---|---|---|
| Waardering (F1) | 2020-01-03 (-24m) | 86 |
| Kredietcondities (F2) | 2020-01-03 (-24m) | 82 |
| Positionering (F3) | 2020-10-26 (-15m) | 99 |
| Volatiliteit (S1) | 2020-01-27 (-24m) | 99 |
| Breedte (S2) | 2020-01-21 (-24m) | 98 |
| Kredietstress (S3) | 2020-02-27 (-23m) | 99 |

Assen op de topdag: fragiliteit 62, stress 37. Regime op de topdag: **Fragiele rust**.

Regimeverloop in het venster:

- 2020-01-03: Kalm
- 2020-02-28: Storm
- 2020-04-10: Schok
- 2020-07-23: Kalm
- 2020-10-30: Storm
- 2020-11-09: Fragiele rust
- 2022-01-27: Storm
- 2022-02-08: Fragiele rust
- 2022-02-16: Storm
- 2022-03-11: Schok
- 2022-03-28: Kalm
- 2022-04-28: Schok
- 2022-06-02: Kalm
- 2022-06-21: Schok
- 2022-10-11: Storm
- 2022-11-25: Fragiele rust

## 3. False-positive-set

Episodes met echte marktstress die géén 2008 werden. Verhoogde stress tonen mag;
de vraag is of het model ze als Storm classificeerde en hoe lang.

| Episode | daling S&P | max fragiliteit | max stress | dagen Storm | dagen Schok |
|---|---|---|---|---|---|
| LTCM (1998) | -19% | 87 | 97 | 99 | 0 |
| Eurocrisis (2011) | -19% | 68 | 92 | 67 | 45 |
| China/olie (2015-16) | -13% | 52 | 90 | 0 | 186 |
| Q4 2018 | -20% | 62 | 88 | 55 | 0 |
| Bankenstress (mrt 2023) | -5% | 66 | 75 | 26 | 0 |

## 4. Kalibratie: wat volgde er op elk regime?

Forward 12-maands max-drawdown van de S&P 500, per regime (maandelijkse samples,
laatste 12 maanden uitgesloten). Dit kalibreert ook de analogen-uitvoer.

| Regime | maanden | mediane fwd DD | ergste fwd DD | % erger dan −15% |
|---|---|---|---|---|
| Kalm | 73 | -7% | -34% | 19% |
| Fragiele rust | 114 | -10% | -27% | 32% |
| Schok | 38 | -9% | -34% | 18% |
| Storm | 72 | -19% | -53% | 54% |

## 5. Baseline-vergelijking

Spearman-rangcorrelatie tussen signaalwaarde en de ernst van de forward 12m
max-drawdown (maandelijkse samples). Hoger = beter rangschikken van drawdown-risico.
De HY-OAS-baseline uit het design doc is niet reproduceerbaar (FRED-historie afgeknot);
de Baa-spread vervult die rol. De binaire regels zijn grofkorrelig — dat is precies
hun handicap als baseline.

| Signaal | Spearman | n |
|---|---|---|
| model: fragiliteit | 0.42 | 415 |
| model: stress | 0.27 | 415 |
| model: (F+S)/2 | 0.42 | 415 |
| baseline: Baa-spread-percentiel | 0.10 | 354 |
| baseline: koers onder 200d MA | 0.23 | 415 |
| baseline: VIX > 30 | 0.09 | 415 |

## 6. Paarsgewijze pijlercorrelaties

Boven ~0,8 zou samenvoegen aan de orde zijn (design doc §7).

| | Waardering (F1) | Kredietcondities (F2) | Positionering (F3) | Volatiliteit (S1) | Breedte (S2) | Kredietstress (S3) |
|---|---|---|---|---|---|---|
| Waardering (F1) | 1.00 | 0.13 | 0.23 | -0.01 | 0.20 | -0.15 |
| Kredietcondities (F2) | 0.13 | 1.00 | -0.30 | 0.24 | 0.40 | 0.08 |
| Positionering (F3) | 0.23 | -0.30 | 1.00 | -0.42 | -0.27 | -0.30 |
| Volatiliteit (S1) | -0.01 | 0.24 | -0.42 | 1.00 | 0.53 | 0.57 |
| Breedte (S2) | 0.20 | 0.40 | -0.27 | 0.53 | 1.00 | 0.19 |
| Kredietstress (S3) | -0.15 | 0.08 | -0.30 | 0.57 | 0.19 | 1.00 |

## 7. Gewicht- en drempelsensitiviteit

Elk pijlergewicht ±50% (as opnieuw genormaliseerd), daarna het percentage dagen
waarop het regime verandert t.o.v. de basisconfiguratie. Slaat de conclusie om bij
een kleine wijziging, dan is het signaal te zwak om te rapporteren (design doc §5).

| As | pijler | −50% | +50% |
|---|---|---|---|
| fragility | Waardering (F1) | 18.5% | 19.0% |
| fragility | Kredietcondities (F2) | 15.4% | 10.7% |
| fragility | Positionering (F3) | 6.7% | 3.6% |
| stress | Volatiliteit (S1) | 2.0% | 2.5% |
| stress | Breedte (S2) | 1.3% | 1.0% |
| stress | Kredietstress (S3) | 3.7% | 1.4% |

Drempel (basis 60) verschoven:

| drempel | % dagen ander regime |
|---|---|
| 55 | 22.6% |
| 65 | 21.5% |

## 8. Stabiliteit en bekende zwakke punten

Regimewissels sinds 1990: **109** (3.1 per jaar); mediane regimeduur **38** handelsdagen, kortste 5.

Wat dit rapport laat zien, ook waar het tegenvalt:

- **COVID (2020) is niet voorspeld — per ontwerp.** Op de topdag stond het model op
  Kalm/Fragiele-rust-grens (fragiliteit 60, stress 45). Een exogene schok is ex ante
  onzichtbaar; de waarde zat in de omslag naar Schok binnen drie weken en in de matige
  fragiliteit die het snelle herstel verklaarde (design doc §2).
- **1998 (LTCM) leest als Storm.** De stress was echt (krediet, volatiliteit) en de
  waardering stond op recordniveau — de fragiliteit was dus geen vals signaal, maar de
  Fed-verlagingen kapten de episode af. Wie in 1998 voorzichtig werd, was twee jaar te
  vroeg voor de dotcom-top en miste die rally; de kalibratietabel (§4) prijst dit in.
- **2022 kende geen kredietstress.** De Baa-spread bleef kalm en equal-weight versloeg
  cap-weight; twee van de drie stresspijlers stonden daardoor laag terwijl de index
  -25% deed. Het trendfilter droeg de stress-as vrijwel alleen. Het regime bleef
  hangen rond de drempel — de Schmitt-marge (§7-config) houdt het label sindsdien
  vast tot het signaal echt wegzakt, maar de onderliggende zwakte blijft: een
  rente-gedreven daling zonder kredietstress scoort structureel lager dan een
  kredietcrisis van gelijke omvang.
- **De vroege jaren draaien op een smalle set.** Vóór 1996 bestaat de stress-as
  vrijwel alleen uit het trendfilter (§1); conclusies over 1990-1995 zijn daarom
  zwak onderbouwd.
- **Positionering mist zijn tweede been.** Top-10-concentratie heeft geen gratis
  historie en telt pas over tien jaar mee; F3 is tot die tijd alleen margin debt.
