# QA og test: rapport

Gren `rolig`, testet 16-10-2026 mod en lokal kopi på port 8106 (egen `DATA_DIR`, to testbrugere). Serveren er stoppet. Ingen eksisterende filer er ændret, ingen commits.

## 1. Kort konklusion

**Ikke klar til at åbne for flere familier. Klar til fortsat brug i én familie, med små forbehold.**

- Funktionelt er den eksisterende app solid: login, opskrifter, ugeplan, indkøbsliste, husk-påmindelser og lav mad virker, også ved årsskifte, uge 53, skudår og sommertid. Ingen datatab fundet.
- **Blokerende (K1):** Flere familier er ikke bygget. Der findes ingen `household`-tabel, og alle brugere deler alle data. Det gælder opskrifter, planer, indkøb, afdelingsrækkefølge, basisvarer og barnenote. En bruger kan også slette eller ændre en andens ting. Så længe det er sådan, må ingen anden familie lukkes ind.
- Fire mellem-fund: 500-fejl ved mængden "1/0", 500-fejl når to telefoner krydser samme nye vare af samtidigt, tom opskriftstitel kan gemmes, og Bilka-tilbud er kun et bibliotek (ikke koblet til API eller skærme).
- Regression: `pytest` 211 gamle + 107 nye grønne, 15 nye `xfail` (afslører fund). `npm run check`: 0 fejl, 0 advarsler.

## 2. Fund

| ID | Alvor | Titel | Sted |
|---|---|---|---|
| K1 | Kritisk | Ingen adskillelse mellem familier (flere familier ikke bygget) | `models.py` (ingen household), alle `api/*.py`, `api/deps.py:30` |
| M1 | Mellem | Mængde "1/0" i en ingredienslinje giver 500 | `ingredients/parser_da.py:110` |
| M2 | Mellem | Samtidig første afkrydsning af samme vare giver 500 | `api/shopping.py:336-338` |
| M3 | Mellem | Opskrift med titel af kun mellemrum gemmes med tom titel | `api/schemas.py:58`, `api/recipes.py:_fill_recipe` |
| M4 | Mellem | Bilka-tilbud/Tjek ikke koblet til API eller UI (fase 4 ikke bygget) | `offers/`, `docs/PLAN.md` fase 4 |
| L1 | Lav | Planstart `9999-12-30` giver 500; år 0001 accepteres | `api/plans.py:311` (`PlanIn`) |
| L2 | Lav | Dobbeltklik på "Tilføj" giver to ens egne varer | `api/shopping.py:346` |
| L3 | Lav | Negative/enorme mængder accepteres; "-5 g mel" og "1e308 g" læses som tekst | `schemas.py:LineIn`, `parser_da.py` |
| L4 | Lav | `GET /api/recipes?q=`: "æble" finder ikke "Æblegrød"; `%` matcher alt | `api/recipes.py:140-142` |
| L5 | Lav | Korte trin uden punktum behandles som overskrifter i Lav mad | `frontend/src/lib/steps.ts:3` |
| L6 | Lav | Ingen grænse for antal linjer (2000 ok) og længde på et trin (100.000 tegn ok) | `schemas.py:RecipeIn` |
| L7 | Lav | Login: højst 2 samtidige kodeordstjek og 5 forsøg/min pr. IP | `auth.py:19,25` |
| L8 | Lav | TESTPLAN siger "kodeord læses fra stdin", men `create-user` spørger to gange via getpass | `cli.py:26-30` |

## 3. Detaljer pr. fund

