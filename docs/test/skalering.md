# Skalering: 10, 50 og 200 familier

Rolle: senior udvikler (skalering). Gren `rolig`, commit `babc11e`. Alt er målt lokalt
på port 8105 med egen `DATA_DIR`. Intet er rørt i driften, prøven eller på eksterne sider
(eksterne kald er erstattet af en lokal mock). Ingen filer i repoet er ændret.
Hjælpescripts ligger uden for repoet i `/private/tmp/claude-501/sc/` (`seed.py`, `load.py`,
`run2.sh`, `pushlock.py`, `dup.py` m.fl.).

## 1. Kort konklusion

**Ikke klar til at åbne for flere familier – med forbehold.** Appen er i dag bygget til
**én** husstand: der er ingen husstands-/familietabel, og alle brugere deler opskrifter,
planer, indkøbsliste, ingrediensrettelser og telefoner til beskeder (S-01). Det er den
egentlige grænse; ingen mængde tuning ændrer den.

Selv hvis datamodellen rettes, knækker der tre ting længe før hardwaren er presset:
(1) en forbindelsespulje på 15 mod en trådpulje på 40 giver et stilstand i hele appen
ved få dusin samtidige forespørgsler (S-02), og 15 samtidige langsomme eksterne kald
(søgning/import) giver det samme (S-03); (2) påmindelsesjobbet sender alle beskeder til
alle telefoner og holder skrivelåsen under netværkskaldene, så alle skrivninger fejler
hver aften kl. 19 (S-04); (3) katalog-endpointet returnerer og indlæser alle opskrifter og
sprænger 512 MB ved ca. 8.000 opskrifter (S-05).

Rå kapacitet er ikke problemet: én proces klarer 100-140 forespørgsler/s på denne Mac, og
200 samtidigt aktive brugere med 4 s tænketid (ca. 43 req/s) gav p50 6 ms, p95 267 ms og
0,07 % fejl. SQLite i WAL-tilstand gav ingen "database is locked" under almindelig skrivning.
**Skift til Postgres er ikke nødvendigt endnu** (se afsnit 6).

## 2. Fund

| ID | Alvor | Titel | Sted |
|---|---|---|---|
| S-01 | Kritisk | Ingen husstande: alle brugere deler ét datasæt (og én planlægning) | `models.py` (alle tabeller), `api/plans.py:286`, `api/plans.py:311` |
| S-02 | Høj | Pulje-stilstand: 15 DB-forbindelser mod 40 tråde stopper hele appen under belastning | `db.py:20`, `api/deps.py:18-31` |
| S-03 | Høj | DB-forbindelsen holdes under eksterne kald (søgning, import, push-hello) | `api/recipes.py:174-180`, `api/recipes.py:299-319`, `api/deps.py:26-29` |
| S-04 | Kritisk | Påmindelser: alle telefoner får alle beskeder, og skrivelåsen holdes under netværkskald | `reminders.py:87-141` |
| S-05 | Høj | Ubegrænsede lister: `/api/recipes` (2,6 MB, 934 MB RAM ved 8.000 opskrifter), planer, egne varer | `api/recipes.py:140-156`, `api/plans.py:290`, `api/shopping.py:230`, `catalog.py:153` |
| S-06 | Mellem | Samtidige skrivninger giver 500 (UNIQUE-brud, check-then-insert) | `api/plans.py:354-355`, `api/shopping.py:336-338` |
| S-07 | Mellem | Flere workers er ikke sikre: dobbelte påmindelser, nøgle-race, opstarts-race, pr.-proces-grænser | `api/__init__.py:43`, `push.py:54-59`, `auth.py:69` |
| S-08 | Mellem | Ingen komprimering af API og statiske filer (10x for JSON) | `api/__init__.py`, `_mount_frontend` |
| S-09 | Mellem | Login-flaskehals: 98 af 100 samtidige logins får 429, 234 MB RAM-spids | `auth.py:25`, `api/auth_routes.py:20` |
| S-10 | Høj | Ingen kopi uden for maskinen (allerede kendt i drift.md) | `docs/drift.md` (Backup) |
| S-11 | Mellem | Overvågning/log: `INFO`-log forsvinder, helbredstjek tester ikke DB, ingen målinger | `Dockerfile` (HEALTHCHECK), `api/__init__.py:62`, `config.py` |
| S-12 | Lav | SQLite-indstillinger: `synchronous=FULL`, 2 MB cache, ingen eksplicit `busy_timeout` | `db.py:19-28` |
| S-13 | Lav | Manglende indekser på fremmednøgler/dato | `models.py` (`PlanMeal.recipe_id`, `.date`, `.leftover_from_id`, `WishlistItem.recipe_id`, `ShoppingExtra.ingredient_id`, `PlanLineState.line_id`) |
| S-14 | Lav | `upload_image` er `async` men kalder synkron DB og disk i event-løkken | `api/recipes.py:236-252` |
| S-15 | Lav | Billeder: importerede gemmes i original størrelse (op til 8 MB), ingen kvote/oprydning | `importer.py:download_image`, `api/recipes.py:236` |

## 3. Måleopsætning og forbehold

- Mac (8 kerner, 8 GB), loopback, load-generator og server på samme maskine. LXC'ens CPU og
  disk kendes ikke; tal i absolutte ms/rps skal læses som relative.
