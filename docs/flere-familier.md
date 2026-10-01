# Flere familier – design (ikke bygget)

Status: gennemtænkt 30-09-2026, opdateret med jeres svar 01-10-2026. Ikke bygget. Krav fra jer:

- Flere familier (husstande) bruger samme app.
- **Opskrifterne deles** på tværs af familier.
- **Rettelserne deles** på tværs: når én familie retter, hvilken vare en
  ingredienslinje er ("fløde" = piskefløde), får alle glæde af det.

## 1. Hvad deles, og hvad er familiens eget?

Tommelfingerregel: **viden om mad deles, familiens hverdag gør ikke.**

| Data | Delt | Pr. familie | Hvorfor |
|---|---|---|---|
| Opskrifter (titel, linjer, fremgangsmåde, billede) | ✔ | | Kravet |
| Hovedingredienser (★) | ✔ | | Egenskab ved retten |
| Ingredienstabel (navn, afdeling, g/stk, g/dl) | ✔ | | Fælles viden |
| Aliaser og bekræftelser (Tjek) | ✔ | | Kravet: rettelser deles |
| **Basisvarer** (salt, olie, mel …) | | ✔ | Familier har forskellige skabe. Kan ikke være fælles |
| **Note om barnet** på en opskrift | | ✔ | Børn er forskellige ("uden chili" gælder kun jer) |
| **Vores samling** (hvilke retter vi bruger, favoritter) | | ✔ | 500 fælles retter må ikke drukne de 30, I laver |
| Madplaner, ønskeliste, har hjemme, rester | | ✔ | Hverdagen |
| Indkøbsliste, afkrydsning, egne varer | | ✔ | Hverdagen |
| Afdelingernes rækkefølge | | ✔ | Forskellige butikker |

To ting, der i dag ligger på fælles tabeller, skal flyttes ud pr. familie:
`ingredient.pantry` (basisvare) og `recipe.child_note`.

## 2. Datamodel

Nye tabeller:

| Tabel | Indhold |
|---|---|
| `household` | id, navn, oprettet |
| `household_member` | household_id, user_id, rolle (`admin`/`medlem`) |
| `invite` | household_id, token (tilfældig, 32 bytes), udløber, brugt af |
| `household_recipe` | household_id, recipe_id, favorit, tilføjet (= "vores samling") |
| `household_recipe_note` | household_id, recipe_id, child_note |
| `household_pantry` | household_id, ingredient_id (basisvarer pr. familie) |
| `catalog_change` | hvem, hvornår, hvad (alias/vare/linje), før, efter (historik til fortryd) |

Nye kolonner: `household_id` på `plan`, `shopping_extra`, `setting`
(`shopping_check`, `plan_meal` osv. hører til en plan og arver den).
`recipe.created_by_household` til ejerskab.

## 3. Delte rettelser: risikoen og hvordan den styres

At rettelser deles er det, der gør den fælles opskriftsbase god (én familie
tjekker "fløde", alle har gavn af det). Men én forkert rettelse rammer alle.
Beskyttelser, i prioriteret rækkefølge:

1. **Allerede bygget (30-09-2026):** en bekræftelse kan ikke gøre en anden vares
   navn til alias ("løg" bekræftet som rødløg gælder kun den ene linje), og der
   læres kun af nye bekræftelser.
2. **Historik og fortryd:** hver ændring af aliaser, varer og linjekoblinger
   skrives i `catalog_change`. Under Varer vises "Seneste rettelser (af hvem)"
   med en fortryd-knap.
3. **Uenighed synliggøres, ikke overskrives i stilhed:** bekræfter familie B et
   varenavn anderledes end familie A's alias, gemmes B's valg på linjen, og
   aliaset markeres "uenighed" i Tjek i stedet for at skifte for alle.
4. **Familiens egne bekræftede linjer røres aldrig** af andres rettelser (som i
   dag: `bekræftet` er brugerens valg).

## 4. Redigering af delte opskrifter: fælles opskrift og familiens tilpasninger

Besluttet 01-10-2026. "Kopiér og tilpas" er fravalgt: hver stavefejl eller lille
ændring ville give en ny, næsten ens opskrift.

**Fælles (alle kan rette, med historik):** titel, ingredienslinjer, mængder,
fremgangsmåde, billede, stjerner og varekobling. Rettelser gavner alle. Hver
ændring gemmes i `recipe_version` (hvem, hvornår, hele den gamle udgave) og kan
fortrydes. Planer peger på linjernes id'er, der bevares ved redigering, så "har
hjemme" og rester overlever rettelser.

**Familiens tilpasninger (kun for den familie, lagt oven på):**

| Tilpasning | Eksempel |
|---|---|
| Note om barnet | "Tag barnets portion fra før chili" |
| Egen note | "Vi bruger halv chili" |
| Spring en linje over | "Vi bruger ikke svampe" (kommer ikke på listen) |
| Egen mængde på en linje | 600 g hakket oksekød i stedet for 500 g |
| Ekstra linje | "1 dåse majs" |

Tabel: `household_recipe_adjustment` (household_id, recipe_id, line_id eller
ny linje, type, værdi). Dagssiden, ingredienserne i Planlæg og indkøbslisten
bruger familiens tilpasninger. Opskriftssiden viser "Jeres udgave" med de
fælles linjer + tilpasninger, og "Vis original" for den fælles.

