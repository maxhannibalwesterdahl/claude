# Fase 0.2 – Bilka-tilbud og kobling af varer: resultat

Dato: 28-09-2026. Formål: afgøre, om tilbud kan hentes, og om varenavne fra
opskrifter og tilbud kan kobles til én fælles vare uden AI.

## Kort konklusion

| Del | Resultat | Gratis udgave god nok? |
|---|---|---|
| Hente Bilka-tilbud | Virker. 191 madvaretilbud i uge 40 | Ja |
| Koble opskrifternes varenavne | 94-95 % rigtige på kendte varer, 0 farlige fejl efter rettelse | **Ja** |
| Koble tilbud til varer | 70 % af relevante tilbud findes, men 41 % kræver bekræftelse, og 30 % findes ikke | **Kun delvist** |

Anbefaling: Første version bruger den gratis udgave overalt. Tilbud vises som
forslag, som brugeren bekræfter eller afviser, og bekræftelserne gemmes. Tjek
tallene igen i fase 4, og overvej først AI for **tilbudsmatchningen**. Det er
den eneste del, hvor gratis-udgaven er tydeligt svag. Med ~190 madvaretilbud om
ugen vil det koste få øre pr. uge.

## 1. Hentning af tilbud

- Tjek-API'et virker uden nøgle. Bilka havde **644 tilbud** fordelt på fem
  aviser: mad, nonfood, halloween og to elektronikaviser.
- Tjek har **ingen varekategorier** (feltet er tomt). Men Bilka udgiver
  madvarer i en separat avis ("Bilka Food Uge 40 – Fødevarer & Personlig
  Pleje"). Kun den bruges: **191 tilbud**.
- Uden filteret blev halloween-græskar til "hokkaido græskar". Filteret ramte
  først også "Bilka **Nonfood**", fordi ordet indeholder "food". Rettet til hele
  ord.
- Af de 191 er **32 relevante** for madlavning ud fra ingredienstabellen. Resten
  er kaffe, slik, øl, pålæg, færdigretter og personlig pleje.
- **Mange tilbud er familie- og storpakninger**: kyllingebryst 2,6 kg til
  179 kr., mørbrad 5 kg, pølser 2 kg. For en husstand på 2+1 er et tilbud ikke
  automatisk en god handel. Kilopris kan beregnes (Tjek leverer mængde og
  enhed), men pakningsstørrelse bør vises tydeligt.

## 2. Kobling af opskrifternes varenavne

Ingredienstabellen har 244 varer med afdeling, basisvare-markering og aliaser.
Koblingen prøver i rækkefølge: alias, bøjning ("avocadoer", "pastinakker",
"fennikler"), frisk/tørret efter enhed ("1 tsk timian" = tørret), og til sidst
to usikre regler (første ord fjernet, sidste del af et sammensat ord).

| Måling | Varer | Korrekt | Usikker, rigtig | Usikker, forkert | Ikke fundet | Farlig fejl |
|---|---|---|---|---|---|---|
| Sæt 3, blind for koblingen* | 189 | 93,7 % | 1,1 % | 2,1 % | 3,2 % | **0** |
| Sæt 4, helt nye varenavne | 51 | 62,7 % | 21,6 % | 5,9 % | 7,8 % | **1** (2 %) |

\* Tabellen er skrevet efter at have set varerne i sæt 3. Sæt 3 måler derfor om
koblingen er rigtig, ikke hvor mange varer tabellen kender. Sæt 4 måler det.

- **Farlig fejl** = forkert vare markeret sikker, så den kommer direkte på
  listen. Den ene var "1 tsk koriander" → frisk koriander. Rettet: koriander
  følger nu samme frisk/tørret-regel som timian.
- Sæt 4 (20 nye opskrifter, 223 linjer) indeholdt kun 51 varenavne, der ikke
  var set før. **89 % af alle linjer fik en vare, 83 % sikkert.** Ordforrådet
  mættes hurtigt, og brugerens rettelser gemmes som nye aliaser.

## 3. Kobling af tilbud

Tilbudsteksten deles i alternativer ("X, Y eller Z"). Sammensatte ord udfoldes
("okse-, grise- eller grise/kalvekød" → oksekød, grisekød), blandingsprodukter
("okse/grisekød") springes over, og mærkenavne fjernes ved at prøve teksten uden
de forreste ord.

| Måling (37 forventede match) | Første kørsel, blind | Efter to rettelser |
|---|---|---|
| Rigtigt og sikkert | 23 | 11 |
| Rigtigt, men usikkert | 3 | 15 |
| Ikke fundet | 11 | 11 |
| **Forkert og sikkert** | **8** | **1** |
| Forkert, men usikkert | 9 | 10 |

De to rettelser efter den blinde kørsel: kun madvareavisen, og match fundet
efter fjernede ord er usikre ("varmrøget laks" → "laks" er forkert, "Dava
frilandsæg" → "æg" er rigtigt, og det kan reglerne ikke se forskel på).

**Hvorfor 30 % ikke findes:** Bilkas ordforråd mangler i tabellen:
"entrecotes", "oksespidsbryst", "tykstegsbøffer", "frilandsæg",
"lakseportioner", "plantedrik", "tun 3-pak". Det samme gælder "røget laks" skrevet
som "kold- eller varmrøget laks". Mange tilbud går igen fra uge til uge, så
bekræftelser og nye aliaser vil hjælpe. Men det kræver brugerens tid i starten.

## Filer

| Fil | Indhold |
|---|---|
| `backend/src/madplan/offers/tjek.py` | Henter tilbud, filtrerer til madvareavisen |
| `backend/src/madplan/offers/match.py` | Tilbud → varer |
| `backend/src/madplan/ingredients/matcher.py` | Varenavn → vare (`IngredientMatcher`) |
| `backend/src/madplan/ingredients/data/ingredienser.txt` | Ingredienstabellen |
| `backend/tests/data/blind_matches.tsv`, `cover_matches.tsv` | Facit for kobling |
| `backend/tests/data/bilka_offer_matches.tsv` | Facit for tilbud, uge 40 |
| `backend/tests/data/bilka_offers_2026-09-28.json` | Alle 644 tilbud (første, blinde kørsel) |
| `backend/tests/data/bilka_food_offers_2026-09-28.json` | De 191 madvaretilbud |
| `backend/scripts/matcher_report.py`, `offer_report.py` | Målescripts |
