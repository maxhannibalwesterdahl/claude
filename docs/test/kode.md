# Kodereview før go-live (senior udvikler, kode)

Gren `rolig` (commit babc11e). Backend og frontend er læst igennem med fokus på det, der er nyt i `rolig` i forhold til `main` (påmindelser/push, uge-per-indkøb, forslag, nemlig-import, hele det nye Svelte-UI). Intet er ændret i eksisterende filer.

## 1. Kort konklusion

**Ikke klar til go-live med flere familier. Klar til fortsat drift for én husstand.**

Det afgørende fund er F-01: der findes slet ingen familie/husstand i datamodellen eller API'et. `docs/flere-familier.md` er markeret "ikke bygget", og koden stemmer: alle forespørgsler er globale, og `CurrentUser` giver kun et brugerobjekt. Hver bruger ser og kan ændre alle planer, indkøbslister, påmindelser og beskeder. Det er ikke en fejl i det enkelte endpoint, men en manglende arkitekturdel, så den skal bygges, ikke lappes.

Uden for flerfamilie-emnet er koden i god stand: 211 tests grønne, 1 advarsel (Starlette/httpx), `svelte-check` 0 fejl og 0 advarsler, ingen skema-drift mellem `models.py` og migrationerne, og migrationerne kører på en driftslignende database uden datatab. Jeg fandt dog et par rigtige fejl (F-05 og F-06), som kan ødelægge en indkøbsliste eller give 500, og nogle driftsrisici i påmindelsesjobbet (F-07).

Antal fund: **1 kritisk, 4 høje, 6 mellem, 14 lave**.

## 2. Fund

