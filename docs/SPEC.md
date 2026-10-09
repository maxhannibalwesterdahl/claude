# Madplan – specifikation

Ugentlig madplan til eget brug for én husstand. Opskrifter importeres fra danske
opskriftssider, ingredienser lægges sammen på tværs af ugen, og indkøbslisten
bruges på mobilen i Bilka.

Status: fase 0 og 1 er bygget. Se [PLAN.md](PLAN.md) for rækkefølge og status.

---

## 1. Rammer

| | |
|---|---|
| Brugere | 2 voksne med hver sit login, én fælles husstand |
| Husstand | 2 voksne + 1 barn (1 år) |
| Primær enhed | Mobil (PWA på hjemmeskærmen). Tablet/computer til planlægning |
| Indkøb | Én stor tur om ugen i Bilka, søndag eller mandag |
| Drift | Egen LXC-container i Proxmox, adskilt fra Home Assistant |
| Adgang udefra | Tailscale Funnel (Tailscale kun på serveren, ikke på telefonerne) |
| Budget | Gratis i drift. Ingen betalte API'er i første version |

## 2. Gennemgang af den aftalte plan – rettelser

Planen fra idéfasen er gennemgået. Følgende er ændret eller præciseret:

1. **Mealie droppes som motor.** Efter beslutningerne skulle vi selv bygge
   madplanen (barnets ret, rester, ønskeliste), indkøbslisten (sammenlægning,
   basisvarer, afkrydsning pr. dag) og den danske ingredienslæsning. Mealie ville
   kun have leveret opskriftslagring og import, og import kommer fra biblioteket
   `recipe-scrapers`, som vi kan bruge direkte. Mealie ville koste en ekstra
   tjeneste, et ekstra login, synkronisering mellem to datamodeller og afhængighed
   af deres API. Testet: `recipe-scrapers` læser Valdemarsro korrekt og har
   færdige læsere til valdemarsro.dk, madensverden.dk, dr.dk, sundpaabudget.dk
   og hellofresh.dk. Arla virker via generiske opskriftsdata. Spis Bedre virker
   ikke (ingen opskriftsdata på siderne, testet i fase 0).
   *Konsekvens:* Home Assistant-integrationen via Mealie forsvinder. Kan bygges
   senere mod vores eget API (fase 6).
2. **Ikke alle måltider er opskrifter.** "Pizza ude", "Rugbrød", "Grød" skal
   kunne skrives ind som fritekst uden indkøb.
3. **Samme ingrediens flere gange i én opskrift.** Valdemarsros lasagne har
   "125 g frisk mozzarella" og "salt og peber" to gange hver (ragu + bechamel).
   Sammenlægningen skal også virke inden for én opskrift.
4. **Pakningsstørrelser tages ikke med i første version.** Listen viser samlet
   mængde ("800 g hakket oksekød", "3 løg"). Styk-enheder (dåse, stk, pakke)
   rundes op til hele tal. Omregning til pakninger kræver produktdata, vi ikke
   har.
5. **Intet prisoverslag i første version.** Bilka ToGo som kilde til normalpriser
   er ikke efterprøvet. Tilbud virker (efterprøvet, se §6).
6. **Tilbud skal sammenlignes pr. kg/l, ikke pr. pakke.** Eksempel fra testen:
   kyllingebryst til 179 kr. i Bilka og 29 kr. i Netto er forskellige
   pakningsstørrelser. Tjek leverer mængde og enhed pr. tilbud, så kilopris kan
   beregnes. Først relevant, når Netto/Rema kommer med.
