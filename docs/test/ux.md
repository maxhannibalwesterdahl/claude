# UX-gennemgang før go-live (rolle 1: UX-designer)

Gren `rolig`. Lokal kopi på port 8101 med egen `DATA_DIR`. Serveren er stoppet og dataene slettet.

## 1. Kort konklusion

**Klar med forbehold.** Selve flowet (login, opskrift, uge, indkøb, lav mad) er gennemtænkt, og sproget er roligt og konsekvent dansk. Der er ingen blokerende UX-fejl i hovedrejsen for en bruger, som kender appen. For en NY familie mangler der onboarding: efter login møder de en tom skærm uden at få at vide, at opskrifter kommer først. Der er ingen vej til at få adgang uden administratoren, og "Lav mad", påmindelser og Bilka-tilbud er svære at finde.

Et fund er ikke UX men blokerer go-live for flere familier: **to brugere deler alle data** (UX-01). Det skal bekræftes med sikkerhedsrapporten.

## 2. Metode og begrænsning

Browserruden (Claude Browser) var delt med en anden testagent, der navigerede samme fane til port 8102. Cookien `madplan_session` ligger på `127.0.0.1` uden portadskillelse, så et browserlogin ville have logget den anden agent ud. Jeg lod derfor være at bruge den. Der er **ingen skærmbilleder eller 375 px-visning**. Gennemgangen bygger på Svelte-koden, API-kald med curl mod den lokale server (import, uge, slots, indkøb, sletning, login-grænse) og de tekster, appen viser. Pixelmål, tryk-mål og visuel hierarki hører under `ui.md`.

## 3. Fund

| ID | Alvor | Titel | Sted |
|---|---|---|---|
| UX-01 | Kritisk (kryds-ref. sikkerhed) | En anden bruger ser den første brugers uge. Der er ingen familieadskillelse | `docs/flere-familier.md` ("ikke bygget"), alle `/api/plans`-kald |
| UX-02 | Høj | Ingen onboarding: tom "Uge" nævner ikke, at opskrifter skal ind først | `routes/+page.svelte:244-250` |
| UX-03 | Høj | Ny familie kan ikke få adgang selv. Login har ingen hjælp, og kodeord kan ikke ændres i appen | `routes/login/+page.svelte`, `cli.py` |
| UX-04 | Høj | Sletning af en opskrift, der står i ugen, ødelægger planen uden advarsel | `routes/opskrift/[id]/+page.svelte:61`, backend |
| UX-05 | Høj | Log ud (og alle indstillinger) gemt bag et ikon med navnet "Ryd op" | `routes/opskrifter/+page.svelte:93-101`, `routes/rydop/+page.svelte:127` |
| UX-06 | Mellem | Log ud rydder ikke den lokale indkøbsliste | `routes/rydop/+page.svelte:86`, `lib/shopping.svelte.ts:23` |
| UX-07 | Mellem | "Lav mad" er kun en tydelig knap for i dag. Andre dage: tekstlink dybt i dagsarket | `lib/uge/MealPanel.svelte:229`, `TonightCard.svelte:58` |
| UX-08 | Mellem | Påmindelser findes kun inde i dagsarket, og beskeder skal slås til pr. telefon | `lib/uge/Reminders.svelte`, `lib/push.svelte.ts` |
| UX-09 | Mellem | Bilka-tilbud har ingen skærm i frontenden | `frontend/src` (ingen forekomst), `backend/src/madplan/offers/` |
| UX-10 | Mellem | Import fejler: teknisk tekst og ingen vej videre til "Skriv selv" | `routes/importer/+page.svelte:25-36`, backend-svar |
| UX-11 | Mellem | "Barnet"-valget vises for alle, også familier uden børn | `lib/uge/MealPanel.svelte:106-130` |
| UX-12 | Mellem | Basisvarer er forudfyldt (smør, mel, olie …) uden at familien er spurgt | `routes/rydop/+page.svelte:127-140`, indkøbssiden |
| UX-13 | Mellem | Ingen net: Opskrift og "Lav mad" kan ikke åbnes, og forklaringen er kort | `routes/lav/[dato]/+page.svelte:46-58`, `service-worker.ts` |
| UX-14 | Lav | Jargon: "Ryd op", "Tjek", "Rigtig", "Til", "stjerne", "hovedingrediens", "planen" | flere |
| UX-15 | Lav | Sletning af uge forklarer ikke, hvad der forsvinder | `lib/uge/week.svelte.ts:139` |
| UX-16 | Lav | Dobbelte ingredienslinjer fra import (mozzarella 2×125 g) vises uden hint | import fra valdemarsro.dk |
| UX-17 | Lav | Login-grænsen (5 forsøg) siger "Vent et minut" uden at låse op | backend login, `login/+page.svelte` |
| UX-18 | Lav | "Lav en uge" kan oprette uge i fortiden og kræver gæt af "Indkøbsdag" | `lib/uge/NewWeekSheet.svelte` |

