# Flere familier – design

Status: gennemtænkt 30-09-2026, opdateret med jeres svar 01-10-2026. **Trin 1-2 i
afsnit 10 er bygget (16-10-2026):** datamodel, migration 0007, `CurrentHousehold`,
alle ruter afgrænset til familien og test-matrixen (`backend/tests/test_qa_adgang.py`).
Resten (admin-side, invitationer, vores samling, tilpasninger, historik) er ikke bygget.
Kun ejerfamilien (`recipe.created_by_household`) kan rette en fælles opskrift; andre får
404. Familiens note om barnet og basisvarer ligger i `household_recipe_note` og
`household_pantry`; `recipe.child_note` og `ingredient.pantry` er forældede kolonner
(pantry er startlisten til nye familier). Fælles varekatalog kan i dag endnu rettes af
alle (skal flyttes til systemadmin, trin 7). Krav fra jer:

- Flere familier (husstande) bruger samme app.
- **Opskrifterne deles** på tværs af familier.
- ~~**Rettelserne deles** på tværs~~ (01-10-2026). **Ændret 16-10-2026:** en
  familie kan aldrig ændre en anden families indkøbsliste. Rettelser af varer
  gælder kun familien selv; det fælles katalog ændres kun af systemadmin, der
  kan ophøje familiers valg til fælles standard (afsnit 3).

## 1. Hvad deles, og hvad er familiens eget?

Tommelfingerregel: **viden om mad deles, familiens hverdag gør ikke.**

| Data | Delt | Pr. familie | Hvorfor |
|---|---|---|---|
| Opskrifter (titel, linjer, fremgangsmåde, billede) | ✔ | | Kravet |
| Hovedingredienser (★) | ✔ | | Egenskab ved retten |
| Ingredienstabel (navn, afdeling, g/stk, g/dl) | ✔ | | Fælles viden |
| Fælles aliaser (katalog) | ✔ | | Fælles viden; kun systemadmin retter |
| **Foretrukne varer** ("mælk → letmælk") | | ✔ | Familier køber forskelligt |
| **Bekræftelser på linjer** (Tjek) | | ✔ | Én families valg må ikke ændre andres liste |
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
| `household_ingredient_pref` | household_id, fra-vare eller ord ("mælk"), til ingredient_id (letmælk) – lag 2 |
| `household_line_match` | household_id, line_id, ingredient_id (familiens bekræftelse på én linje) – lag 1 |
| `catalog_change` | hvem, hvornår, hvad (alias/vare), før, efter (historik til fortryd, kun systemadmin) |

Nye kolonner: `household_id` på `plan`, `shopping_extra`, `setting`
(`shopping_check`, `plan_meal` osv. hører til en plan og arver den).
`recipe.created_by_household` til ejerskab.

## 3. Hvilken vare er en linje? Tre lag pr. familie

Besluttet 16-10-2026. Viden om varer deles, men hver familie bestemmer selv,
hvad den køber. **Ingen familie kan ændre en anden families indkøbsliste.**

Når en linje skal kobles til en vare, vinder det øverste lag, der har et svar:

| # | Lag | Eksempel | Hvem ændrer |
|---|---|---|---|
| 1 | Familiens bekræftelse på én linje (`household_line_match`) | "I denne opskrift er fløden madlavningsfløde" | Familien selv |
| 2 | Familiens foretrukne vare (`household_ingredient_pref`) | "Når der står mælk, køber vi letmælk" | Familien selv, gælder alle opskrifter |
| 3 | Opskriftens kobling (sat af ejeren, afsnit 4) | Linjen "2 dl mælk" er koblet til mælk | Ejerfamilien |
| 4 | Fælles katalog og matcher (aliaser) | "piskefløde" = fløde 38 % | Kun systemadmin |

Eksempel: opskriften siger "2 dl mælk". Familie A har "mælk → letmælk", familie
B har "mælk → sødmælk". Samme opskrift, forskellige indkøbslister. En familie
uden præference får lag 3/4.

**Når en familie retter en kobling** (i Tjek, på indkøbslisten eller i en
opskrift), spørges der: *"Kun i denne opskrift"* (lag 1) eller *"Altid hos os"*
(lag 2). Rettelsen skrives aldrig i det fælles katalog.