- Server som i Dockerfile: `uvicorn --factory madplan.api:create_app`, **1 worker** (ingen
  `--workers` i `CMD`). Uden `--proxy-headers`/Tailscale.
- Data: "lille" = 1 husstand (40 opskrifter, 6 planer), "stor" = 200 familiers data lagt ind
  i samme database (8.000 opskrifter, 88.000 ingredienslinjer, 1.600 planer, 11.200 retter,
  3.000 egne varer; 14 MB). 200 brugere i begge. Seedet direkte i DB.
- Brugerne bruger session-cookies lavet med `make_session`; login er målt for sig (S-09).
- "Nul tænketid" = hver virtuel bruger sender næste forespørgsel med det samme. Det er en
  stresstest og svarer til mange flere rigtige brugere. "Realistisk" = 4 s tænketid (±50 %).
- Blanding: læs = plan, indkøb, katalog, opskrift, forslag, ingredienser, `/`, health.
  Skriv = afkrydsning (sync), egen vare, sæt ret, ny opskrift. Mixed = 80 % læs / 20 % skriv.
- Alle virtuelle brugere skriver til samme plan (appen har kun én). Det overdriver
  race-fejlene i S-06 i forhold til 200 separate familier.
- Frisk server og frisk database pr. række. RSS = `ps`, spids over 0,5 s-målinger.

## 4. Måletal

### 4.1 Hele blandingen, lille datasæt, 1 worker, nul tænketid (stress)

| Brugere | Type | req/s | p50 ms | p95 ms | p99 ms | Fejl | RSS-spids |
|---|---|---|---|---|---|---|---|
| 10 | læs | 105,7 | 72 | 363 | 393 | 0 % | 126 MB |
| 50 | læs | 82,9 | 567 | 1.084 | 1.399 | 0 % | 128 MB |
| 200 | læs | 6,1 | 30.001 | 30.005 | 30.029 | 51,7 % | 132 MB |
| 10 | skriv | 91,2 | 73 | 304 | 412 | 3,2 % | 121 MB |
| 50 | skriv | 94,0 | 394 | 1.196 | 1.831 | 6,9 % | 126 MB |
| 200 | skriv | 12,9 | 362 | 30.005 | 30.012 | 44,2 % | 129 MB |
| 10 | mixed | 138,2 | 24 | 330 | 419 | 0,3 % | 127 MB |
| 50 | mixed | 123,8 | 324 | 839 | 1.159 | 0,5 % | 138 MB |
| 200 | mixed | 10,5 | 30.001 | 30.004 | 30.013 | 50,7 % | 127 MB |

Brugere tændes jævnt over 2/3/5 s. Ved 200 stopper appen (S-02), og klienten opgiver efter
30 s. Tomgang: 68 MB (lille) / 102 MB (stor). Opstart til sund: 1,0 s i begge.

### 4.2 Realistisk belastning (200 samtidigt aktive, 4 s tænketid, 30 s)

| Type | req/s | p50 ms | p95 ms | p99 ms | Fejl | RSS-spids |
|---|---|---|---|---|---|---|
| mixed | 42,5 | 6 | 267 | 613 | 0,07 % | 115 MB |
| læs | 44,9 | 7 | 36 | 64 | 0,06 % | 116 MB |

Den ene fejl i hver række er et 500 (skrive-race, S-06) hhv. en afbrudt forbindelse.

### 4.3 Pr. endpoint ved 50 brugere, mixed, nul tænketid

| Endpoint | n | p50 ms | p95 ms | p99 ms |
|---|---|---|---|---|
| GET /api/health | 46 | 24 | 76 | 81 |
| GET / (index.html) | 75 | 59 | 145 | 193 |
| GET /api/plans/current | 501 | 256 | 578 | 906 |
| GET /api/shopping | 441 | 337 | 694 | 1.160 |
| GET /api/recipes | 170 | 732 | 1.106 | 1.259 |
| GET /api/ingredients | 57 | 513 | 892 | 1.180 |
| GET /api/suggestions | 119 | 277 | 640 | 833 |
| POST /api/shopping/sync | 146 | 351 | 750 | 1.033 |
| POST /api/shopping/extras | 88 | 540 | 1.050 | 1.681 |
| PUT /api/plans/{id}/slots | 108 | 337 | 715 | 950 |
| POST /api/recipes | 30 | 452 | 768 | 968 |

Ventetid, ikke regnetid: se 4.4. Ved 10 brugere var p50 for `/api/shopping` 78 ms,
`/api/recipes` 348 ms og `/api/ingredients` 207 ms (samme kø, færre foran).

### 4.4 Pris pr. forespørgsel uden kø (én bruger, i proces)