Sletning: en opskrift, der bruges i en anden families plan eller samling,
kan ikke slettes, kun fjernes fra "vores samling". Importerer to familier samme
ret fra Valdemarsro, genbruges den (samme `source_url`).

## 5. Login, invitationer og roller

- **Én bruger hører til præcis én familie** (besluttet 01-10-2026).
- **Kun systemadmin opretter familier** (besluttet 01-10-2026). Det kræver en
  **admin-side** (se afsnit 5a). På sigt: man kan skrive sig op, og admin
  godkender.
- **Invitation til en familie:** familiens egen admin laver et link (gyldigt 7
  dage); den nye opretter selv brugernavn og kodeord.

### 5a. Admin-side (systemadmin)

`user.is_system_admin` (i dag: Max). Siden `/admin`, kun for systemadmin:

- Liste over familier: navn, medlemmer, antal opskrifter i samlingen, seneste aktivitet.
- **Opret familie** → giver et invitationslink til familiens første admin.
- Nulstil kodeord for en bruger, deaktivér en bruger eller familie.
- Seneste rettelser i den fælles opskrifts- og varebase med fortryd (afsnit 3),
  så misbrug eller fejl kan rulles tilbage.
- Senere: **ansøgninger** fra folk, der har skrevet sig op, med godkend/afvis.

Ruterne under `/api/admin/*` kræver `is_system_admin`. Test-matrixen (afsnit 6)
tjekker, at almindelige brugere får 404.
- **Glemt kodeord:** familiens admin kan nulstille et medlem i appen. Du kan
  nulstille en admin fra kommandolinjen. Ingen mail i første omgang (kræver
  mailserver).
- Brugernavne skal være unikke på tværs af familier.

## 6. Adgangskontrol (det vigtigste at få rigtigt)

- Én fælles afhængighed `CurrentHousehold` i API'et, som alle ruter med familiens
  data bruger, og som filtrerer alle opslag på `household_id`.
- Findes noget, men tilhører det en anden familie, svares **404** (ikke 403),
  så man ikke kan gætte sig til andres data.
- **Test-matrix:** en test opretter to familier og kalder *hvert* endpoint med
  den anden families id'er og forventer 404. Nye endpoints skal med i matrixen.

## 7. Søgning

Standard i vælgeren: **vores samling** først, derefter **alle delte opskrifter**,
derefter **Valdemarsro**. Importerer en familie en Valdemarsro-ret, som en anden
familie allerede har, genbruges den (samme `source_url`) og lægges bare i
samlingen.

## 8. Drift og ansvar

- **Backup uden for huset bliver et krav, før familie nr. 2 kommer ind**
  (besluttet 01-10-2026: ikke nødvendig, så længe det kun er jer).
- **Persondata** er minimale (brugernavne, madplaner), men en familie skal kunne
  få sine data udleveret og slettet. Kort privatlivstekst i appen.
- SQLite holder fint til nogle dusin familier. Billeder: grænse pr. familie.
- Samme Funnel-adresse kan bruges. Et eget domæne er pænere, men ikke nødvendigt.

## 9. Migration af jeres data

1. Opret familie 1 og læg jeres to brugere i den som admin.
2. Alle nuværende planer, egne varer og indstillinger får `household_id = 1`.
3. `ingredient.pantry` kopieres til `household_pantry` for familie 1. Nye
   familier får startlistens basisvarer.
4. `recipe.child_note` flyttes til `household_recipe_note` for familie 1.
5. Alle nuværende opskrifter lægges i familie 1's samling.

Migrationen tager en kopi først og kører uden fremmednøgler (som i dag).

## 10. Omfang og rækkefølge

| Trin | Indhold | Tid |
|---|---|---|
| 1 | Datamodel, migration, `CurrentHousehold` | 1 dag |
| 2 | Alle ruter afgrænset til familien + test-matrix | 1-2 dage |
| 3 | Admin-side: familier, opret med invitation, nulstil kodeord | 1 dag |
| 4 | Invitationer i familien, familieindstillinger (medlemmer, navn) | ½ dag |
| 5 | Vores samling, basisvarer og barnenote pr. familie | 1 dag |
| 6 | Familiens tilpasninger (spring over, egen mængde, ekstra linje, note) | 1-1½ dag |
| 7 | Historik og fortryd for opskrifter og rettelser, "uenighed" i Tjek | 1 dag |
| 8 | Backup uden for huset, dataudlevering/sletning, privatlivstekst | ½-1 dag |
| Senere | Tilmelding med godkendelse på admin-siden | 1 dag |

**I alt ca. 7-9 dage** (uden tilmelding). Trin 1-2 er forudsætningen og bør
laves samlet. Trin 8 skal være færdigt, før familie nr. 2 kommer ind.

## 11. Beslutninger

| Spørgsmål | Svar (01-10-2026) |
|---|---|
| Redigering af delte opskrifter | Fælles opskrift, alle kan rette med historik; personlige ændringer som familiens tilpasninger (afsnit 4) |
| Kan en bruger være i flere familier? | Nej, præcis én |
| Hvem opretter familier? | Kun systemadmin via admin-side. Senere tilmelding med godkendelse |
| Backup uden for huset | Ikke nu. Krav, før familie nr. 2 kommer ind |