## 4. Detaljer

### UX-01 Kritisk: ingen familieadskillelse
- **Genskab:** opret brugerne `ux` og `anden` med `madplan-admin`. Log ind som `ux`, lav en uge og læg en ret på. Log ind som `anden` og kald `GET /api/plans`.
- **Faktisk:** `anden` får `[{"id":1,"start_date":"2026-10-16",...}]`, altså den første brugers uge. Opskrifterne var tomme for `anden` i mit test, men planer er delt. Designdokumentet siger, at husstande er "ikke bygget".
- **Forventet:** hver familie ser kun sin egen uge, ønskeliste, indkøbsliste og påmindelser.
- **Forslag:** byg `household` før flere familier lukkes ind (se `docs/flere-familier.md` pkt. 2). Det er også en sikkerhedssag. Bekræft mod `sikkerhed.md`.

### UX-02 Høj: tom start uden vejledning
- **Genskab:** log ind som ny bruger. Forsiden `/` viser "Der er ingen madplan endnu." og knappen "Lav en uge". Fanerne Indkøb og Opskrifter viser hver sin tomme tilstand ("Der er ingen madplan endnu", "Der er ingen opskrifter endnu").
- **Problem:** de tre tomme tilstande peger forskelligt og ikke på en rækkefølge. Rejsen bør være 1. opskrift, 2. uge, 3. indkøb. Den første knap ("Lav en uge") sender familien til en uge uden retter, og vælgeren siger blot "I har ingen opskrifter endnu." uden knap. Den er en blindgyde, selv om søgefeltet kan finde Valdemarsro og nemlig (det er en god genvej, men skjult i feltet i bunden).
- **Forslag:** ét velkomstkort ved første besøg: "Start med en opskrift: Importér fra link / Skriv selv / Find på Valdemarsro". Lav ugen automatisk eller foreslå den bagefter. Giv "I har ingen opskrifter endnu." i vælgeren et link til `/importer`. Vis tre trin øverst ("1 Opskrift, 2 Uge, 3 Indkøb") til de er gennemført én gang.

### UX-03 Høj: adgang og kodeord
- Familier kan kun oprettes af administratoren med `madplan-admin create-user`. Loginsiden har ingen tekst om det ("Få adgang hos …"), intet "glemt kodeord" og ingen måde at skifte kodeord. Fejl er den ene linje "Forkert brugernavn eller kodeord".
- `madplan-admin create-user` bruger `getpass` og kræver en terminal. TESTPLAN.md skriver "læses fra stdin", men det virker ikke fra et rør (`EOFError`). Det gælder administratorens onboarding, ikke familien.
- **Forslag:** kort hjælpetekst på login, og en side til at skifte kodeord. Længere sigt: invitationslink (som i `flere-familier.md`).

### UX-04 Høj: slet opskrift, der er i brug
- **Genskab:** importér, læg på i dag, `DELETE /api/recipes/1` (204). Dagen viser nu "Slettet opskrift" uden indhold, og indkøbslisten mister varerne. Dialogen spørger kun `Slet "Lasagne"?`.
- **Forventet:** advarsel som "Lasagne står på ugen (fredag). Den fjernes derfra, og varerne forsvinder fra indkøbslisten." Helst også fortryd.
- **Forslag:** returnér antal planlagte forekomster fra serveren og vis dem i dialogen.

### UX-05 Høj: Log ud og indstillinger er skjult
- Siden "Ryd op" rummer Basisvarer, Rækkefølge i butikken, Indkøbsdag, Alle varer og Log ud. Adgangen er et listeikon øverst på Opskrifter med navnet "Ryd op" (eller en chip "Ryd op · N"). En ny bruger leder efter "Indstillinger" og finder det ikke. En delt telefon kan ikke logges ud uden at kende stien.
- **Forslag:** omdøb siden til "Mere" eller "Indstillinger", brug tandhjul, og læg ryd-op-opgaverne i en sektion øverst.