**K1. Ingen adskillelse mellem familier.** Genskab: log ind som to brugere, `GET /api/recipes`, `/api/plans`, `/api/shopping?plan_id=1` giver samme data. `PUT /api/settings/departments` fra den ene ændrer den anden. `DELETE /api/recipes/{id}` og `/api/plans/{id}` virker på alles data. Forventet (flere-familier.md §1, §6): egen plan, indkøb, basisvarer, barnenote, afdelingsrækkefølge pr. familie; fremmed id giver 404. Forslag: byg trin 1-2 i designet (`CurrentHousehold`, `household_id` på plan, extra, setting; `household_pantry`; `household_recipe_note`) og lav test-matrixen. De fem xfail-tests i `test_qa_adgang.py` er et udgangspunkt. Bemærk også: `ingredient.pantry`, aliaser og ingredienstabel er fælles (det er tilsigtet for aliaser), men basisvarer skal ud pr. familie. Rate-limiter og push-abonnementer er heller ikke knyttet til en familie (`PushSubscription` sender påmindelser til alle telefoner, `reminders.py:targets`).

**M1. "1/0".** `POST /api/parse {"lines":["1/0 dl vand"]}`, `POST /api/recipes` og import giver 500 (ZeroDivisionError). Også "0/0 stk æg" og "1 1/0 dl mælk". Forventet: linjen læses som tekst uden mængde. Forslag: fang `ZeroDivisionError`/`ValueError` i `_to_float` og returnér `None`. Importerer man en side med en sådan linje, fejler hele importen.

**M2. Samtidig afkrydsning.** `sync()` slår rækken op og indsætter bagefter; to samtidige kald med samme nye `(plan_id, key)` giver `UNIQUE constraint failed: shopping_check`, én af dem får 500. Genskabt mod uvicorn og i test (6 tråde, 15 runder). Telefonen sender igen, så virkningen er lille, men det logges som fejl. Forslag: fang `IntegrityError`, rul tilbage og opdatér rækken (eller `INSERT ... ON CONFLICT DO UPDATE WHERE updated_ms < :ts`).

**M3. Tom titel.** `POST /api/recipes {"title":"   "}` giver 201 og titlen `""`; opskriften har tom flise i listen. Forventet 422. Forslag: valider på den strippede titel i `RecipeIn`.

**M4. Tilbud.** Der er ingen rute eller skærm for Bilka-tilbud eller tilbudsforslag (SPEC §3.7, PLAN fase 4/5 delvist). `offers/` har kun bibliotek og 5 tests. Det er ikke en fejl i det byggede, men dækker testpunktet "Bilka-tilbud/tjek": kun enhedstests mod fast data. Ingen kald til Tjek er foretaget.

**L1.** `POST /api/plans {"start_date":"9999-12-30"}` giver 500 (dato-overløb ved beregning af slutdato). Forslag: begræns `start_date` til fx 2020-2100.

**L2.** To hurtige `POST /api/shopping/extras {"text":"banan"}` giver to rækker. "Løbet tør" dubleres korrekt ikke. Forslag: ignorér ens ikke-afkrydsset tekst på samme plan, eller deaktivér knappen under afsendelse i UI.

**L3.** `quantity: -5` på manuel linje gemmes. "-5 g mel" og "1e308 g smør" giver `item="5 g mel"` / `"e308 g smør"` uden mængde og havner i Tjek. "99999999999 dl mælk" accepteres og regnes med. Forslag: `ge=0, le=100000` på `quantity`, og afvis ikke-endelige tal.

**L4.** SQLite `LIKE` er kun store/små-ufølsom for ASCII. Frontend filtrerer lokalt og bruger ikke `q`, så ingen brugerpåvirkning i dag. Forslag: filtrér i Python med `casefold()` eller fjern parameteren.

**L5.** Trin som "Tilsæt mel" (kort, uden punktum) bliver overskrift: Lav mad viser "6 trin" for 4 handlinger og trin-for-trin-visningen har overskrifter som egne sider. Importerede opskrifter har oftest punktum. Set i UI på `/lav/2026-10-27`.

**L6.** 2000 ingredienslinjer (der giver 2000 Tjek-punkter) og et 100.000 tegns trin gemmes uden fejl. Forslag: max ca. 100 linjer og 50 trin, 1000 tegn pr. trin.

