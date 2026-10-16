# Samlet testrapport før go-live

Dato: 16-10-2026. Gren: `rolig`. Seks testere arbejdede samtidig efter
[TESTPLAN.md](TESTPLAN.md). Detaljer, genskabelse og forslag står i hver rapport.

## Konklusion

**Appen er ikke klar til at åbne for flere familier.** Den er god og stabil til
én familie: alle hovedfunktioner virker, inklusive årsskifte, uge 53, skudår og
sommertid. Intet datatab blev fundet, og migrationerne holder.

Den afgørende mangel blev fundet af alle fem testere uafhængigt af hinanden:
**familier (husstande) findes ikke i koden.** [flere-familier.md](../flere-familier.md)
er et design, der ikke er bygget. Lukkes der flere familier ind i dag, kan alle
se, ændre og slette hinandens opskrifter, planer, indkøbslister og påmindelser,
og alle telefoner får alle familiers beskeder.

## Overblik

| Rapport | Konklusion | Kritisk | Høj | Mellem | Lav |
|---|---|---|---|---|---|
| [UX](ux.md) | Med forbehold | 1 | 4 | 8 | 5 |
| [UI](ui.md) | Med forbehold | 0 | 0 | 6 | 13 |
| [Sikkerhed](sikkerhed.md) | Nej | 1 | 1 | 5 | 7 |
| [Kode](kode.md) | Nej (ja for én familie) | 1 | 4 | 6 | 14 |
| [Skalering](skalering.md) | Nej, med forbehold | 2 | 4 | 5 | 4 |
| [QA](qa.md) | Nej | 1 | 0 | 4 | 8 |

Mange fund går igen på tværs (fx familieadskillelse i alle fem). Listen herunder
er slået sammen, så hvert problem kun står én gang.

## Prioriteret liste

### P0 – Blokerer go-live for flere familier

| # | Problem | Kilder |
|---|---|---|
| 1 | **Byg husstande.** Tabel + `household_id` på familiens data, én fælles `CurrentHousehold`-afhængighed, som alle ruter bruger, og en adgangs-testmatrix. Fælles: opskrifter, ingredienser, aliaser. Pr. familie: planer, indkøb, basisvarer, butiksrækkefølge, påmindelser, push. | UX-01, S-01 (sik.), F-01, F-03, S-01 (skal.), QA kritisk |
| 2 | **Påmindelser kun til egen families telefoner**, og et push-abonnement må ikke kunne overtages af en anden bruger. | S-02 (sik.), F-02 |
| 3 | **Påmindelsesjobbet holder skrivelåsen under netværkskald** (op til 15 s). Ved aftenspids fejler andres skrivninger med `database is locked`. Hent data, luk sessionen, send derefter. | S-04 (skal.), F-07 |
| 4 | **Forbindelsespuljen (5+10) er mindre end trådpuljen (40).** Ved 200 samtidige brugere fejlede 52 %, og selv `/api/health` svarede ikke. Hæv puljen og lad være med at holde forbindelsen under eksterne kald (søgning/import). | S-02, S-03 (skal.), F-11 |
| 5 | **Indkøbslisten i `localStorage` ryddes ikke ved logout** og har én fælles nøgle. Næste bruger på telefonen ser og sender den forrige brugers liste. | F-04, UX-06, S-07 (sik.) |

### P1 – Lige før eller lige efter go-live