| Endpoint | Forespørgsler | Tid lille | Tid stor | Svar lille | Svar stor | Gzip lille |
|---|---|---|---|---|---|---|
| /api/plans/current | 10 | 3,2 ms | 8,1 ms | 21 KB | 21 KB | 2,5 KB |
| /api/shopping | 12 | 3,4 ms | 52 ms | 24 KB | 24 KB | 2,3 KB |
| POST /api/shopping/sync | 13 | 3,4 ms | 49 ms | 24 KB | 24 KB | 2,3 KB |
| POST /api/shopping/extras | 17 | 7,3 ms | 49 ms | 25 KB | 25 KB | 2,3 KB |
| PUT /api/plans/{id}/slots | 19 | 5,8 ms | 6,0 ms | 18 KB | 18 KB | 2,5 KB |
| /api/recipes | 4 / 19 | 4,8 ms | **1.071 ms** | 13 KB | **2,6 MB** | 2,4 KB |
| /api/ingredients | 4 | 3,8 ms | 51 ms | 39 KB | 39 KB | 4,7 KB |
| /api/suggestions | 3 | 1,6 ms | 9,5 ms | 1,9 KB | 1,9 KB | 0,3 KB |
| /api/plans (liste) | 2 | 0,9 ms | 7,0 ms | 0,4 KB | **98 KB** | 3,9 KB |

Forespørgselstallet er konstant i antal retter (ingen klassisk N+1; `selectinload`
bruges konsekvent). På stor DB koster `/api/shopping` 52 ms mod 3 ms, fordi
`pick_current` og `plan_extras` læser alle planer og alle egne varer (S-05).
Hver afkrydsning på en indkøbstur er et `POST /shopping/sync` og bygger hele listen igen.
Under belastning er tiden i 4.3 næsten kun ventetid på den ene Python-tråd (GIL).

### 4.5 Stor datamængde (200 familiers data i én database), 1 worker, nul tænketid

| Brugere | Type | req/s | p50 ms | p95 ms | Fejl | RSS-spids |
|---|---|---|---|---|---|---|
| 1 | læs | 5,8 | 32 | 1.276 | 0 % | 319 MB |
| 10 | læs | 2,4 | 228 | 30.003 | 7,8 % (timeout på /api/recipes) | **934 MB** |
| 50 | læs | 4,3 | 4.191 | 30.002 | 6,7 % | **931 MB** |
| 10 | mixed | 2,2 | 416 | 30.002 | 5,1 % | 913 MB |
| 50 | mixed | 4,3 | 4.299 | 17.837 | 5,0 % | 922 MB |

Containerens `mem_limit: 512m` ville have dræbt processen (OOM) i alle rækker undtagen
den første. Ca. 25 KB RAM pr. opskrift pr. samtidig forespørgsel.

### 4.6 Flere workers (2 workers, lille datasæt, mixed, nul tænketid)

| Brugere | req/s | p50 ms | p95 ms | p99 ms | Fejl | RSS (samlet) |
|---|---|---|---|---|---|---|
| 10 | 350,2 | 11 | 115 | 214 | 0,3 % | 309 MB |
| 50 | 199,8 | 129 | 814 | 1.343 | 1,3 % | 292 MB |

2,5x gennemløb mod 1 worker, men to processer koster ca. 150 MB hver og skriver
sig oven i S-07.

### 4.7 Pulje-stilstand (S-02): 200 brugere, læs, nul tænketid, 5 s opstart

| Pulje (SQLAlchemy) | Fejl | req/s | p50 ms | p95 ms |
|---|---|---|---|---|
| Standard 5 + 10 (som koden) | 49-52 % (timeouts) | 6-11 | 30.000 | 30.005 |
| 60, ingen overløb | 37 % | 15,3 | 1.350 | 30.011 |
| 110, ingen overløb | 0 % | 72,8 | 2.533 | 4.170 |
| 300, ingen overløb | 0 % | 60,4 | 3.005 | 4.987 |

Mens stilstanden varer, svarer selv `/api/health` ikke (probe: 8 × 4 s timeout i træk;
appen var normal igen få sekunder efter, at lasten stoppede, uden genstart).

### 4.8 Andre målinger

| Måling | Resultat |
|---|---|
| 20 samtidige 12 s-søgninger (mock) → `/api/me` ventede | **9,2 s** (8 søgninger: 0 s) |
| Påmindelser: 40 telefoner × 5 påmindelser, mock-POST 0,15 s | 200 POST, 31,3 s; samtidig skrivning fejlede efter 5,2 s: `database is locked` |
| Påmindelser: 10 telefoner × 3, samme mock | 30 POST, 5,1 s |
| 2 samtidige planlæggere (som 2 workers), 1 påmindelse, 1 telefon | 2 beskeder sendt (3 af 3 forsøg) |
| 20 / 100 samtidige logins fra forskellige IP | 2 lykkedes, 18 / 98 fik 429; RSS-spids 234 MB |
| Argon2-tjek | 28 ms pr. login |
| JS+CSS+HTML i `frontend/build` | 79 filer, 299 KB rå, 102 KB gzip |

## 5. Detaljer pr. fund

### S-01 (Kritisk) Ingen husstande

- Sted: `models.py` – `Recipe`, `Plan`, `PlanMeal`, `ShoppingCheck`, `ShoppingExtra`, `Setting`,
  `PushSubscription` har hverken `household_id` eller `user_id`. `User` har kun brugernavn og kodeord.
  `pick_current` (`api/plans.py:286`) vælger *én* plan for alle; `create_plan` (`api/plans.py:311`)
  afviser en plan, der overlapper en andens (409); ingrediensrettelser og aliaser gælder alle.
- Genskab: opret to brugere (`madplan-admin create-user`), log ind som begge: begge ser samme
  `/api/plans/current`, `/api/recipes` og `/api/shopping`. Den ene kan slette den andens opskrift.