**L7.** Seks af otte samtidige logins i en test fejlede (login-semaforen tillader to ad gangen, som designet; `test_login_is_refused_when_hash_gate_is_full` dækker det). Mange familier, der logger ind samtidigt (fx søndag aften), eller en familie bag samme IP, kan få 429. Skaleringsagenten bør vurdere grænserne.

**L8.** Dokumentation: `printf 'kode\n' | madplan-admin create-user x` fejler med EOFError. Der skal to linjer (kodeord og gentag).

## 4. Testmatrix (bestået/fejlet pr. linje)

B = bestået, F = fejlet (se fund), U = ikke udført. "API" = curl/httpx mod lokal server, "UI" = browser, "pytest" = ny eller eksisterende automatisk test.

### Login og adgang
| # | Test | Metode | Resultat |
|---|---|---|---|
| 1 | Login med korrekt bruger, store bogstaver og mellemrum i navn | API, pytest | B |
| 2 | Forkert kodeord, ukendt bruger, tomt felt, manglende/for lange felter | API, pytest | B (401/422, ingen 500) |
| 3 | Logout fjerner adgang; cookie er HttpOnly, SameSite=Lax | API, pytest | B |
| 4 | Alle 52 `/api`-ruter uden login giver 401 (matrix fra OpenAPI) | pytest | B |
| 5 | Slettet brugers cookie afvises | pytest | B |
| 6 | Login i UI på 375 px | UI | B |
| 7 | 429-grænser ved samtidige logins | API | B (som designet, se L7) |

### Opskrifter
| # | Test | Metode | Resultat |
|---|---|---|---|
| 8 | Manuel oprettelse med æøå, emoji, 200 tegn, HTML/SQL-tegn | API, pytest | B |
| 9 | Tom titel / 201 tegn | API, pytest | B (422) |
| 10 | Titel af kun mellemrum | API, pytest | F (M3) |
| 11 | Redigering bevarer linje-id'er, fremmed linje-id afvises | API, pytest | B |
| 12 | Redigering bevarer afkrydsning og "har hjemme" | pytest | B |
| 13 | Sletning (to gange), plan viser "Slettet opskrift", liste uden fejl | API, pytest | B |
| 14 | Dubletter af link (skråstreg, store bogstaver) | API, pytest | B (409) |
| 15 | Ugyldigt link (`javascript:`, `file:`), lokal adresse ved import | API, pytest | B (422) |
| 16 | Import fra rigtig side | U | U (ekstern; dækket af eksisterende `fake_web`-tests) |
| 17 | Billede: upload JPEG/PNG/WebP, forkert indhold, 9 MB, skift, slet, filer ryddes | API, pytest | B |
| 18 | Billeder kræver login, sti-snyd (`..%2F`) giver 404 | API, pytest | B |
| 19 | Søgning `q` med æ/Æ og `%` | pytest | F (L4) |
| 20 | Servings 0/-1/101, linje over 300 tegn, tomme linjer droppes | pytest | B |
| 21 | Meget mange linjer / meget lange trin | API | F (L6, accepteres uden grænse) |
| 22 | Opskriftsliste, kort med 200 tegns titel i UI | UI | B (ingen overløb) |

### Ingredienslæser og matcher
| # | Test | Metode | Resultat |
|---|---|---|---|
| 23 | Bøjninger, brøker, intervaller, "½", "1½" | pytest | B |
| 24 | "1/0", "0/0", "1 1/0" | API, pytest | F (M1) |
| 25 | Negative, enorme, "1e308", arabiske cifre, kun emoji | pytest | B (ingen nedbrud), L3 for kvalitet |
| 26 | Ny vare matcher eksisterende linjer; omdøbt vare bevarer gammelt navn som alias | pytest | B |
| 27 | Duplikat/alias-navn, ugyldig afdeling, g/stk ≤ 0 | pytest | B |
| 28 | Tjek: bekræft/ignorér/stjerne på ukendt linje giver 404 | pytest | B |
| 29 | Tjek-skærm i UI viser usikre varer | UI | B |