### UX-06 Mellem: lokal liste overlever Log ud
- `logout()` kalder kun `/logout` og går til `/login`. `localStorage["madplan.indkob.v1"]` indeholder stadig forrige familiens indkøbsliste og ventende kryds. Ved login som en anden på samme telefon vises den (så længe `sync` ikke har svaret; ved offline, hele tiden).
- **Forslag:** ryd nøglen (og `madplan.findfrem.*`) ved log ud og ved 401.

### UX-07 Mellem: "Lav mad" kan ikke findes
- Kun "I aften"-kortet har knappen "Lav mad". På andre dage skal man åbne dagsarket og finde et tekstlink nederst. På opskriftssiden findes kun en rund afspilningsknap uden synlig tekst (aria-label "Start trin for trin").
- **Forslag:** synlig knap "Lav mad" i dagsarket for alle dage med opskrift, og tekst ved afspilningsknappen ("Trin for trin").

### UX-08 Mellem: påmindelser
- Ingen genvej fra Uge. En ny familie ved ikke, at "Husk" findes. Beskeder tilbydes først nederst i dagsarket, når der er en åben påmindelse. På iPhone kræves hjemmeskærm først (teksten er god, men kommer sent). Beskeder er pr. telefon, og det står ("Ikke slået til på denne telefon"), men ikke om begge i familien får dem.
- **Forslag:** ved første login: ét spørgsmål "Vil I have besked om påmindelser?" med forklaring. Vis klokkeikon på dage med påmindelser (kan være der allerede; ikke verificeret visuelt).

### UX-09 Mellem: Bilka-tilbud ikke i appen
- Backend har modulet `offers/`, men `grep` for "Bilka"/"tilbud" i `frontend/src` finder intet. Familier forventer det ud fra produktbeskrivelsen. Hvis det er bevidst slået fra, skal det ikke omtales ved udrulning.

### UX-10 Mellem: importfejl
- Faktiske svar (422): "Linket peger på en lokal adresse", "Siden har ingen opskriftsdata, som kan læses", "Siden svarede med fejl 404", "Kan ikke finde siden nonexistent.invalid". Teksterne er ærlige men tekniske. Indtastes `www.valdemarsro.dk/…` uden `https://`, stopper browserens indbyggede check (type=url) på brugerens sprog og uden forklaring på dansk. Serveren svarer `Linket skal starte med https://`, men tillader `http://` (teksten passer ikke).
- Efter en fejl står der ingen næste handling. Appen kunne tilbyde "Skriv opskriften selv" og "Prøv et andet link".
- **Forslag:** knap/link til `/ny` i fejlboksen. Tilføj `https://` automatisk, hvis det mangler. Omskriv "lokal adresse" til "Linket kan ikke bruges".
- Positivt: dublet (409) giver et link til opskriften. Knappen "Indsæt link" er god.

### UX-11 Mellem: Barnet
- Hver dag har rækken "Barnet · Samme som de voksne · Noget andet", og opskrifter har "Note om barnet". For familier uden små børn er det støj. Det er også en ekstra beslutning pr. dag.
- **Forslag:** slå fra som standard og tilbyd i indstillinger ("Har I et barn med egen mad?").

### UX-12 Mellem: basisvarer
- Salt, peber, smør, hvedemel, olivenolie, krydderier m.fl. er markeret som basisvarer og kommer ikke på listen (testet: 12 varer på listen, 7 basisvarer skjult for lasagnen). En familie uden mel eller smør står i butikken uden dem og opdager det først i køkkenet. Sektionen "Basisvarer brugt i ugen · altid hjemme" med "Løbet tør" er pæn, men står nederst.
- **Forslag:** ved første uge: "Disse har I altid hjemme?" med afkrydsning (kort liste). Se `flere-familier.md` (basisvarer pr. familie).

### UX-13 Mellem: ingen net
- App-skallen åbner offline, og indkøbslisten er gemt lokalt (flot, og siger "Uden net. Listen er gemt her, N kryds venter"). Opskrift, Uge og "Lav mad" henter via API ved hver åbning og viser kun "Det kræver net. Prøv igen, når I har forbindelse." Mister mobilen dækning ved komfuret, kan en ny side ikke åbnes. Åbnet trin for trin fortsætter.
- **Forslag:** gem dagens opskrift lokalt, når siden åbnes, og vis den offline. Eller en knap "Hent til offline" i dagsarket.