**Det fælles katalog bliver bedre via systemadmin:** admin-siden viser
familiernes valg samlet ("3 familier kobler 'hakkede tomater' til hakkede
tomater på dåse"). Systemadmin kan med ét tryk gøre et valg til fælles alias,
så nye familier får glæde af det. Alle ændringer i kataloget skrives i
`catalog_change` og kan fortrydes.

Bevares fra i dag: en bekræftelse kan ikke gøre en anden vares navn til alias
("løg" bekræftet som rødløg gælder kun den ene linje).

## 4. Redigering af delte opskrifter: ejeren retter, alle andre tilpasser

Besluttet 16-10-2026 (erstatter 01-10-2026, hvor alle kunne rette den fælles
opskrift). "Kopiér og tilpas" er stadig fravalgt: det ville give mange næsten
ens opskrifter.

**Kun ejeren retter den fælles opskrift.** Ejer er den familie, der lagde
opskriften ind (`recipe.created_by_household`). Kun ejerfamiliens medlemmer kan
rette titel, ingredienslinjer, mængder, fremgangsmåde, billede, stjerner og
varekobling. Det, ejeren retter, ses af alle. Hver ændring gemmes i
`recipe_version` (hvem, hvornår, hele den gamle udgave) og kan fortrydes af
ejeren og af systemadmin. Planer peger på linjernes id'er, der bevares ved
redigering, så "har hjemme" og rester overlever rettelser.

**Alle andre familier kan kun lave tilpasninger.** De gemmes for sig og lægges
oven på den fælles opskrift, kun for den familie. Den fælles opskrift ændres
aldrig af en anden familie, og alle andre ser den uændret. Backend afviser
rettelser fra andre end ejeren med 404 (testes i matrixen, afsnit 6). I
frontend vises "Rediger" kun for ejeren; andre ser "Tilpas til os".

**Familiens tilpasninger (kun for den familie, lagt oven på):**

| Tilpasning | Eksempel |
|---|---|
| Note om barnet | "Tag barnets portion fra før chili" |
| Egen note | "Vi bruger halv chili" |
| Spring en linje over | "Vi bruger ikke svampe" (kommer ikke på listen) |
| Egen mængde på en linje | 600 g hakket oksekød i stedet for 500 g |
| Egen vare på en linje | "fløde" er madlavningsfløde hos os (lag 1, afsnit 3) |
| Ekstra linje | "1 dåse majs" |

Ser en anden familie en stavefejl, kan de skrive den som egen note. Senere kan
der komme en "Foreslå rettelse"-knap, som ejeren godkender. Ikke i første omgang.

Ejer ejerfamilien ikke længere (familien slettes), overgår ejerskabet til
systemadmin.

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
- Fælles katalog: familiernes varevalg samlet, med "Gør til fælles alias", og
  historik med fortryd (afsnit 3).
- Seneste rettelser af opskrifter (ejerens) med fortryd (afsnit 4).
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
5. Alle nuværende opskrifter lægges i familie 1's samling, og familie 1 bliver
   ejer af dem (`created_by_household = 1`). Linjernes nuværende koblinger og
   bekræftelser bliver dermed opskriftens kobling (lag 3), og eksisterende
   aliaser bliver det fælles katalog (lag 4). Familie 1 får ingen lag 1-2 fra
   start; den ser alt præcis som i dag.

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
| 7 | Varer i tre lag pr. familie ("kun her"/"altid hos os"), katalog på admin-siden, historik og fortryd | 1-1½ dag |
| 8 | Backup uden for huset, dataudlevering/sletning, privatlivstekst | ½-1 dag |
| Senere | Tilmelding med godkendelse på admin-siden | 1 dag |

**I alt ca. 7-9 dage** (uden tilmelding). Trin 1-2 er forudsætningen og bør
laves samlet. Trin 8 skal være færdigt, før familie nr. 2 kommer ind.

## 11. Beslutninger

| Spørgsmål | Svar (01-10-2026) |
|---|---|
| Redigering af delte opskrifter | ~~Alle kan rette med historik (01-10-2026)~~. **16-10-2026:** kun ejerfamilien retter den fælles opskrift; alle andre kan kun lave tilpasninger, der kun gælder dem selv (afsnit 4) |
| Hvem bestemmer, hvilken vare en linje er? | **16-10-2026:** hver familie for sig (lag 1-2, afsnit 3). Fælles katalog kun via systemadmin |
| Kan en bruger være i flere familier? | Nej, præcis én |
| Hvem opretter familier? | Kun systemadmin via admin-side. Senere tilmelding med godkendelse |
| Backup uden for huset | Ikke nu. Krav, før familie nr. 2 kommer ind |