### Ugeplan
| # | Test | Metode | Resultat |
|---|---|---|---|
| 30 | Ny uge, overlap giver 409, 0 og 15 dage afvises | API, pytest | B |
| 31 | Plan over årsskifte og uge 53 (28/12-3/1) giver 7 forskellige dage | API, pytest | B |
| 32 | "Nuværende uge" ved 27/12, 31/12, 1/1, 3/1, 4/1 | pytest | B |
| 33 | Skudår 29/2, sommertid 25/10-2026 og 28/3-2027 | pytest | B |
| 34 | Ekstremdato `9999-12-30` | API, pytest | F (L1) |
| 35 | Planlæg, erstat, flyt over årsskifte, bytte, uden for plan, gange 3/-1 | API, pytest | B |
| 36 | Rester samme/senere dag afvises; flytning bryder umulig rest | API, pytest | B |
| 37 | Ønskeliste, fordel, dobbelt-fordel giver ingen dubletter, tom og 201 tegn | API, pytest | B |
| 38 | To enheder planlægger hver sin dag samtidigt | pytest | B |
| 39 | Dobbelt-submit ny uge | pytest | B (201 + 409) |
| 40 | Ugevisning mobil og computer | UI | B |

### Indkøbsliste
| # | Test | Metode | Resultat |
|---|---|---|---|
| 41 | Samlet på tværs af ugen (flere retter, ×½, ×2, barnets ret) | API, pytest | B |
| 42 | Egne varer: emoji, 200 tegn, tomme, ukendt vare 404 | API, pytest | B |
| 43 | Egen vare dobbeltklik | API, pytest | F (L2) |
| 44 | "Løbet tør" dobbelt giver én række | API, pytest | B |
| 45 | Afkrydsning: ældste ændring taber, lige tid beholder første, uret langt fremme, skrald-ændringer | API, pytest | B |
| 46 | Afkrydsning pr. plan (uge 1 påvirker ikke uge 2) | pytest | B |
| 47 | To telefoner krydser samme nye vare af samtidigt | API, pytest | F (M2) |
| 48 | Butiksrækkefølge: ufuldstændig/duplikeret afvises, rækkefølgen styrer listen | API, pytest | B |
| 49 | Sletning af plan, stale plan-id, ukendt plan | API, pytest | B |
| 50 | Indkøbsside i UI (afdelinger, "egen vare", "Vælg vare") | UI | B |

### Bilka-tilbud og tjek
| # | Test | Metode | Resultat |
|---|---|---|---|
| 51 | Tilbudsmatch (bibliotek) | pytest (eksisterende 5) | B |
| 52 | Tilbud i API/UI, tilbudsmarkering på liste, forslag ud fra tilbud | – | U (ikke bygget, M4) |

### Påmindelser og husk
| # | Test | Metode | Resultat |
|---|---|---|---|
| 53 | Tidspunkter: gyldige 00:00, 23:59; ugyldige 24:00, 7:00, 19:60, tom | API, pytest | B |
| 54 | Standardtider normaliseres; nulstil med null; gentagelse til/fra | API | B |
| 55 | Tekst trimmes, emoji bevares, tom/201 tegn afvises | API, pytest | B |
| 56 | Påmindelse følger flyttet ret og slettes med retten | pytest | B |
| 57 | Dobbelt-submit giver to (dokumenteret), dobbelt sletning 404 | pytest | B |
| 58 | Planlægning omkring sommertid (nat 25/10) | pytest | B |
| 59 | Push-abonnement med ukendt endpoint afvises | API | B (422) |
| 60 | Rigtig push til telefon, service worker | UI | U (se 6) |

### Lav mad og Ryd op
| # | Test | Metode | Resultat |
|---|---|---|---|
| 61 | Dag uden ret, dag med ret: ingredienser grupperet, "find frem" | UI | B |
| 62 | Trin for trin med play-knap, "trin 1 af 6" | UI | B |
| 63 | Trin uden punktum | UI | F (L5) |
| 64 | Ryd op: basisvarer (30), butiksrækkefølge, alle varer | UI | B |