- Forventet: hver familie ser kun sit eget. Faktisk: ét fælles datasæt. (Datalæk er også i
  sikkerhedsrapportens område; her er pointen, at skaleringstal for "200 familier" kun kan måles
  som 200 brugere på ét datasæt, og at 200 familiers data i samme tabel giver S-05.)
- Forslag: `household` + `household_id` på alle ejede tabeller, brugere knyttet til en husstand,
  alle forespørgsler filtreret via en fælles afhængighed, sammensatte indeks `(household_id, …)`,
  `Setting`/aliaser/ingredienser pr. husstand (eller fælles katalog + pr.-husstand-rettelser),
  push-abonnementer pr. husstand. Opret husstande via `madplan-admin`.

### S-02 (Høj) Pulje-stilstand

- Sted: `db.py:20` (`create_engine` uden pulje-indstillinger, dvs. `QueuePool` 5 + 10 overløb,
  30 s timeout); `api/deps.py:18-31` (sessionen åbnes i en synkron afhængighed, og `current_user`
  henter brugeren med det samme, så forbindelsen er hentet fra puljen til hele forespørgslen er færdig).
  Alle ruter er synkrone (`def`) og kører i anyios trådpulje på 40 tråde.
- Mekanisme: forbindelsen frigives først, når afhængighedens oprydning har fået en tråd. Alle 40 tråde
  kan stå og vente på en forbindelse, som holdes af forespørgsler, der kun mangler en tråd for at blive
  lukket. Ingen kommer videre før puljens 30 s-timeout. Verificeret: en pulje på 60 hjælper ikke (37 %
  fejl), 110 og 300 gør (0 % fejl), jf. 4.7.
- Genskab: start serveren, send 200 samtidige `GET /api/plans/current` med gyldig cookie (se
  `load.py`, 200 brugere, 5 s opstart). Log: `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5
  overflow 10 reached` (477 gange i én kørsel). Mens det varer, svarer `/api/health` ikke.
  Docker-helbredstjek (`urlopen`, 5 s) melder "unhealthy", men compose genstarter ikke på det.
- Tærskel: 50 samtidige brugere gik godt, 200 gik ned. Typisk udløser: alle åbner appen samtidig
  (fx efter en besked kl. 19) eller S-03.
- Forslag: `create_engine(..., pool_size=64, max_overflow=0)` (SQLite-forbindelser er billige) og
  uvicorn `--limit-concurrency 100` (højst pulje-størrelsen), så overskydende får 503 i stedet for stilstand.
  Bedre: giv forbindelsen tilbage tidligt (`session.commit()`/`close()` efter `current_user`, åbn
  derefter igen når ruten skal bruge den), eller gør afhængigheden til én kontekst uden separat
  oprydningstråd. Hæv eventuelt trådgrænsen (anyio `CapacityLimiter`) i `lifespan`.
  (`--limit-concurrency` er ikke prøvet; pulje-størrelse er.)

### S-03 (Høj) Forbindelse holdt under eksterne kald

- Sted: `api/recipes.py:174-180` (`import_recipe`: `check_url` med `getaddrinfo` uden timeout,
  `importer.load` op til 15 s pr. forespørgsel og 5 omdirigeringer, `download_image` 15 s),
  `api/recipes.py:299-319` (`_external_hits`: søgning 15 s), `api/reminders.py` (`subscribe` med
  `hello`). `current_user` har allerede åbnet en transaktion (`api/deps.py:29`), så en pulje-plads
  og en tråd er optaget hele ventetiden.
- Genskab: kør en lokal mock, der svarer efter 12 s, peg `search_nemlig.SEARCH_URL` på den
  (kun i et scratch-script), send 20 samtidige `GET /api/search/nemlig?q=pastaN` og mål
  `/api/me` efter 3 s. Resultat: 9,2 s ventetid (8 søgninger: 0 s). Søgningerne selv: 12 s og 24 s.
- Forventet: en langsom ekstern side påvirker kun den, der søger. Faktisk: 15 samtidige langsomme
  kald fryser alle DB-forespørgsler. Søgning udløses mens man skriver, så få brugere kan nå det.
- Forslag: afslut transaktionen før det eksterne kald (`session.rollback()`/`close()` før `load`),
  åbn ny efter. Sæt en global grænse for samtidige eksterne kald (fx `threading.BoundedSemaphore(4)`
  → 429/503), korte timeouts (`httpx.Timeout(connect=3, read=8)`), og kør `getaddrinfo` med
  timeout. Overvej, at importen køres som baggrundsjob med status.

### S-04 (Kritisk) Påmindelser: alle-til-alle og skrivelås under netværk

- Sted: `reminders.py:87` (`targets` = alle `PushSubscription`), `reminders.py:133-141`
  (for hver påmindelse: send til *alle* telefoner, `session.flush()` efter hver, `commit` først til sidst).
  `push.py:send` bruger `httpx.post(timeout=15)` synkront.
- Mekanisme: `flush()` åbner en skrivetransaktion, som holdes gennem resten af løkken, mens der
  sendes til push-tjenesterne. SQLite har én skriver; alle andre skrivninger får "database is locked"
  efter 5 s (pysqlites standard-timeout) og bliver til 500.
