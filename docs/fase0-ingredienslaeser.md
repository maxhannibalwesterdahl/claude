# Fase 0.1 – Dansk ingredienslæser: resultat

Dato: 28-09-2026. Mål fra [PLAN.md](PLAN.md): mindst 90 % af rigtige
ingredienslinjer giver korrekt mængde, enhed og vare.

**Resultat: 93,6 % i en blind måling. Målet er nået.** En AI-model er ikke
nødvendig for selve læsningen af linjerne.

## Hvad der måles

Hver linje skal give tre ting korrekt:

| Linje | Mængde | Enhed | Vare |
|---|---|---|---|
| `2 små, finthakkede fed hvidløg` | 2 | fed | hvidløg |
| `400 g hakket oksekød` | 400 | g | hakket oksekød |
| `2 dl grofthakket bredbladet persille` | 2 | dl | bredbladet persille |

Regel for **vare**: det, man køber. Forberedelse og størrelse fjernes
("finthakket", "store", "skyllede"), mens ord der gør varen til et andet
produkt beholdes ("hakket oksekød", "frossen broccoli", "røget paprika").
En linje tæller kun som korrekt, hvis alle tre dele er rigtige.

## Metode

Facit er skrevet i hånden for hver linje, før læseren blev kørt på den. For at
undgå, at læseren blot tilpasses testdataene, er der brugt tre adskilte sæt:

| Sæt | Kilde | Unikke linjer | Første kørsel | Status |
|---|---|---|---|---|
| 1 | Valdemarsro, 30 opskrifter | 289 | 100 %* | Brugt til at skrive læseren |
| 2 | Madens Verden + Arla, 30 opskrifter | 273 | **75,8 %** (blind) | Brugt til at rette læseren |
| 3 | Valdemarsro + Madens Verden + Arla, 32 nye opskrifter | 249 | **93,6 %** (blind) | Endelig måling |

\* Ikke et retvisende tal, da læseren er skrevet med disse linjer foran sig.

Efter den blinde måling af sæt 3 blev de generelle fejl rettet. Alle tre sæt
ligger nu over 98 %, men det tal er ikke blindt. **93,6 % er det tal, der skal
regnes med.** En ny blind måling kræver et nyt sæt.

Alle tre sæt køres som regressionstest (`backend/tests/test_parser_golden.py`),
så senere ændringer ikke gør læseren dårligere.

## Kendte fejl efter rettelser

| Linje | Læseren giver | Burde give |
|---|---|---|
| `150 g friske eller optøede, frosne brombær` | friske | brombær |
| `650 g små, faste kartofler, fx nix pille` | faste kartofler | kartofler |
| `4 skind- og benfri laksefileter` | skind- og benfri laksefileter | laksefileter |
| `lidt af det grønne fra porrer` | af det grønne | porrer |
| `top af fennikler` | top af fennikler | fennikler |

Den første er den eneste, hvor varen forsvinder helt. Resten giver et
varenavn, som matchningen i næste trin stadig kan genkende.

## Vigtigt forbehold

Læseren løser kun den første halvdel af problemet: at dele en linje op i
mængde, enhed og vare. **Den svære halvdel er ikke testet endnu:** at koble
varen til en fælles ingrediens, så "citron", "øko citron", "citronsaft" og
"friskpresset citronsaft" kan lægges sammen eller holdes adskilt korrekt, og så
Bilkas tilbudstekster kan matches. Det testes i fase 0.2 sammen med
Bilka-tilbuddene. Det er der, AI-spørgsmålet reelt afgøres.

## Andre fund

- **Spis Bedre kan ikke importeres.** 0 af 204 sider havde strukturerede
  opskriftsdata, selvom `recipe-scrapers` angiver siden som understøttet.
- **Arla virker** (15 af 15 og 10 af 10 opskrifter importeret).
- **Valdemarsro og Madens Verden virker** stabilt.
- Madens Verden skriver noter i parentes ("1 løg (hakket)"), Arla sætter
  forberedelse foran varen ("2 hakkede løg"). Valdemarsro bruger komma. Læseren
  håndterer alle tre.

## Filer

| Fil | Indhold |
|---|---|
| `backend/src/madplan/ingredients/model.py` | Fælles typer og `IngredientParser`-grænsefladen |
| `backend/src/madplan/ingredients/parser_da.py` | Den regelbaserede læser |
| `backend/tests/data/*_lines.tsv` | Facit for de tre sæt |
| `backend/tests/data/*.json` | Rå ingredienslinjer hentet fra siderne |
| `backend/scripts/fetch_testdata.py` | Henter nye testopskrifter |
| `backend/scripts/parser_report.py` | Udskriver træfsikkerhed og fejl for et sæt |