### Flere familier
| # | Test | Metode | Resultat |
|---|---|---|---|
| 65 | Familie B ser ikke A's planer, indkøb, ønsker | API, pytest xfail | F (K1) |
| 66 | Afdelingsrækkefølge/basisvarer pr. familie | API, pytest xfail | F (K1) |
| 67 | Barnenote privat pr. familie | pytest xfail | F (K1) |
| 68 | Fælles opskrift kan ikke slettes af andre familier | pytest xfail | F (K1) |
| 69 | Påmindelser/måltider på anden families data giver 404 | pytest xfail | F (K1) |
| 70 | Delte opskrifter og familiens tilpasninger, fælles rettelser | – | U (ikke bygget) |
| 71 | To brugere i samme familie deler alt (nuværende tilsigtet adfærd) | pytest | B |

## 5. Nye testfiler

| Fil | Tests | Indhold |
|---|---|---|
| `backend/tests/test_qa_adgang.py` | 8 (3 grønne, 5 xfail) | login-matrix over alle ruter, familieadskillelse (xfail), fælles familie |
| `backend/tests/test_qa_indkoeb_og_uge.py` | 38 (35 grønne, 3 xfail) | årsskifte, uge 53, skudår, sommertid, mængder, afkrydsning, samtidighed, dobbelt-submit |
| `backend/tests/test_qa_kanttilfaelde.py` | 76 (69 grønne, 7 xfail) | tekster, tal, billeder, påmindelser, ingredienser, login |

Alt: **122 nye tests (107 grønne, 15 xfail)**. De 15 xfail dækker K1 (5), M1 (3), M2, M3, L1, L2, L3, L4 (2). Alle xfail på kendte fejl bruger `strict=True`, så de melder sig, når fejlen rettes, undtagen K1 og M2 (`strict=False`; K1 skal omskrives til to familier, M2 er et kapløb). Kør: `cd backend && .venv/bin/pytest -q` (318 grønne, 15 xfailed, ca. 37 s).

Huller, der stadig er i den automatiske dækning: ingen UI-/browsertests (kun typecheck), ingen test af offline-kø i frontend, ingen test af service worker/push i en rigtig browser, ingen last-/skalatests, Valdemarsro/nemlig-import mod rigtige sider.

## 6. Hvad der er tjekket og fundet i orden

- Alle ruter kræver login; ukendte `/api`-stier giver JSON-404; billeder kræver login og er beskyttet mod sti-snyd.
- Billedupload tjekker indhold (ikke filnavn), størrelse og rydder gamle filer.
- Ingen 500 på ugyldige datoer (på nær L1), gange, tider, tomme felter og for lange tekster; fejl er danske og forståelige.
- Mængder: sammenlægning på tværs af dage, ×½ afrundes til hele pakker, ×2, barnets ret, rester dækker linjer.
- Afkrydsning: "seneste ændring vinder", uret langt fremme låser ikke, ugyldige ændringer blokerer ikke resten.
- Datoer: årsskifte, uge 53, skudår, sommertid giver 7 forskellige dage og rigtig "nuværende uge".
- Frontend: `npm run check` giver 0 fejl; login, ugevisning, opskriftsliste, indkøb, Tjek, Ryd op og Lav mad virker i browser.
- Serveren overlevede alle fejlindput (6 stk 500, ingen nedbrud).

## 7. Hvad der ikke kunne testes

- Flere familier, delte opskrifter og familiens tilpasninger (ikke bygget).
- Bilka-tilbud/Tjek mod live API og i UI (ikke koblet; ingen eksterne kald for at skåne kilderne).
- Import fra Valdemarsro/nemlig og søgning på dem (eksterne sider; kun lokal SSRF-afvisning testet).
- Push-beskeder til rigtig telefon og service worker/offline: browserruden afviste registrering af service worker over `http://localhost`, så offline-kø og installation er ikke prøvet (kun serversiden af synkronisering).
- Rigtige samtidige telefoner, iOS-Safari, tilgængelighed (hører til UI-/UX-rapporterne).