- Genskab: `pushlock.py 40 5 0.15 8`: 40 telefoner, 5 påmindelser, mock-POST 0,15 s. 200 POST tager 31 s.
  En skrivning, der starter efter første flush, fejler efter 5,2 s med `OperationalError: database is locked`.
  Skrivninger, der starter før første flush, går igennem; derefter er alt låst.
- Skala: 200 familier × 2 telefoner = 400 abonnementer. 100 påmindelser kl. 19 → 40.000 POST
  ≈ 100 minutter ved 150 ms, med skrivelåsen holdt det meste af tiden. Samme kl. 7. Også datalæk:
  hver families påmindelsestekster sendes til alle andres telefoner.
- Forslag: vælg kun abonnementer for påmindelsens husstand (S-01); `commit()` efter hver påmindelse
  (eller marker `sent_on` i en kort transaktion *før/efter* netværkskaldet, aldrig under det);
  send parallelt med begrænset samtidighed (fx 8) og kort timeout (5 s); læg en overgrænse på
  beskeder pr. kørsel; log antal/varighed.

### S-05 (Høj) Ubegrænsede lister og indlæsning af hele tabeller

- `api/recipes.py:140-156` `list_recipes`: alle opskrifter + alle linjer + alle varer, ingen `limit`,
  ingen `?q`-sti i frontend (`ChooserSheet.svelte:57`, `opskrifter/+page.svelte:65` henter altid alt).
  8.000 opskrifter: 1,07 s, 2,6 MB (286 KB gzip), 319 MB RSS ved én bruger, 934 MB ved ti.
- `api/plans.py:290` `pick_current` henter *alle* planer for hver visning af plan/indkøb/sync;
  `api/plans.py:298` `list_plans` er ubegrænset (98 KB ved 1.600 planer).
- `api/shopping.py:230` `plan_extras` henter alle egne varer nogensinde (rækker slettes ikke);
  `/api/shopping` 3 ms → 52 ms på stor DB.
- `catalog.py:153` `learn_alias` og `catalog.py:168` `rematch_open_lines` læser alle ubekræftede/åbne
  ingredienslinjer i Python for hver bekræftelse/ny vare; `api/recipes.py:128` `_check_duplicate`
  scanner alle opskrifter med kilde-URL i Python ved hver oprettelse/import (opret: 16 → 61 ms på stor DB).
  `catalog.Catalog(session)` bygges pr. forespørgsel (4 forespørgsler, ca. 5 ms).
- Forventet: svartid og RAM uafhængig af den samlede datamængde. Faktisk: lineær i hele databasen.
- Forslag: `/api/recipes` skal give opskriftsoversigt uden `ingredients`-arrays, med `limit/offset`
  og serverside-søgning; filtrer pr. husstand (S-01); `pick_current` som to `LIMIT 1`-forespørgsler på
  indekseret `start_date`; ryd egne varer, der er krydset af for mere end N dage siden; `_check_duplicate`
  som `WHERE lower(rtrim(source_url,'/')) = :u` (eller gem en normaliseret kolonne med unikt indeks);
  cache `Catalog` i processen og ugyldiggør den ved ændring af varer/aliaser.

### S-06 (Mellem) Skrive-race giver 500

- Sted: `api/plans.py:354-355` (`set_slot`: slet + indsæt, `UNIQUE(plan_id,date,for_child)`),
  `api/shopping.py:336-338` (`sync`: `SELECT` derefter `INSERT` på `UNIQUE(plan_id,key)`).
- Genskab: 10 brugere sender `PUT /plans/{id}/slots` for samme plan: 30 af ca. 400 kald giver
  `sqlite3.IntegrityError: UNIQUE constraint failed: plan_meal.plan_id, plan_meal.date, plan_meal.for_child`;
  `POST /shopping/sync` på samme nøgle: 3 gange `shopping_check.plan_id, shopping_check.key`. Svar 500 (ikke 409/200).
- Realisme: to telefoner i samme husstand, der krydser samme vare af i butikken, eller sætter samme dag.
  Telefonen sender ventende ændringer igen, så det retter sig, men giver fejlbeskeder og 500 i logfilen.
- Under test sås derudover omkring 1 % afbrudte forbindelser (`ReadError`) ved skriv/mixed; årsagen er
  ikke fastslået (formodet: uvicorn lukker forbindelsen efter uhåndteret undtagelse).
- Forslag: `INSERT … ON CONFLICT DO UPDATE` for `ShoppingCheck` (`sqlalchemy.dialects.sqlite.insert`),
  fang `IntegrityError` i `set_slot` og prøv én gang igen, eller svar 409.

### S-07 (Mellem) Flere workers er ikke sikre

Dockerfilen kører én worker, så det rammer ikke i dag, men det er den første naturlige
skalering (2,5x i 4.6). Fundet:

- `api/__init__.py:43` starter `run_forever` i **hver** worker: 2 planlæggere sendte 2 beskeder for
  1 påmindelse (3 af 3 forsøg). Forslag: kræv påmindelsen med `UPDATE meal_reminder SET sent_on=:today
  WHERE id=:id AND (sent_on IS NULL OR sent_on!=:today)` og send kun, hvis `rowcount == 1`; eller kør
  planlæggeren som egen proces/container.
- `push.py:54-59` `load_key`: første kald fra to processer skriver samme `vapid.tmp` og den ene fejler
  (`FileNotFoundError` ved `os.replace`) — set i test. Kun første gang.