| ID | Alvor | Titel | Sted |
|---|---|---|---|
| F-01 | Kritisk | Ingen familie/husstand i datamodel og adgangskontrol | `models.py:21`, `api/deps.py:26-35`, alle ruter |
| F-02 | Høj | Påmindelser sendes til alle telefoner uanset familie | `reminders.py:87-141`, `api/reminders.py:114-140` |
| F-03 | Høj | Fælles tabeller, der skal være pr. familie (basisvarer, afdelingsrækkefølge, beskedadresse, aliaser) | `models.py:40`, `api/shopping.py:165-169,447-455`, `api/reminders.py:127-133`, `catalog.py:124-159` |
| F-04 | Høj | Indkøbslisten gemmes på telefonen uden bruger, og logud rydder den ikke | `frontend/src/lib/shopping.svelte.ts:8,48-53`, `routes/rydop/+page.svelte:86-89` |
| F-05 | Høj | `Infinity` (og negative) mængder i en opskrift giver 500 på indkøbslisten | `api/schemas.py:33-34`, `api/recipes.py:104`, `shopping.py:62,96,101` |
| F-06 | Mellem | Afkrydsning med `e:²` giver 500 og blokerer hele synkroniseringen | `api/shopping.py:324` |
| F-07 | Mellem | Påmindelsesjobbet holder skrivelås under netværkskald | `reminders.py:133-142` |
| F-08 | Mellem | Samtidige ændringer giver 500 (unik-begrænsning) eller overlappende planer | `api/plans.py:313-321,344-357` |
| F-09 | Mellem | Manglende indekser på fremmednøgler og dato | `models.py:139,143,147,168,205,239` |
| F-10 | Mellem | Ingen test af adgangsmatrix, familieadskillelse, sommertid/årsskifte eller frontend | `backend/tests/`, `frontend/` |
| F-11 | Mellem | Forbindelsespulje (5+10) mindre end trådpuljen (40) | `db.py:20`, `api/__init__.py` |
| F-12 | Lav | `upload_image` er `async`, men laver blokerende databasekald | `api/recipes.py:235-253` |
| F-13 | Lav | `load_plan` kalder `expire_all()` og kan i fremtiden kassere ikke-flushede ændringer | `api/plans.py:216-218` |
| F-14 | Lav | Planer ved yderkanten af datoområdet giver 500 | `api/plans.py:312` |
| F-15 | Lav | Tom `item` og urimelige mængder accepteres på ingredienslinjer | `api/recipes.py:96-108`, `api/schemas.py:27-40` |
| F-16 | Lav | Ventende afkrydsninger droppes aldrig ved varig serverfejl | `frontend/src/lib/shopping.svelte.ts:112-121` |
| F-17 | Lav | `?til=` på login kan bruges til omdirigering med `/\` (bør verificeres i browser) | `frontend/src/routes/login/+page.svelte:16-17` |
| F-18 | Lav | Notifikationsknappen "Klaret" fejler lydløst; offline-skal kun for `/` | `frontend/src/service-worker.ts:76-89,40` |
| F-19 | Lav | Duplikeret logik og konstanter | se detaljer |
| F-20 | Lav | Død kode: `offers/`, `get_settings`-genimport, ældre redirect-ruter | se detaljer |
| F-21 | Lav | For store filer/funktioner | se detaljer |
| F-22 | Lav | Små driftspunkter: backupmappe, rate-limiter, opstart/nedlukning, migration ved flere workers | `cli.py:86`, `auth.py:73-96`, `api/__init__.py:29-46` |
| F-23 | Lav | Løse ender i API-adfærd: `multiplier` på rester, tavs ignorering af `text`, abonnement kan overtages, "Origin" bliver fælles adresse | `api/plans.py:363-369`, `api/reminders.py:120-133` |
| F-24 | Lav | Ugyldige nøgler fylder `shopping_check`; kolonnelængde passer ikke til API-grænsen | `models.py:224`, `api/shopping.py:104,327-340` |
| F-25 | Lav | Enhedens tidszone bruges til "i dag" i klienten; serveren bruger Europe/Copenhagen | `frontend/src/lib/dates.ts:18` |

## 3. Detaljer pr. fund

### F-01 (Kritisk): Ingen familie/husstand
- **Faktisk:** `User` har ingen relation til en husstand (`models.py:21-29`). Der er ingen tabeller `household`, `household_member` osv. `grep -i "household|husstand|family"` i `backend/src` giver ingen kodetræf. `current_user` returnerer kun `User` (`api/deps.py:26-32`). Alle slag er globale: `select(Plan)` (`plans.py:290,298,313`), `session.get(PlanMeal, id)` (`plans.py:234`), `session.get(ShoppingExtra, id)` (`shopping.py:324,393,408`), `session.get(MealReminder, id)` (`api/reminders.py:56`), `session.get(WishlistItem, id)` (`plans.py:457`). Ca. 60 opslag i `api/*.py` og `reminders.py`, og ingen af dem har et filter.
- **Genskabelse:** opret to brugere med `madplan-admin create-user`, log ind som den ene, læg en plan, log ind som den anden: den ser planen, indkøbslisten og kan slette den (`DELETE /api/plans/{id}`).
- **Forventet:** som i `docs/flere-familier.md` §6: én fælles afhængighed `CurrentHousehold`, som alle ruter med familiedata bruger, 404 ved andres id'er, og en test-matrix.
- **Forslag (mønster, så det er centraliseret og robust):**
  1. Tabeller `household` og `household_member` (eller `user.household_id`, da en bruger kun hører til én familie), `household_id NOT NULL` på `plan`, `shopping_extra`, `setting` (nøgle bliver `(household_id, key)`), og `push_subscription` via brugeren.
  2. Én afhængighed `CurrentHousehold` i `deps.py`, og tilgangsfunktioner, der *altid* tager husstanden med: `get_plan(session, hh, id)`, `get_meal(session, hh, id)` (join via `Plan.household_id`), `get_extra`, `get_reminder`, `get_wish`. Ruterne må ikke bruge `session.get(Model, id)` direkte for familiedata. En enkel regel i review og en lille test, der scanner `api/*.py` efter `session.get(` på familiemodeller, holder mønsteret.
  3. `Plan`-nære børn (meal, line_state, reminder, wish, check) arver familien via planen. Opslag skal ske med join/EXISTS, ikke i to trin uden filter.
  4. Test-matrix (to familier, hvert endpoint kaldt med den andres id'er, forventer 404). Kør den automatisk over `app.routes`, så nye endpoints ikke kan glemmes.
- Opskrifter, ingredienstabel og aliaser er bevidst fælles; her skal der i stedet være historik/fortryd (design §3) før andre familier får lov at rette.

### F-02 (Høj): Påmindelser går til alle telefoner
`reminders.py:87-88` (`targets()` = alle `PushSubscription`) og `send_due` (`:111-141`) sender hver påmindelse til hver tilmeldt telefon. `PushSubscription.user_id` bliver aldrig brugt til at filtrere (`models.py:268`). Teksten ("Husk: …", retten og datoen) fra familie A havner dermed hos familie B. Forslag: `targets(session, household_id)` og send kun til abonnenter i påmindelsens husstand. Når der er mange telefoner bliver løkken `påmindelser × telefoner` også dyr (se F-07).

### F-03 (Høj): Fælles tabeller, der burde være pr. familie
- `Ingredient.pantry` (`models.py:40`): familie A's "basisvare" ændrer familie B's liste (`shopping.py:259`). Design §1 siger, at den skal flyttes til `household_pantry`.
- `Setting` "departments" (`shopping.py:165-169`, `447-455`): afdelingsrækkefølgen er fælles; én families omrokering ændrer alle.
- `Setting` "push_subject" (`api/reminders.py:127-133`): overskrives af enhver bruger med værdien af `Origin`-headeren.
- `learn_alias` (`catalog.py:124-159`) rækker globalt: én families bekræftelse omskriver alle ubekræftede linjer i alle opskrifter. Det er bevidst (delte rettelser), men uden `catalog_change`/fortryd (design §3) kan én forkert rettelse ramme alle. Det er også en vektor for misbrug mellem familier.
- `Recipe.child_note` (`models.py:74`) er fælles; design §1 siger pr. familie.

### F-04 (Høj): Lokal lagring følger ikke brugeren
`shopping.svelte.ts:8` bruger én nøgle `madplan.indkob.v1`, og `logout()` (`routes/rydop/+page.svelte:86-89`) rydder den ikke. Konstruktøren læser den ved opstart (`:48-53`). Efter at en anden bruger logger ind på samme telefon vises den forrige brugers liste (offline-kopien), og de ventende afkrydsninger (med forrige brugers `plan_id`) sendes til det nye login og rammer planer med samme id. Med flere familier kan en delt tablet/telefon dermed lække og forvirre data. Forslag: gem under en nøgle med bruger-id (fra `/api/me`), ryd `shopping` (data, pending) og lokalstorage ved logud og når `/me` svarer med et andet id; evt. `caches.delete` for API-svar, hvis de senere gemmes.

### F-05 (Høj): `Infinity`/negative mængder ødelægger indkøbslisten
- **Genskabelse (verificeret med TestClient):** `POST /api/recipes` med `{"title":"x","ingredients":[{"raw":"x","item":"mel","quantity":Infinity,"match_status":"ingen"}]}` giver 201. Læg opskriften på en dag; `GET /api/shopping?plan_id=…` giver **500** (`OverflowError` i `math.ceil(inf)` fra `shopping.combine`, `shopping.py:62,96,101`). Samme med `1e308` ganget med 2 (×2 giver `inf`). `NaN` gemmes som NULL (SQLite). `-5` gemmes og giver negative mængder.
- **Faktisk/forventet:** Mængder skal være endelige og ≥ 0. Her er `LineIn.quantity`/`quantity_max` blot `float | None` (`schemas.py:33-34`).
- **Konsekvens:** Kun den ene uge er ramt, men listen kan ikke åbnes, før opskriften rettes. Når opskrifter deles mellem familier, rammer fejlen alle, der har den på en plan. Selve `/plans/{id}` returnerer sandsynligvis også en fejl, fordi `inf` ikke kan skrives som JSON (ikke testet).
- **Forslag:** `Field(None, ge=0, allow_inf_nan=False, le=1e6)` på begge felter; samme for `ExtraIn` hvis der kommer mængder; og gør `combine` robust (`math.isfinite`) som sikkerhedsnet.

### F-06 (Mellem): `e:²` giver 500 i sync
`api/shopping.py:324`: `ch.key[2:].isdigit()` er sand for tegn som `²` og `٣`, men `int()` kaster `ValueError` for fx `²`. Verificeret: `POST /api/shopping/sync` med `{"changes":[{"key":"e:²","checked":true,"ts":1}]}` giver 500, og hele pakken (også gyldige ændringer) afvises. Telefonen sender ventende ændringer igen for evigt (se F-16), så én dårlig række blokerer for alle. Appen selv laver ikke sådanne nøgler, så det er en robusthedsfejl, men docstringen i `SyncIn` (`:117-119`) lover det modsatte. Forslag: `ch.key[2:].isascii() and ch.key[2:].isdigit()`, eller `try/except ValueError`, eller regex `^e:\d{1,18}$` i `Change`.

### F-07 (Mellem): `send_due` holder skrivelås under netværkskald
`reminders.py:133-142`: for hver påmindelse sendes der HTTP (`timeout=15`, `push.py:134`), og derefter `r.sent_on = today` + `session.flush()`. Fra første flush holder transaktionen SQLites skrivelås til `commit()` til sidst. Mens næste telefon svarer langsomt (op til 15 s hver), kan andre brugeres skrivninger få "database is locked" (Pythons standard-timeout er 5 s), altså 500. Det sker kun, når der er noget at sende, men giver periodiske fejl hvert minut omkring kl. 19 og 07, når der er mange familier. Forslag: send først (kun læsning), saml resultaterne, og skriv `sent_on`/sletning af døde abonnementer i en kort transaktion til sidst; eller commit efter hver afsendelse. Overvej også `PRAGMA busy_timeout` og at sende parallelt/med kø.

### F-08 (Mellem): Samtidige ændringer
- `set_slot` (`plans.py:354-357`): to enheder, der lægger en ret på samme dag samtidigt, kan begge slette og indsætte; den anden `commit()` rammer `UNIQUE(plan_id, date, for_child)` og giver 500 i stedet for en pæn besked. Samme i `move_meal`, `distribute_wishes` og `place_wish`.
- `create_plan` (`plans.py:313-321`): overlaptjek er kun i Python, uden databasebegrænsning, så to samtidige POST kan oprette overlappende uger.
- Forslag: fang `IntegrityError` centralt (exception handler → 409 "Prøv igen") og lad `create_plan` tage `BEGIN IMMEDIATE` (eller engangsnøgle i db) før tjekket.

### F-09 (Mellem): Manglende indekser
SQLite opretter ikke indeks på fremmednøgler automatisk. Uden indeks scanner `ON DELETE CASCADE/SET NULL` hele børnetabellen:
`plan_line_state.line_id` (`models.py:168`, rammes ved hver opskriftsredigering, der fjerner en linje), `plan_meal.recipe_id` (`:143`, ved sletning af opskrift og i `suggestions` group by), `plan_meal.leftover_from_id` (`:147`), `wishlist_item.recipe_id` (`:205`), `shopping_extra.ingredient_id` (`:239`). Desuden bruges `plan_meal.date` i påmindelsesjobbets forespørgsel hvert minut (`reminders.py:116-127`) uden indeks (`:139`). Med 200 familier bliver det tusindvis af rækker, og påmindelsesjobbet læser hele tabellen minut for minut. Forslag: ny migration med disse indekser (`render_as_batch` er allerede slået til).

### F-10 (Mellem): Testdækning af kritiske stier
Der er 211 tests, men:
- Adgangskontrol testes kun på to endpoints (`tests/test_api.py:13-15`). Der er ingen parametriseret test, der kalder *alle* ruter uden cookie.
- Ingen test af familieadskillelse (følger af F-01).
- Ingen test af sommertid/årsskifte: planer, der spænder over årsskifte (fx 28/12–3/1), `slot_due` om natten ved skift til/fra sommertid, og `local_today` ved 23:30 UTC. `reminders`-testene monkeypatcher uret.
- Ingen migrationstest fra gamle revisioner med data (kun `test_migrations.py` med en syntetisk migration). Jeg har selv kørt en opgradering fra 8c2e5d71a0f4 med data i `meal_reminder` og `shopping_extra`: ingen datatab, `foreign_key_check` tom.
- Ingen test af ugyldige tal (F-05) eller `e:²` (F-06).
- Frontend har ingen tests overhovedet (kun `svelte-check`; CI kører check/build). Logikken i `shopping.svelte.ts` (offline-kø, rækkefølge, ur-forskel) og `ordered.ts` fortjener enhedstests (vitest).

### F-11 (Mellem): Pulje- og trådstørrelser
`db.py:20` bruger `create_engine(...)` uden pulje-indstillinger. For SQLite-fil bruger SQLAlchemy 2 `QueuePool` (5 + 10 overløb, 30 s ventetid), mens FastAPI/anyio kører synkrone ruter i op til 40 tråde, og nogle ruter holder en session i 15 s (import, `subscribe` med `hello`). Under belastning venter anmodninger 30 s og ender i `TimeoutError`. Forslag: sæt `pool_size`/`max_overflow` efter trådpuljen, `PRAGMA busy_timeout` og kort `timeout` på eksterne kald; flyt eksterne kald ud af åbne sessioner.

### F-12 (Lav): `async def` med blokerende arbejde
`upload_image` (`recipes.py:235-253`) er `async`, men `load_recipe`, `commit`, `write_bytes` og `unlink` blokerer event-loopen (de andre ruter er `def` og kører i trådpulje). Gør ruten `def` og læs filen med `file.file.read(MAX_UPLOAD + 1)`.

### F-13 (Lav): `expire_all()` i `load_plan`
`plans.py:217` kalder `session.expire_all()` hver gang. I dag er alt flushed først (fx `place_wish` flusher inden `set_slot`), så det virker, men en fremtidig ændring, der ikke flushes før `load_plan`, mister ændringen uden fejl. Og det giver ekstra forespørgsler. Forslag: fjern kaldet (brug `populate_existing()`), eller kommenter kontrakten.

### F-14 (Lav): Datoer ved yderkanten
`POST /api/plans` med `start_date: "9999-12-31"` giver `OverflowError` → 500 (`plans.py:312`). Valider fx 2020–2100 i `PlanIn`. Ellers er datohåndteringen i orden: planer gemmes som rene datoer, `_end()` regnes med `timedelta`, og klienten bruger `Math.round` i `daysBetween`, så sommertid ikke påvirker dagtælling. Årsskifte er ikke noget problem (der bruges ikke ISO-uge-numre).

### F-15 (Lav): Linjevalidering
`apply_lines` (`recipes.py:96-108`) accepterer `item=""` (NOT NULL i db, men tom streng er lovlig) og gemmer mængder uden grænser (se F-05). `position` følger indekset i den rå liste, så springede tomme linjer giver huller (harmløst). Når `item is None` genparses linjen og mister en tidligere "bekræftet" (kun et problem, hvis en klient sender `id` uden `item`). Forslag: `min_length=1` på `item`, og bevar `match_status` ved genparse, hvis `raw` er uændret.

### F-16 (Lav): Poison pill i klientens kø
`shopping.svelte.ts:112-117`: ved alle fejl andre end 0/401 sættes status til `error`, og `pending` bliver. Er fejlen varig (500 som F-06, 422 ved >2000 ændringer, `SyncIn.changes max_length`), sendes de samme ændringer hvert 20. sekund for evigt, og ingen nye afkrydsninger når serveren. Forslag: ved 4xx (undtagen 401/429) drop de ventende, eller send dem én og én, og vis en rolig besked.

### F-17 (Lav): Omdirigering efter login
`login/+page.svelte:16-17`: `target.startsWith('/') && !target.startsWith('//')` stopper ikke `/\evil.example`, som browsere læser som `//evil.example`. SvelteKit `goto` med en adresse på et andet domæne foretager en almindelig navigation. Bør verificeres i browser; sikkerhedsagenten kan bekræfte. Forslag: `new URL(target, location.origin).origin === location.origin` og brug `pathname + search`.

### F-18 (Lav): Service worker
- `notificationclick` med "Klaret" (`service-worker.ts:80-88`) ignorerer svaret: offline eller udløbet session betyder, at påmindelsen ikke krydses af, og brugeren får ingen besked. Forslag: tjek `res.ok`, vis ellers en ny notifikation ("Det gik ikke, åbn appen").
- Offline-skallen er kun `/` (`:13,40`); en dyb adresse (fx `/indkob`) hentes fra net ved navigation og falder tilbage til `/`, hvilket virker, fordi SvelteKit router klient-side. Indkøbslisten ligger i `localStorage`. Det er i orden, men ikke testet på telefon.
- `install` bruger `cache.addAll`: fejler én fil, installeres den nye version ikke (atomisk), og den gamle bliver. Det er ønskværdigt, men giver ingen fejlmelding.

### F-19 (Lav): Duplikeret logik
- `_end(plan)`: `plans.py:153` og `shopping.py:149`.
- Linjens række-nøgle `i:<id>`/`t:<nøgle>`: `shopping.py:206` og `:430`.
- URL-normalisering: `recipes.py:132` og `_norm_url` `:295`.
- Standardtider `19:00`/`07:00`: `reminders.py:23-24` og `frontend/src/lib/uge/Reminders.svelte:20-21` (kommentaren siger "skal passe til backend"). `/api/meta` kunne levere dem.
- Datoformat/`parseDate` ligger fint samlet i `dates.ts`, men afdelinger er hårdkodet i `matcher.py:21` og hentes af klienten via `/meta` (fint).
- `types.ts` er håndskrevet. Jeg har sammenlignet alle grænseflader med `schemas.py`, `plans.py`, `shopping.py` og fandt **ingen forskelle** (felter, nullbarhed, literals). `Line.id: number | null` afviger bevidst (nye linjer i editoren). Forslag: generér typer fra OpenAPI (`openapi_url=None` er slået fra i drift, så brug `app.openapi()` i et script) for at undgå fremtidig drift.

### F-20 (Lav): Død kode
- `backend/src/madplan/offers/` (Tjek-tilbud) bruges ikke af appen, kun af `scripts/` og `tests/test_offers.py`. Hold den, men markér det i README, eller flyt til `scripts`.
- `api/__init__.py:17` genimporterer `get_settings` med `noqa`; `CurrentUser` bruges i `_images`.
- Redirect-ruter `routes/planlaeg|tjek|varer|dag/[dato]/+page.ts` er bevidste (gamle links), men hører til en ryd-op efter nogle måneder.
- `uge/week.svelte.ts:12` `lowerFirst` m.fl. er i brug; ingen ubrugte eksporter fundet i stikprøve.

### F-21 (Lav): For store filer
`api/plans.py` (551 linjer: skemaer, opbygning og ruter), `api/shopping.py` (455), `RecipeEditor.svelte` (513), `routes/indkob/+page.svelte` (508). Forslag: `api/schemas`-moduler pr. område og en `services`-del (`plan_out`, `build`) uden FastAPI, så adgangskontrol (F-01) kan lægges ét sted.

### F-22 (Lav): Drift
- `cli.backup` sletter kun `madplan-*.db` (`cli.py:86`); `premigrate-*.db` fra `db.py:77` ryddes aldrig. `--keep 0` sletter ingenting (`[:-0]`).
- `RateLimiter._attempts` (`auth.py:73`) vokser med hver ny IP, og `succeeded()` (`:90-96`) fjerner det *seneste* forsøg, som ved samtidige forsøg fra samme IP kan være en andens. Under Funnel er IP'en den, Tailscale sætter.
- `lifespan` annullerer baggrundsopgaven uden at afvente den (`api/__init__.py:43-46`); en igangværende `send_due` i en tråd kan køre mod en lukket engine. `migrate()` kører i hver workerproces, hvis der startes flere (kun én i dag).
- Logud er kun klientside (`auth_routes.py:41-43`, cookien er stateløs 90 dage); en kopieret cookie virker efter logud. Det kan løses med `session_version += 1` ved logud.

### F-23 (Lav): API-adfærd
- `update_meal` (`plans.py:363-369`) tillader `multiplier` på `rester` (sat til 1.0 i `set_slot`), og `text` ignoreres tavst for ikke-fritekst.
- `subscribe` (`api/reminders.py:120-124`) lader en bruger overtage et eksisterende `endpoint` (flytter rækken til sig). Endpoints er uforudsigelige, så risikoen er lille; med familier bør den kræve samme bruger/husstand.
- `Origin` bliver fælles `push_subject` (se F-03).

### F-24 (Lav): `shopping_check`-rækker
`Change.key` tillader 300 tegn (`shopping.py:104`), kolonnen er `String(120)` (`models.py:224`); SQLite håndhæver det ikke, men en senere flytning gør. `sync` accepterer vilkårlige nøgler med præfikset `i:`/`t:` (op til 2000 pr. kald, `:327-340`), så man kan fylde tabellen med skrald; tjek at nøglen findes i listen, eller begræns formatet (`^[it]:`+rimeligt).

### F-25 (Lav): Tidszone i klienten
`dates.ts:18` `today()` bruger enhedens lokale dato, mens serveren bruger `Europe/Copenhagen` (`config.py:16`). Kun et problem, hvis telefonen er i en anden tidszone (rejse). Alle datoer sendes med `?today=`, så serveren følger klienten for planer, men påmindelser (`reminders.py`) følger serveren. Acceptabelt for danske familier; dokumentér det.

## 4. Hvad der er tjekket og fundet i orden

- **Tests og værktøj:** `cd backend && .venv/bin/pytest -q`: 211 bestået, 1 advarsel (Starlette: `httpx` i `TestClient` er udfaset, anbefaler `httpx2`). `cd frontend && npm run check`: 267 filer, 0 fejl, 0 advarsler.
- **Migrationer:** `compare_metadata` mellem migrationerne (kørt til head) og `models.py` med `compare_type` og `compare_server_default` giver **ingen forskelle**. En opgradering fra revision `8c2e5d71a0f4` med rækker i `plan_meal`, `meal_reminder` og `shopping_extra` gav `True`, ingen tabte rækker, `PRAGMA foreign_key_check` tom, nye kolonner med standardværdier (`again_on = 1`). `db.migrate` slår fremmednøgler fra under migrationen, kontrollerer bagefter og tager en kopi først (`db.py:56-92`). Cascade/SET NULL er konsistente med modellerne.
- **Sessioner/transaktioner:** `get_session` bruger `with sessionmaker()`, så sessionen lukkes og ruller tilbage ved fejl (`db.py:100-102`). Fejl midt i `place_wish` efter `delete` ruller korrekt tilbage (intet commit). Påmindelsesjobbet bruger egen session pr. kørsel og fanger undtagelser i `run_forever`, så løkken ikke dør (`reminders.py:146-155`). Genmatch ved opstart kan ikke forhindre opstart (`api/__init__.py:33-41`).
- **Datoer og tid:** servertid regnes i Europe/Copenhagen (`config.py:16-24`); `slot_due` og `mark_seen` sammenligner lokal tid; sommertid giver ingen dobbelt- eller udeblevne sendinger ud over det forventede (sendes højst én gang pr. dag via `sent_on`). Klientens `daysBetween` er sikker over sommertid. Uger over årsskifte er ikke et problem (rene datoer).
- **Last write wins:** `ts` begrænses til nu + 60 s, og ugyldige ændringer springes over uden at blokere resten (`shopping.py:315-321`), bortset fra F-06.
- **Frontend-state:** `sequencer` (`ordered.ts`) forhindrer, at gamle svar overskriver nyere; `Week.load` håndterer 404 for slettede uger; `lav`-siden ignorerer svar til en dag, man er gået fra; `shopping.sync` skelner uge-skift undervejs; `$state.snapshot` bruges, når pending sendes. Ingen `{@html}` i koden (XSS-fladen er lille). `api()` håndterer 204, ikke-JSON svar, netværksfejl (status 0) og 401 med omdirigering.
- **Service worker:** versionerede cache-navne, rydning af gamle caches, API-kald caches ikke, `skipWaiting`/`claim`, push med `try/catch` om JSON.
- **Push/krypto:** `allowed_endpoint` holder serveren til kendte tjenester; VAPID-nøgle skrives atomisk (`push.py:46-60`); `Status 404/410` fjerner døde abonnementer.
- **Import:** `check_url` blokerer ikke-globale adresser og tjekker hver omdirigering (`importer.py:80-96`), størrelsesgrænser på side og billede, billednavn er uuid.
- **Frontend-typer** matcher API-skemaerne (se F-19).

## 5. Hvad der ikke kunne testes

- Selve familieadskillelsen, fordi den ikke findes (F-01).
- Rigtig Web Push til Apple/Google/Mozilla (kræver ægte abonnement); kun kryptering og signatur er dækket af eksisterende tests.
- Service worker, offline-adfærd, iOS-hjemmeskærm og tastaturopførsel er kun læst, ikke kørt på enhed. F-17 bør bekræftes i en rigtig browser.
- `npm run build` er ikke kørt, fordi det ville overskrive `frontend/build`, som de andre agenter bruger.
- Last- og samtidighedsproblemer (F-07, F-08, F-11) er udledt af koden, ikke målt; skaleringsagenten dækker måling.
- Eksterne tjenester (Valdemarsro, nemlig.com, Tjek) er ikke kaldt.