| # | Problem | Kilder |
|---|---|---|
| 6 | Server-side ugyldiggørelse af sessioner ved logout + skift af kodeord i appen. | S-07 (sik.), UX-03 |
| 7 | Loginbegrænsningen kan omgås/misbruges via `X-Forwarded-For` (`--forwarded-allow-ips "*"` i Dockerfile). Begræns også pr. brugernavn. | S-04 (sik.) |
| 8 | Sikkerhedsheadere: CSP, X-Frame-Options, nosniff, HSTS, Referrer-Policy. | S-05 (sik.) |
| 9 | SSRF i import: DNS rebinding omgår filteret. Forbind til den IP, der blev tjekket. | S-06 (sik.) |
| 10 | Mængder: `Infinity`, `1/0` og negative tal accepteres og får indkøbslisten til at give 500. Valider ved indgang. | F-05, QA mellem |
| 11 | Samtidig afkrydsning fra to telefoner og samtidige ændringer på samme dag giver 500 (UNIQUE-fejl). | F-08, QA mellem, S-06 (skal.) |
| 12 | `/api/recipes` vokser med antal opskrifter (2,6 MB / 1 s ved 8.000) og kan sprænge 512 MB. Paginér eller slank svaret; slå gzip til. | S-05 (skal.) |
| 13 | Onboarding: en ny familie møder en tom app uden vejledning; "Log ud" ligger bag "Ryd op". | UX-02, UX-05 |
| 14 | Kopi af data uden for maskinen (står allerede som åbent punkt i drift.md). | S-10 (skal.) |

### P2 – Snart

- Manglende indekser på fremmednøgler (F-09).
- Synk med ugyldig nøgle giver 500 (F-06). Cookie med ikke-ASCII og meget store id'er giver 500 (sik. lav).
- Sletning af opskrift, der står i ugen, advarer ikke (UX-04).
- Fejltekster ved import er tekniske og fører ikke videre til "Skriv selv" (UX-10).
- To uvicorn-workers sender dobbelte påmindelser. Bliv på én worker, indtil jobbet er låst (S-07 skal.).
- UI: sidetitler pr. side (WCAG 2.4.2), pladsholder- og feltkontrast, `scroll-padding-bottom`, chip-overløb, pinch-zoom på indkøbslisten (UI-01 til UI-06).
- Titel af kun mellemrum accepteres (QA).

### P3 – Pænt at have

De lave fund i hver rapport: design-tokens for skrift/skygger/radius, mørk
splash i PWA, død kode i `offers/`, søgning med `q` og æøå, grænser for
længde og antal linjer, m.m.

## Det, der er i orden

- Alle API-ruter kræver login. Kodeord hashes med argon2. Cookie er signeret, HttpOnly og SameSite=Lax. CSRF på JSON-ruter afvises.
- Ingen rå SQL, ingen `{@html}`, ingen hemmeligheder i git-historikken. `/docs` er slået fra.
- Containeren kører ikke som root, har ingen udadgående porte og har grænser for hukommelse og processer.
- Migrationer matcher modellerne. En opgradering fra en ældre version med data mistede intet.
- Frontendens typer matcher backend-skemaerne.
- Dato og tid i dansk tid håndteres rigtigt over sommertid og årsskifte.
- Designsystemet er stramt, kontrasten består i lyst og mørkt tema, ark er rigtige `<dialog>`.
- Ved realistisk belastning (200 aktive brugere, 4 s mellem klik) var p95 267 ms. SQLite er nok endnu; Postgres først ved flere app-containere eller vedvarende `database is locked`.

## Tests

- 211 eksisterende + 107 nye tests består. 15 nye er markeret `xfail`, ét pr. kendt fund.
  Når et fund rettes, skal den tilsvarende `xfail` fjernes.
- Nye filer: `backend/tests/test_qa_adgang.py`, `test_qa_indkoeb_og_uge.py`, `test_qa_kanttilfaelde.py`.
- `npm run check`: 0 fejl, 0 advarsler.

## Ikke testet

- Rigtig iPhone, skærmlæser og fysiske touch-bevægelser.
- Web Push mod rigtige tjenester, service worker og offline på en telefon.
- Tailscale Funnel (hvad den sætter i `X-Forwarded-For`, TLS/HSTS) og ydelsen i LXC'en. Tallene for skalering er målt på en Mac og er relative.
- Import fra eksterne opskriftssider og Bilka-API'et (kun SSRF-afvisningen er testet lokalt).
- Delte opskrifter med familiens tilpasninger (ikke bygget).