- Opstart: `migrate()` og `sync_seed()` kører i hver worker samtidig. Kør dem én gang før workers startes.
- `auth.py:69` `RateLimiter`, `HASH_GATE` og `search_*._cache` er pr. proces: 5 forsøg/min bliver 5 × antal workers;
  `_attempts` fjerner aldrig IP-nøgler, der ikke lykkes igen (lille lækage).

### S-08 (Mellem) Ingen komprimering

- `api/__init__.py` har ingen `GZipMiddleware`; `_mount_frontend` sender filer ukomprimerede. Målt:
  `/api/shopping` 23,7 KB → 2,3 KB gzip, `/api/ingredients` 38,6 KB → 4,7 KB, JS/CSS 299 KB → 102 KB.
  Tailscale Funnel komprimerer ikke (ikke efterprøvet her, ingen adgang til Funnel). Det spiller
  mest på mobildata i butikken (hver afkrydsning henter 24 KB).
- Cache: `_app/immutable/*` har `immutable`, `index.html` har `no-cache`, billeder `private,
  max-age=31536000, immutable` (uuid-navne) – i orden. API-svar har hverken `ETag` eller `Cache-Control`
  (`/api/ingredients` og `/api/meta` ændres sjældent og kunne få `ETag`/304).
- Forslag: `app.add_middleware(GZipMiddleware, minimum_size=500)`; `ETag` på `/api/ingredients`;
  eller en lille Caddy foran, som også leverer de statiske filer og billeder.

### S-09 (Mellem) Login-flaskehals

- `auth.py:25` `HASH_GATE = BoundedSemaphore(2)` og `api/auth_routes.py:20` `acquire(blocking=False)`:
  hvert argon2-tjek tager 28 ms, men et udbrud af samtidige logins afvises med 429 "Mange logger ind lige nu".
  Test: 100 samtidige logins fra 100 forskellige IP: 2 ok, 98 gange 429; 20 samtidige: 2 ok.
  RSS 109 → 234 MB (2 × 64 MB argon2 + trådene). Ved go-live, hvor mange familier logger ind
  samtidigt, vil nogle få "prøv igen om lidt". Sessioner varer 90 dage, så det er kun en indkøringsfase.
- Forslag: vent i op til 2-3 s på semaforen i stedet for at afvise straks (`acquire(timeout=3)`), eller
  sænk argon2-hukommelsen (`PasswordHasher(memory_cost=19456)` er OWASP-minimum) og tillad 3-4 samtidige.

### S-10 (Høj) Ingen kopi uden for maskinen

- `docs/drift.md` (Backup): nattekopi af databasen (14 dage) og vzdump af LXC (7 + 4) ligger alle på
  værtens ene NVMe. Dør disken, er alt væk – også andre familiers data. Gendannelse er beskrevet og
  afprøvet (30-09-2026), men kun mod samme disk.
- Forslag: nattekopi af `/data/backups` + `images/` til andet sted (restic/rclone til cloud-lager eller
  Macen); eller Litestream mod S3-kompatibelt lager for løbende replikering af SQLite (RPO sekunder).
  Tilføj en gendannelsesøvelse pr. kvartal og et alarmtjek, hvis nyeste kopi er over 26 timer gammel.
  `premigrate-*.db` ryddes ikke automatisk (db 14 MB/kopi ved 200 familier; tilføj oprydning).

### S-11 (Mellem) Overvågning og logning

- `api/__init__.py:62` `/api/health` returnerer altid `ok` uden at røre databasen; helbredstjek i
  Dockerfile kører hvert 60. sekund og genstarter intet. Under S-02 er det synkront og går i stå sammen med alt andet.
  Foreslå `SELECT 1` + skrivetest og at tælle åbne forbindelser; lad en ekstern ping (fx Uptime Kuma på
  en anden maskine, ikke på Funnel-adressen fra denne test) varsle ved fejl.
- Logning: `logging.getLogger("madplan")` har ingen handler. Python skriver kun `WARNING` og opefter
  (verificeret), så `log.info(...)` – "sendte N påmindelser", "genmatchede N linjer", "kopi før migration" –
  kommer aldrig i `docker compose logs`. Sæt `logging.basicConfig(level=INFO)` ved opstart.
- Logvolumen: `json-file` 10 MB × 3. Ved ca. 100 B pr. adgangslinje giver 40 req/s ca. 2,5 times historik
  (5 req/s ≈ 21 timer). Hæv til 50 MB × 5 eller send til fil/Loki. Ingen request-id, ingen svartid i loggen,
  ingen tællere (fejl, p95, pulje-brug, antal beskeder).
- Genstart: opstart til sund 1,0 s (også 14 MB DB); `restart: unless-stopped`; ved `mem_limit`-OOM genstarter
  Docker automatisk, men aktive forespørgsler tabes. Planlæggeren sender højst én gang pr. dag, og
  `mark_seen` forhindrer efterslæb, så en genstart kl. 19:00-19:01 kan fortsætte uden dubletter.
  Dog: en besked midt i en kørsel, der dræbes før `commit`, sendes igen (fordi `sent_on` først committes til sidst).

### S-12 (Lav) SQLite-indstillinger