7. **Søgning på Valdemarsro returnerer også artikler** ("16 skønne opskrifter
   til fryseren", "5 små glimt"). Resultater uden opskriftsdata frasorteres.
8. **Login og offline.** Uden Cloudflare Access styrer vi selv sessionen: lang
   session (90 dage) og indkøbslisten gemt lokalt på telefonen, så den kan bruges
   uden dækning.
9. **Backup.** Én SQLite-fil. Backup via Proxmox' backup af LXC'en plus en
   daglig kopi af databasefilen.
10. **Drift sættes op tidligt**, ikke til sidst. Offline og Funnel på en rigtig
    telefon er en af de største risici og testes i fase 0.
11. **Ingen automatisk skalering efter portioner** (brugerens beslutning). En
    opskrift er ét familiemåltid, som den står. I stedet en manuel gange-knap
    (×½, ×1, ×2) pr. dag, så der kan laves dobbelt til rester. Undgår skæve
    mængder som "½ dåse" og fjerner husstandsopsætningen. Almindelige
    opskrifter til 4 giver naturligt rester til jer.

## 3. Funktioner

### 3.1 Opskrifter
- **Import via link** fra understøttede sider. Titel, antal portioner,
  ingredienser, fremgangsmåde og billede gemmes lokalt. Understøtter også sider
  med generisk schema.org/Recipe-data.
- **Søg fra appen** på Valdemarsro (første version), med resultater importeret
  med ét tryk. Flere sider senere.
- **Manuel oprettelse og redigering**, fordi retterne i dag er "i hovedet".
- **Hovedingredienser:** 1-2 ingredienser pr. opskrift markeres som hoved-
  ingredienser. Bruges til tilbudsforslag. Foreslås automatisk (kød/fisk/største
  mængde), kan rettes.
- **Barnenote:** fast note pr. opskrift, fx "tag barnets portion fra før chili".
- **Portioner:** opskriftens antal portioner gemmes og vises tydeligt, men
  bruges ikke til at skalere automatisk (se §3.3).

### 3.2 Madplan
- En plan dækker en periode, der starter på indkøbsdagen (typisk søndag eller
  mandag) og løber 7 dage. Ingen fast ugestart.
- **Én ret pr. dag** til hele husstanden (aftensmad). Frokost er ikke med i
  første version.
- **Barn får noget andet:** en dag kan have en ekstra ret til barnet. Typisk
  fritekst (grød, mos, rester) uden indkøb, men kan også være en opskrift.
- **Ret-typer pr. dag:** opskrift, fritekst (intet indkøb), rester.
- **Rester:** "Rester fra <ret>" har intet indkøb og ændrer ikke kilderetten.
  Skal der laves dobbelt, sættes kilderetten manuelt til ×2.
- **Bruger rest fra:** en opskrift (fx lasagne) kan markere, at den bruger rest
  fra en anden dag (kødsovs). Brugeren markerer, hvilke af lasagnens
  ingredienser resten dækker, og de krydses af automatisk. Appen foreslår at
  sætte kilderetten til ×2, men gør det ikke selv, og vurderer ikke, om resten
  er nok.
- **Ønskeliste:** retter til ugen, som trækkes ud på dagene manuelt. Ingen
  automatisk fordeling efter holdbarhed (fravalgt).
- **Visning:** mobil = én dag ad gangen med swipe. Tablet/computer = ugegitter
  med træk og slip.

### 3.3 Mængder
- En opskrift bruges som den står: ét familiemåltid. Ingen portionsfaktorer og
  ingen husstandsopsætning.
- Hver ret i planen har en **gange-knap: ×½, ×1 (standard), ×2**. Bruges til at
  lave dobbelt til rester eller til at justere opskrifter til 2 eller 8
  personer.
- Opskriftens antal portioner vises ved retten, så det er tydeligt, når en
  opskrift er usædvanligt stor eller lille.
- Ved ×½ rundes styk-enheder (dåse, stk, pakke, æg) op til hele tal.

### 3.4 Ingredienser pr. dag
- Hver dag viser sine ingredienser, ganget med dagens gange-knap.
- Hver linje kan krydses af som **"har hjemme"**, og så kommer den ikke på
  indkøbslisten.
- Linjer, der dækkes af rester, er krydset af automatisk og markeret "rest".

### 3.5 Indkøbsliste
- Samler alle ikke-afkrydsede linjer i planen, minus basisvarer.
- Åbner på den igangværende uge (som Planlæg). Andre uger vælges med ‹ ›.
- **Sammenlægning:** samme vare + omregnelig enhed lægges sammen
  ("2 løg" + "150 g løg" → "3 løg"). Kan det ikke omregnes, vises linjerne under
  samme vare ("løg: 2 stk + 1 dl hakket").
- Hver vare viser, hvilke dage den bruges.
- **Sortering efter afdeling** i Bilka. Rækkefølgen kan ændres.
- **Afkrydsning i butikken:** store felter, én hånd. Virker offline og
  synkroniserer bagefter. Ved samtidig afkrydsning fra to telefoner vinder den
  seneste ændring pr. vare.
- **Egne varer:** fritekst ("bleer", "kaffe") kan tilføjes.
- Krydses en vare af som "har hjemme" på listen, krydses alle dens linjer af i
  planen.

### 3.6 Basisvarer
- Liste over varer, der altid er hjemme. Startliste: salt, peber, olie,
  olivenolie, smør, mel, sukker, eddike, almindelige tørrede krydderier,
  bouillonterninger. Kan redigeres.
- Kommer aldrig på indkøbslisten automatisk.
- Sammenklappet sektion under listen: "Basisvarer brugt i denne uge".
- **"Løbet tør":** sætter en basisvare på næste indkøbsliste med ét tryk.

### 3.7 Tilbud (første version: kun Bilka)
- Ugens Bilka-tilbud hentes automatisk (dagligt) fra Tjek, **kun fra Bilkas
  madvareavis** (Tjek har ingen kategorier; nonfood og halloween frasorteres).
- Tilbudsmatch vises som forslag. Usikre forslag bekræftes eller afvises med ét
  tryk, og svaret gemmes, så samme tilbud genkendes næste gang.
- Pakningsstørrelse og kilopris vises, da mange tilbud er storpakninger.
- **På indkøbslisten:** varer med et matchende tilbud markeres med pris og
  gyldighed.
- **Retforslag ved planlægning:**
  1. Egne opskrifter, hvor en hovedingrediens er på tilbud.
  2. Valdemarsro-søgning på hovedingrediensen fra tilbuddet (fx "kylling"),
     så også nye retter foreslås.

### 3.8 Login
- To brugere, brugernavn + kodeord (argon2-hash), session-cookie i 90 dage.
- Loginforsøg begrænses (rate limit), da adressen er offentlig via Funnel.
- Ingen selvregistrering.

## 4. Matchning og ingredienslæsning (udskiftelig)

Al fortolkning af ingredienser går gennem to grænseflader, så en AI-baseret
udgave kan sættes ind senere uden at ændre resten:

```
IngredientParser.parse(linje: str) -> ParsedIngredient
    # "2 dl fløde" -> {mængde: 2, enhed: "dl", vare: "fløde", note: None}

IngredientMatcher.canonical(vare: str) -> Ingredient | None
    # "oksefars" -> Ingredient("hakket oksekød")

OfferMatcher.match(tilbud: Offer, ingredienser: list[Ingredient]) -> list[Match]
    # "Hakket okse-, grise- eller grise/kalvekød" -> hakket oksekød, hakket svinekød
```

**Gratis udgave (første version):**
- **Dansk regelbaseret parser:** tal, brøker (½, ¼, 1/2), intervaller (2-3),
  danske enheder (g, kg, ml, cl, dl, l, tsk, spsk, knsp, fed, stk, dåse, pakke,
  bundt, håndfuld, skive, stængel/stængler), noter efter komma ("finthakket"),
  "salt og peber", "evt."-linjer.
- **Ingredienstabel:** kanonisk navn, synonymer, afdeling, er basisvare,
  omregning (vægt pr. stk, vægt pr. dl).
- **Tekstmatchning** af tilbud mod ingredienstabellens navne og synonymer
  (normaliseret tekst + token-overlap).
- **Læring:** brugerens rettelser gemmes som synonymer, så matchningen bliver
  bedre med tiden.

**Senere (fase 6):** Claude-udgave af samme grænseflader, eventuelt kun brugt på
det, den gratis udgave ikke kan matche. Kræver API-nøgle og forudbetalt kredit
(anslået under 5 kr./md.).

## 5. Arkitektur

```
Telefon/PC (PWA)
   │  https://madplan.<tailnet>.ts.net
   ▼
Tailscale Funnel  (container: tailscale, userspace-netværk)
   ▼
App-container
   ├─ Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic
   │    ├─ recipe-scrapers  (import)
   │    ├─ parser/matcher   (§4)
   │    └─ baggrundsjob: hent Bilka-tilbud dagligt
   ├─ Frontend: SvelteKit (statisk SPA), TypeScript, PWA
   │    └─ service worker + IndexedDB til offline indkøbsliste
   └─ SQLite-database (volume)
```

- Én Docker Compose-stak i en LXC i Proxmox. Tailscale kører i userspace-tilstand
  i sin egen container, så LXC'en ikke skal have adgang til `/dev/net/tun`.
- Backend serverer både API og frontend, så kun én tjeneste eksponeres via
  Funnel.
- Frontend og backend kommunikerer via et JSON-API. Det bruges også senere til
  Home Assistant.

### Datamodel (overblik)

| Tabel | Indhold |
|---|---|
| `user` | brugernavn, kodeords-hash |
| `recipe` | titel, kilde-URL, portioner, fremgangsmåde, billede, barnenote |
| `recipe_ingredient` | opskrift, rå tekst, mængde, enhed, ingrediens, note, hovedingrediens, gruppe |
| `ingredient` | kanonisk navn, afdeling, basisvare, g/stk, g/dl |
| `ingredient_alias` | alias → ingrediens (også brugerens rettelser) |
| `plan` | startdato (indkøbsdag), antal dage |
| `plan_meal` | plan, dato, type (opskrift/fritekst/rester), opskrift eller fritekst, gange (½/1/2), til barn (ja/nej), rest-kilde |
| `plan_line_state` | plan_meal + recipe_ingredient → har hjemme / dækket af rest |
| `wishlist_item` | plan, opskrift eller fritekst |
| `shopping_extra` | egen vare på listen, afkrydset |
| `shopping_check` | plan + ingrediens → købt (med tidsstempel til sync) |
| `pantry_request` | basisvare sat på listen via "Løbet tør" |
| `offer` | Tjek-id, butik, overskrift, pris, mængde, enhed, gyldig fra/til |
| `offer_match` | tilbud → ingrediens (automatisk eller bekræftet) |

## 6. Datakilder (efterprøvet 28-09-2026)

| Kilde | Bruges til | Status | Risiko |
|---|---|---|---|
| `recipe-scrapers` (Python) | Import fra danske opskriftssider | Testet på Valdemarsros lasagne: titel, 4 portioner, 21 ingredienslinjer korrekt | Lav. Vedligeholdt open source-bibliotek |
| Valdemarsro, Madens Verden, Arla | Import | Testet i fase 0: 92 opskrifter importeret uden fejl | Lav |
| Spis Bedre | Import | Virker ikke: 0 af 204 sider har opskriftsdata | – |
| valdemarsro.dk `/?s=` | Søgning | Returnerer links, blandet med artikler | Mellem. Uofficielt, kan ændres |
| nemlig.com `/webapi/.../Search/Search` og `?GetAsJson=1` | Søgning i opskrifter (ikke varer) og import med mængder | Returnerer JSON. Kræver en ærlig User-Agent: browser-UA sendes i kø (Queue-it) | Mellem. Uofficielt, kan ændres |
| Tjek API (`squid-api.tjek.com/v2`) | Bilka-tilbud | Testet: Bilka = dealer `93f13`, 644 tilbud i uge 40, heraf 191 i madvareavisen. Pris, mængde, enhed og gyldighed. Ingen kategorier | Mellem. Uofficielt, ingen aftale |
| Salling Group API | – | Har ikke priser eller tilbud. Ikke brugbar | – |
| Bilka ToGo | Normalpriser | Ikke efterprøvet | Udskudt |

Uofficielle kilder kan holde op med at virke. Appen skal fungere uden dem:
importerede opskrifter ligger lokalt, og manglende tilbud betyder kun, at
tilbudsmarkeringer udebliver.

## 7. Fravalgt eller udskudt

| Punkt | Afgørelse | Hvorfor |
|---|---|---|
| Største opskriftsdatabase | Fravalgt | Urealistisk. Erstattet af søgning + import |
| Alle danske butikker, billigste butik | Fravalgt | I handler i Bilka. Nettos normalpriser findes ikke |
| Netto og Rema-tilbud | Udskudt (fase 6) | Samme kilde som Bilka, let at tilføje. Kun relevant ved stor besparelse |
| To rækker (voksne/børn) | Fravalgt | Erstattet af "barn får noget andet" pr. dag |
| Automatisk fordeling efter holdbarhed | Fravalgt | De fleste varer holder 5-6 dage |
| Mealie | Fravalgt | Se §2.1 |
| Skalering efter portioner og alder | Fravalgt | Opskrift = ét familiemåltid. Manuel ×½/×1/×2 i stedet (§3.3) |
| Home Assistant-add-on/ingress | Fravalgt | Selvstændig app i Proxmox |
| Cloudflare Tunnel, nyt domæne, Tailscale på telefoner | Fravalgt | Brugerens valg |
| AI-matchning | Udskudt (fase 6) | Gratis først. Grænseflader forberedt (§4) |
| Pakningsstørrelser og prisoverslag | Udskudt | Kræver produktdata |
| Frokost/morgenmad | Udskudt | Aftensmad først |

## 8. Risici

| Risiko | Konsekvens | Håndtering |
|---|---|---|
| Dansk ingredienslæsning er for upræcis | Forkert sammenlægning, rodet liste | Testes først (fase 0) mod mindst 200 rigtige linjer. Mål: ≥ 90 % korrekt |
| Offline-liste virker dårligt i praksis | Listen kan ikke bruges i butikken | Testes først (fase 0) på rigtig telefon via Funnel |
| Tjek/Valdemarsro ændrer sig | Tilbud eller søgning holder op med at virke | Isoleret i egne moduler. Appen virker uden |
| Offentlig adresse via Funnel | Angreb på login | Rate limit, stærke kodeord, ingen registrering, opdateringer |
| Tailscale ændrer gratis-vilkår | Ingen adgang udefra | Kun vejen ind skal udskiftes, ikke appen |
