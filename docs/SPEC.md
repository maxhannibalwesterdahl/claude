# Madplan – specifikation

Ugentlig madplan til eget brug for én husstand. Opskrifter importeres fra danske
opskriftssider, ingredienser lægges sammen på tværs af ugen, og indkøbslisten
bruges på mobilen i Bilka.

Status: specifikation, intet er bygget endnu. Se [PLAN.md](PLAN.md) for rækkefølge.

---

## 1. Rammer

| | |
|---|---|
| Brugere | 2 voksne med hver sit login, én fælles husstand |
| Husstand | 2 voksne + 1 barn (født ca. 2025, 1 år i dag) |
| Primær enhed | Mobil (PWA på hjemmeskærmen). Tablet/computer til planlægning |
| Indkøb | Én stor tur om ugen i Bilka, søndag eller mandag |
| Drift | Egen LXC-container i Proxmox, adskilt fra Home Assistant |
| Adgang udefra | Tailscale Funnel (Tailscale kun på serveren, ikke på telefonerne) |
| Budget | Gratis i drift. Ingen betalte API'er i første version |

## 2. Gennemgang af den aftalte plan – rettelser

Planen fra idéfasen er gennemgået. Følgende er ændret eller præciseret:

1. **Mealie droppes som motor.** Efter beslutningerne skulle vi selv bygge
   madplanen (barneportioner, rester, ønskeliste), indkøbslisten (sammenlægning,
   basisvarer, afkrydsning pr. dag) og den danske ingredienslæsning. Mealie ville
   kun have leveret opskriftslagring og import, og import kommer fra biblioteket
   `recipe-scrapers`, som vi kan bruge direkte. Mealie ville koste en ekstra
   tjeneste, et ekstra login, synkronisering mellem to datamodeller og afhængighed
   af deres API. Testet: `recipe-scrapers` læser Valdemarsro korrekt og har
   færdige læsere til valdemarsro.dk, madensverden.dk, dr.dk, spisbedre.dk,
   sundpaabudget.dk og hellofresh.dk.
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
- **Portioner:** fra opskriften. Hvis siden ikke oplyser det, antages 4.

### 3.2 Madplan
- En plan dækker en periode, der starter på indkøbsdagen (typisk søndag eller
  mandag) og løber 7 dage. Ingen fast ugestart.
- **Én ret pr. dag** til hele husstanden (aftensmad). Frokost er ikke med i
  første version.
- **Barn får noget andet:** en dag kan deles, så voksenretten kun beregnes til de
  voksne og barnets ret kun til barnet.
- **Ret-typer pr. dag:** opskrift, fritekst (intet indkøb), rester.
- **Rester:** "Rester fra <ret>" har intet indkøb. Kilderetten beregnes med
  ekstra portioner svarende til restedagens portioner.
- **Bruger rest fra:** en opskrift (fx lasagne) kan markere, at den bruger rest
  fra en anden dag (kødsovs). Kilderetten får ekstra portioner, og brugeren
  markerer, hvilke af lasagnens ingredienser resten dækker. De bliver krydset af
  automatisk. Appen vurderer ikke, om resten er nok.
- **Ønskeliste:** retter til ugen, som trækkes ud på dagene manuelt. Ingen
  automatisk fordeling efter holdbarhed (fravalgt).
- **Visning:** mobil = én dag ad gangen med swipe. Tablet/computer = ugegitter
  med træk og slip.

### 3.3 Portioner
- Husstandens medlemmer oprettes med rolle og fødselsdato.
- Portionsfaktor pr. person (kan overskrives):

  | Alder | Faktor |
  |---|---|
  | Voksen | 1,0 |
  | 0-1 år | 0,2 |
  | 1-3 år | 0,3 |
  | 4-6 år | 0,5 |
  | 7-10 år | 0,7 |
  | 11+ år | 1,0 |

- Dagens portioner = summen af faktorerne for dem, der spiser retten. I dag:
  2,3 portioner. Opskriften skaleres med `portioner / opskriftens portioner`.

### 3.4 Ingredienser pr. dag
- Hver dag viser sine ingredienser, skaleret.
- Hver linje kan krydses af som **"har hjemme"**, og så kommer den ikke på
  indkøbslisten.
- Linjer, der dækkes af rester, er krydset af automatisk og markeret "rest".

### 3.5 Indkøbsliste
- Samler alle ikke-afkrydsede linjer i planen, minus basisvarer.
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
- Ugens Bilka-tilbud hentes automatisk (dagligt) fra Tjek.
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
| `household_member` | navn, rolle (voksen/barn), fødselsdato, faktor-overskrivning |
| `recipe` | titel, kilde-URL, portioner, fremgangsmåde, billede, barnenote |
| `recipe_ingredient` | opskrift, rå tekst, mængde, enhed, ingrediens, note, hovedingrediens, gruppe |
| `ingredient` | kanonisk navn, afdeling, basisvare, g/stk, g/dl |
| `ingredient_alias` | alias → ingrediens (også brugerens rettelser) |
| `plan` | startdato (indkøbsdag), antal dage |
| `plan_meal` | plan, dato, type (opskrift/fritekst/rester), opskrift, spisende (alle/voksne/barn), rest-kilde |
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
| valdemarsro.dk `/?s=` | Søgning | Returnerer links, blandet med artikler | Mellem. Uofficielt, kan ændres |
| Tjek API (`squid-api.tjek.com/v2`) | Bilka-tilbud | Testet: Bilka = dealer `93f13`, 200+ tilbud/uge med pris, mængde, enhed og gyldighed | Mellem. Uofficielt, ingen aftale |
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