- `db.py:19-28`: `journal_mode=WAL` og `foreign_keys=ON` sættes ved hver forbindelse (godt). Målt på
  forbindelsen: `synchronous=2` (FULL), `busy_timeout=5000` (pysqlite standard, ikke sat af koden),
  `cache_size=-2000` (2 MB), `wal_autocheckpoint=1000`.
- Forslag: `PRAGMA synchronous=NORMAL` (sikkert i WAL, undgår fsync pr. commit; i værste fald mistes
  den sidste transaktion ved strømsvigt, aldrig korruption), `PRAGMA busy_timeout=15000` eksplicit,
  `cache_size=-20000`, `temp_store=MEMORY`. Mac-disken siger intet om NVMe i LXC'en – mål fsync-tiden dér.

### S-13 (Lav) Manglende indekser

`EXPLAIN QUERY PLAN` på stor DB: `SCAN plan_meal` (forslag: gruppering på `recipe_id` og sletning af opskrift),
`SCAN wishlist_item`, `SCAN shopping_extra`, `SCAN meal_reminder` + opslag på `plan_meal.date`
(påmindelsesjobbet hvert minut). Mangler: `plan_meal(recipe_id)`, `plan_meal(date)`, `plan_meal(leftover_from_id)`,
`wishlist_item(recipe_id)`, `shopping_extra(ingredient_id)`, `plan_line_state(line_id)`. Ved 11.200 retter
koster hvert scan under 5 ms, så det er først relevant efter S-01 med sammensatte `(household_id, …)`-indeks.

### S-14 (Lav) `upload_image` blokerer event-løkken

`api/recipes.py:236-252` er `async def`, men kalder `load_recipe` (synkron DB, kan vente op til 30 s på
en forbindelse under S-02) og `write_bytes` på op til 8 MB direkte i event-løkken. Gør den til `def`
(trådpulje) eller brug `run_in_threadpool`.

### S-15 (Lav) Billeder

Egne uploads gøres mindre af telefonen (klientsiden). Importerede billeder gemmes i original størrelse op til
8 MB (`MAX_IMAGE`, nemlig-importen beder om bredde 1200, andre sider ikke). Ingen kvote pr. husstand, og
filer slettes ikke, hvis opskriften ikke gemmes efter download. `FileResponse` har `ETag`/`Last-Modified`, men
svarer aldrig 304; uvæsentligt, da filnavnet er uforanderligt og `immutable`. Forslag: resize/konvertér til
WebP ved import (Pillow), kvote pr. husstand, ugentlig oprydning af forældreløse filer.

## 6. Kapacitet og anbefaling

### Hvor mange familier kan det bære?

| Scenarie | Familier | Begrundelse |
|---|---|---|
| Som koden er i dag | **1** | S-01: ét delt datasæt |
| Husstande indført, ellers uændret kode | ca. 20-30 aktive | S-04 (påmindelser) og S-02/S-03 (stilstand) rammer først; belastningen i sig selv er ikke grænsen |
| Husstande + P1-P5 nedenfor, 1 worker | ca. 200 samtidigt aktive (testet: 43 req/s, p95 267 ms); flere hundrede registrerede | mættet ved 100-140 req/s på Macen |
| Samme + 2 workers (S-07 løst), 768 MB-1 GB | ca. 500+ registrerede | ca. 2,5x gennemløb; kræver rigtig LXC-CPU målt |

Antagelse: en familie er "aktiv" ca. hvert 4. s, mens appen er åben, og højst 20 % er aktive samtidigt
(aftenspids). Tallene er skøn ud fra målingerne på Mac og skal kontrolleres på LXC'en (CPU og disk kendes ikke).

### Hvad knækker først (rækkefølge)

1. Datamodellen (S-01) – blokerer alt.
2. Aftenspidsen kl. 19:00: påmindelsesløkken (S-04) låser skrivninger, og en samtidig åbning af appen (S-02) kan stoppe den.
3. Langsomme eksterne sider (S-03).
4. Hukommelse: kataloget (S-05) sprænger 512 MB ved ca. 8.000 opskrifter eller få samtidige katalog-kald ved 2.000-3.000.
5. CPU: én proces ca. 100-140 req/s (GIL; Python/pydantic-serialisering).
6. SQLite-skrivning først i sidste ende: ingen "database is locked" i 4.1-4.6 trods ca. 90-120 skrivende req/s.

### Prioriteret liste (hurtige gevinster først)