### UX-14 Lav: jargon og ordvalg
- "Ryd op" (hører til afklaring af uklare varer), "Tjek", "Rigtig" (bekræft vare), "Til" (maks-mængde), "stjerne = hovedingrediens", "Foreslå stjerner igen", "Indkøbsdag" (ugens start). Fejlen "Overlapper planen fra 16/10" siger "planen", mens skærmen siger "ugen".
- **Forslag:** "Uklare varer" i stedet for "Ryd op"; "Højst" i stedet for "Til"; "hovedvare"; "ugen" overalt.

### UX-15 Lav: sletning af uge
- `Slet ugen 16.-22. okt.?` nævner ikke, at retter, ønsker, påmindelser og kryds forsvinder, og der er ingen fortryd. Knappen "Slet denne uge" står nederst på siden (kan trykkes ved et uheld under rullen, men dialogen beskytter).

### UX-16 Lav: dobbeltlinjer
- Importen af Valdemarsros lasagne gav "125 g frisk mozzarella" to gange (som på kilden), og "salt og friskkværnet peber" to gange. Indkøbslisten lægger sammen (rigtigt), men opskriften ser fejlbehæftet ud.

### UX-17 Lav: login-grænse
- Efter 5 forkerte forsøg svarer serveren 429 "For mange forsøg. Vent et minut." (testet). Teksten er fin. Grænsen er pr. IP. Flere familier bag samme net (fx fælles wifi) kan blokere hinanden.

### UX-18 Lav: ny uge
- Formularen foreslår dagens dato eller dagen efter seneste uge og genveje til de næste søndag/mandag (`nextWeekday(…, 0/1)`). Datoen kan sættes til fortiden (testet: 2020-01-01 blev oprettet). Forklaringen "Ugen starter på indkøbsdagen og varer syv dage" er god, men "Indkøbsdag" som begreb er nyt for en ny familie.

## 5. Hvad der er tjekket og fundet i orden

- **Sprog:** konsekvent "I/jeres", hele sætninger, ingen udråbstegn, ingen "Fejl" (fælles `copy.ts`). Dansk `lang="da"`.
- **Login:** `autocomplete`, `autocapitalize`, kun interne `?til=`-stier (ingen åben omdirigering).
- **Fejlforebyggelse:** dialog før "Slet", "Erstat" og før man forlader en redigering med ikke-gemte ændringer; "Gem" stopper, hvis indsatte linjer ikke kan læses; dublet-import giver 409 med link.
- **Import:** virker fra valdemarsro.dk (21 linjer, 8 trin, billede, hovedingrediens, varer matchet "sikker"). Fejlbeskeder for ugyldig URL, lokal adresse, 404 og ukendt vært kommer på dansk.
- **Uge:** overlappende uge giver 409 med serverens sætning; ønskeliste, "I aften"-kort og træk-og-slip på bred skærm.
- **Indkøb:** fremdrift (N af M), "Har hjemme" (swipe + Fortryd), "Købt"-fold, offline-lager med ventende kryds, afdelinger.
- **Lav mad:** hele opskriften først, "Trin X af Y", skærmen holdes tændt, "Færdig" fører til ugen; tilbage-knappen er designet til at forlade i ét skridt (ikke testet i browser).
- **Tilbage-navigation:** kode for `navState.inApp`, `BackButton` og `replaceState` i trinvisningen ser rigtig ud.

## 6. Hvad der ikke kunne testes

- **Visuel gennemgang på 375 px, tryk-mål, kontrast, animation:** browserruden var delt med en anden agent, og delt cookie på `127.0.0.1` gjorde login risikabelt (se afsnit 2). Overlades til `ui.md`.
- **Tilbage-knap, swipe og træk i en rigtig browser/PWA.**
- **Rigtige Web Push-beskeder (iOS, Android):** kræver HTTPS og rigtig telefon.
- **Offline-tilstand:** ikke slået fra i en browser; vurderet ud fra kode (`service-worker.ts`, `shopping.svelte.ts`, `api.ts`).
- **Bilka-tilbud:** ingen skærm at teste.
- **Manuel opskrift (`/ny`):** gennemlæst i kode (`RecipeEditor.svelte`), ikke udfyldt i en browser.
- **Import fra andre sider end valdemarsro.dk** (nemlig, arla, dr.dk, hellofresh) og "Spis Bedre virker ikke" (omtalt i teksten).