| # | Tiltag | Fund | Tid | Effekt |
|---|---|---|---|---|
| P1 | `pool_size=64, max_overflow=0`, `--limit-concurrency 100`, `PRAGMA busy_timeout`, `synchronous=NORMAL`, `GZipMiddleware` | S-02, S-08, S-12 | 1-2 t | Fjerner stilstand (0 % fejl ved 200 i test), 10x mindre svar |
| P2 | `logging.basicConfig(INFO)`, dybere `/api/health`, større logrotation | S-11 | 1 t | Synlighed |
| P3 | Påmindelser: commit før/efter hvert netværkskald, parallel send med grænse, kræv `sent_on` atomisk | S-04, S-07 | 0,5 dag | Ingen låse om aftenen, ingen dubletter |
| P4 | Slip DB-forbindelsen før eksterne kald, global grænse og korte timeouts på søg/import | S-03 | 0,5 dag | Langsomme sider påvirker kun den, der søger |
| P5 | `INSERT … ON CONFLICT` / retry på de to race-steder | S-06 | 2-3 t | Færre 500 |
| P6 | Kopi uden for maskinen (+ Litestream, hvis I vil have minutter i stedet for et døgn) | S-10 | 0,5 dag | Tab af disk er ikke længere tab af alt |
| P7 | Husstande (`household_id`, sammensatte indeks, push pr. husstand) | S-01, S-04, S-13 | 3-5 dage | **Krævet før andre familier** |
| P8 | Paginér og søg i kataloget serverside, uden ingrediensarrays; `LIMIT 1` i `pick_current`; ryd gamle egne varer; normaliseret URL-kolonne | S-05 | 1-2 dage | Flad RAM og svartid |
| P9 | Flere workers: planlægger som egen proces, migration før start, delt rate-limit i DB | S-07 | 1 dag | 2,5x gennemløb |
| P10 | `mem_limit` 768m-1g (hvis LXC'en har RAM), login-semafor med ventetid, billedkomprimering, indekser | S-09, S-13, S-15 | 1 dag | Margin |

P7 er det eneste, der *skal* være på plads før andre familier. P1-P6 er hurtige og kan tages i dag.

### Postgres?

Ikke nu. Begrundelse: målinger viser ingen skrivelåsproblemer ved ca. 90-120 skrivende req/s på én
proces, WAL er slået til, databasen er 14 MB ved 200 familier, og alle lås-problemer vi fandt
(S-04) skyldes at holde en transaktion åben under netværk, ikke SQLite selv. Postgres koster en
ekstra container, 150-300 MB RAM, drift af backup og en migrering af Alembic-filer (SQLite-specifik
tabelgenopbygning i `db.migrate`).

Skift giver mening, når mindst ét af disse er sandt:

- I vil køre mere end én app-container/vært (SQLite-filen kan ikke deles over netværk).
- "database is locked" optræder i logfilen efter P3 og P5, eller skrive-p95 holder sig over 200 ms.
- Vedvarende over ca. 50 skrivende req/s eller over ca. 500 aktive familier.
- I har brug for point-in-time-gendannelse eller rapportering ved siden af (så er Litestream for lidt).

Hvis I skifter: gør det samtidig med S-01, mens tabellerne alligevel får `household_id`, og brug
SQLAlchemy-forbindelse via URL (koden er allerede neutral, bortset fra `PRAGMA`, `copy_sqlite` og `db.migrate`).

## 7. Hvad der er tjekket og fundet i orden

- Ingen N+1: antallet af forespørgsler er konstant (10-19 pr. skrivning, 10-12 for plan/indkøb) uanset antal retter.
- WAL slået til, fremmednøgler på, backup via SQLites `backup()` (`db.copy_sqlite`) er sikker under kørsel.
- Ingen "database is locked" under 10/50 brugere skriv/mixed (kun under S-04). Skrivninger er korte (ms).
- Tilbud (`offers/`) bruges ikke af nogen route; kun scripts. Ingen eksterne kald i almindelige læse-/skriveruter.
- Importen tjekker URL mod lokale adresser, størrelsesgrænser på sider (5 MB) og billeder (8 MB), omdirigeringer valideres.
- Statik: `_app/immutable` har 1 års `immutable`, `index.html` `no-cache`; billeder `private, immutable`. Service worker
  cacher app-skallen, så gentagne besøg er billige. Frontenden poller ikke (kun `online`-event og ved handling).
- Hukommelse i tomgang 68-102 MB; spids ved 200 brugere 115-138 MB med lille datasæt (godt under 512 MB).
- Opstart 1,0 s; migration tager sikkerhedskopi først; docker-restart-politik og `deploy.sh` med tilbagerulning findes.
- Argon2-grænsen (2 samtidige) beskytter RAM, som tænkt (afvejning: S-09).
- Tråd-sikkerhed ved læsning: 2 workers + 50 brugere gav ingen låsefejl ud over S-06.

## 8. Hvad der ikke kunne testes

- Tailscale Funnel: latenstid, båndbredde, om den komprimerer, forbindelsesgrænser. Må ikke røres.
- LXC'ens CPU/disk/RAM og fsync-tid på NVMe; Mac-tal er relative. Real kapacitet kræver samme måling i LXC (kun lokalt, ikke mod driften).
- Rigtige push-tjenester (Apple/Google/Mozilla): latenstid og fejlkoder er simuleret med en mock (0,15 s pr. kald).
- Eksterne sider (Valdemarsro, nemlig, Tjek/Bilka): erstattet af lokal mock; selve import-flowet (`check_url` blokerer lokale adresser) er ikke kørt end-to-end.
- Rigtige browsere/PWA-adfærd og mobilnetværk (service worker, offline-kø ved mange ventende ændringer).
- Postgres: ikke prøvet; anbefalingen bygger på målingerne af SQLite og kodens struktur.
- Flere uafhængige husstande: umuligt i dag (S-01). 200 familier er målt som 200 brugere på ét datasæt og som
  200 familiers data i én database; plan-race (S-06) er derfor overdrevet i forhold til rigtig drift.
- Langtidsdrift (timer/dage): hukommelseslækage, WAL-vækst og logfyld er ikke målt over lang tid.
