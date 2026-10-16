# UI-gennemgang: designsystem, tilgængelighed og responsivt

Rolle: UI-designer. Gren `rolig`, lokal kopi på port 8102 med egen `DATA_DIR`. Tjekket i browser (telefon 320, 375 og 667x375 på langs, tablet 768, computer 1280; lys og mørk) og i koden. Kontrastforhold er regnet ud fra CSS-værdierne i `app.css`.

## 1. Kort konklusion

**Klar til go-live med forbehold.** Designsystemet er usædvanligt stramt for en app af denne størrelse: farver, radius, trykflader og skygger kommer næsten alle fra tokens, alle tekstfarver i både lys og mørk tilstand består 4,5:1 (undtagen pladsholdere), fokusringen er tydelig, ark er rigtige `<dialog>`-elementer med fokusstyring, og swipe og langt tryk har knapper som alternativ. Ingen sider får vandret scroll ned til 320 px.

Der er ingen kritiske eller høje fund. De seks mellemfund er alle små rettelser (sidetitler, pladsholderkontrast, `scroll-padding`, chips der løber over, felt-kanter, pinch-zoom på rækker) og bør tages før eller lige efter go-live. Resten er pæn-at-have og token-oprydning.

Fund: **0 kritiske, 0 høje, 6 mellem, 13 lave.**

## 2. Fund

| ID | Alvor | Titel | Sted |
|---|---|---|---|
| UI-01 | Mellem | Alle sider hedder "Madplan" (WCAG 2.4.2, niveau A) | `app.html:14` |
| UI-02 | Mellem | Pladsholdertekst under 4,5:1 i lys og mørk | `app.css:196` (ingen `::placeholder`) |
| UI-03 | Mellem | Fokuseret element skjules delvist bag fast fanelinje og dock | `app.css:142`, `app.css:672` |
| UI-04 | Mellem | Lange tekster løber ud over en chip | `app.css:432`, `lib/uge/ChooserSheet.svelte:166` |
| UI-05 | Mellem | Tekstfelter har ingen synlig kant (1,05-1,14:1 mod baggrunden) | `app.css:196` |
| UI-06 | Mellem | Pinch-zoom blokeres på indkøbsrækker og arkets top | `lib/ui/SwipeRow.svelte:143`, `lib/ui/Sheet.svelte:239` |
| UI-07 | Lav | Fejlbesked på login ligner et inputfelt og er ikke koblet til felterne | `routes/login/+page.svelte:45`, `app.css:623` |
| UI-08 | Lav | Skriftstørrelser: ca. 36 rå px-værdier, seks næsten ens | `app.css` og komponenter |
| UI-09 | Lav | Øvrige hårdkodede værdier (skygger, radius, varigheder) | se detaljer |
| UI-10 | Lav | Samme mønster, forskellig komponent (tilbage, filtre, afkrydsning, logo) | se detaljer |
| UI-11 | Lav | Al tekst i px: brugerens standardskriftstørrelse følges ikke | `app.css:36-44` |
| UI-12 | Lav | Luk-knappen er usynlig i ark med tallerken/"Færdig" ved titlen | `lib/ui/Sheet.svelte:160`, `:258` |
| UI-13 | Lav | Synlig tekst i ugedagsknap står ikke i tilgængeligt navn (2.5.3) | `lib/uge/WeekGrid.svelte:56` |
| UI-14 | Lav | Overskrifter indeholder knapper og tællere; dagene er ikke en liste | `routes/lav/[dato]/+page.svelte:251,255`, `routes/opskrift/[id]/+page.svelte:118` |
| UI-15 | Lav | Glidende scroll ignorerer reduceret bevægelse | `lib/RecipeEditor.svelte:214`, `lib/rydop/IngredientList.svelte:105` |
| UI-16 | Lav | PWA: kun lys splash/tema, iOS-statuslinje uverificeret | `static/manifest.webmanifest`, `app.html:7-9` |
| UI-17 | Lav | `dvh` uden fallback; dock uden safe-area i siden | `lib/ui/Sheet.svelte`, `app.css:672` |
| UI-18 | Lav | Små tekster (11-12 px) og svage fremdriftsindikatorer | `routes/+layout.svelte:154`, `lib/ui/SwipeRow.svelte`, `lib/lav/StepView.svelte:204` |
| UI-19 | Lav | ARIA-detaljer: "vis alle" ens x4, dobbelt alert, ConfirmDialog | `lib/rydop/ReviewCard.svelte:44`, `routes/indkob/+page.svelte:416`, `lib/ConfirmDialog.svelte` |

## 3. Detaljer pr. fund

### UI-01 Alle sider hedder "Madplan" (Mellem)
- **Genskab:** Åbn Uge, Indkøb, Opskrifter, en opskrift. `document.title` er "Madplan" overalt. Der findes ingen `<svelte:head>` eller `<title>` andre steder end `app.html`.
- **Forventet:** Hver side har en titel, der beskriver den (WCAG 2.4.2, niveau A). SvelteKits rutemelder læser `document.title` op ved hver navigation, så skærmlæserbrugere hører "Madplan" ved hvert skift. Faneoversigt og historik er også ens.
- **Forslag:** `<svelte:head><title>Indkøb · Madplan</title></svelte:head>` i hver rute (opskrift: titlen på retten, `lav`: "Lav mad · {ret}").

### UI-02 Pladsholdertekst under 4,5:1 (Mellem)
- **Genskab:** Alle felter med `placeholder` ("Søg i egne, Valdemarsro og nemlig", "Tilføj vare, fx bleer", "Fx kød op af fryseren"). Der er ingen `::placeholder`-regel, så browserens `#757575` bruges i begge temaer (aflæst med `getComputedStyle(el,'::placeholder')`).
- **Målt:** lys på `--band` 4,04:1, på `--paper` 4,41:1 (kun hvid `--card` består med 4,61:1). Mørk på `--card` 3,46:1, på `--band` 3,63:1, på `--paper` 3,93:1.
- **Forslag:** `::placeholder { color: var(--muted); opacity: 1; }` (5,3-6,9:1 i begge temaer).

### UI-03 Fokus skjules delvist bag fast fanelinje (Mellem)
- **Genskab:** 375x812, `/rydop/varer`, tryk Tab 22 gange. Fokuseret række ("dild") ligger med bunden 770 px, mens fanelinjen starter ved 756 px: fokusringen er skåret af. Der er ingen `scroll-padding-bottom`.
- **Forventet:** WCAG 2.4.11: fokuseret element må ikke være helt dækket af fast indhold. Her er det delvist; på sider med `.dock` (Indkøb) eller `.fab` kan det blive helt dækket.
- **Forslag:** `html { scroll-padding-bottom: calc(var(--nav-h) + env(safe-area-inset-bottom) + 16px); }` og `html:has(main.docked) { scroll-padding-bottom: calc(var(--nav-h) + env(safe-area-inset-bottom) + 92px); }`.

### UI-04 Lange tekster løber ud over en chip (Mellem)
- **Genskab:** 320 px, åbn en tom dag. Chips i "Uden indkøb" er `white-space: nowrap; max-width: 100%` uden `overflow`. Jeg satte teksten til "Rester fra langtidsstegt flæskesteg med hjemmelavet rødkål" (som en rigtig opskriftstitel giver): chippen er 288 px bred, teksten 433 px og løber ud af pillen og ud af arket. Samme chip bruges til ønsker (Uge) og forslag.
- **Forventet:** Teksten kortes med ellipsis eller chippen bryder over to linjer.
- **Forslag:** `.chip { overflow: hidden; text-overflow: ellipsis; }` (behold 44 px trykflade), eller `white-space: normal; min-height: var(--chip-h); height: auto; padding-block: 8px;` for chips med brugertekst.

### UI-05 Tekstfelter har ingen synlig kant (Mellem)
- **Genskab:** Felter bruger kun fyldfarven `--band` (`app.css:196`), og ligger på `--paper` eller `--card`. Kontrast mellem felt og baggrund: lys 1,09:1 / 1,14:1, mørk 1,08:1 / 1,05:1.
- **Forventet:** WCAG 1.4.11 kræver 3:1 for den grænse, der viser, hvor et felt er, når intet andet viser det. Ledetekst og pladsholder hjælper, men et tomt felt på `--paper` er svært at se for svagsynede.
- **Forslag:** `box-shadow: inset 0 0 0 1px var(--ring)` på felter (3,4:1 lys, 4,6-5,2:1 mørk), eller en 1 px kant. Det er den eneste rettelse, der ændrer udseendet mærkbart; vurder mod "Rolig"-udtrykket.

### UI-06 Pinch-zoom blokeres på indkøbsrækker og arkets top (Mellem)
- **Sted:** `SwipeRow.svelte:143` `.slide { touch-action: pan-y; }` og `Sheet.svelte:239` `.head { touch-action: none; }`.
- **Problem:** `pan-y` tillader kun lodret panorering, så knibe-zoom starter ikke, når fingrene lander på en række. Indkøbslisten er den skærm, hvor svagsynede oftest vil zoome. (Siden er ellers zoombar: viewport har ikke `maximum-scale`.)
- **Forslag:** `touch-action: pan-y pinch-zoom` på `.slide`. På `.head`: `pan-x pinch-zoom` er ikke nok til trækket nedad, så behold `none` kun på `.grab` (håndtaget), og lad titlen have `pan-y pinch-zoom` med pointer-capture som nu.

### UI-07 Fejlbesked på login ligner et felt (Lav)
- **Genskab:** Log ind med forkert kodeord. Beskeden "Forkert brugernavn eller kodeord" står i en grå `--band`-boks med samme radius som felterne, direkte under kodeordsfeltet, og ligner et tredje felt. Den har `role="alert"` (godt), men felterne har ikke `aria-invalid`/`aria-describedby`.
- **Forslag:** Giv `.msg` en venstre kant eller et ikon i `--tomat`, og sæt `aria-describedby` på begge felter (valgfrit `aria-invalid="true"` efter fejl). Samme `.msg` bruges overalt, så ret den centralt.

### UI-08 Skriftstørrelser (Lav)
- Tokens: 9 stk. (`--fs-cap` 13,5 brugt 14 gange, `--fs-row` 17 5 gange osv.). Ved siden af står ca. 36 rå værdier: 14,5 px (7), 15 px (6), 15,5 px (3), 16 px (2), 16,5 px (4), 17 px (2), 18, 20, 21 px, 12 px (2), 12,5 px (4, samme værdi som `--fs-label`), 13,5 px (2, samme som `--fs-cap`), 11 px.
- Seks næsten ens størrelser (14,5 / 15 / 15,5 / 16 / 16,5 / 17) giver ikke synligt hierarki, kun drift. Eksempler: `DayRow.svelte:100,115,149`, `IngredientRow.svelte:82`, `Reminders.svelte:174,222`, `routes/opskrift/[id]/+page.svelte:221,227,258`.
- **Forslag:** Saml i 5 trin (13,5 / 15 / 17 / 18 / 24) som `--fs-*`, og erstat de rå værdier. Samme for `line-height` (rå `30px`, `36px`, `28px` m.fl.).

### UI-09 Øvrige hårdkodede værdier (Lav)
- Skygger med rå `rgba`: `Plate.svelte:63,76`, `Segmented.svelte:75`, `SwipeRow.svelte:147`, `.rnd.float` i `app.css:420`. Mørk tilstand har ikke egne værdier (kanten fra `--shadow` bruges ikke her), så den lille skygge på valgt segment ses ikke i mørk.
- Radius uden token: `Segmented.svelte:48,60` (12/9), `WeekGrid.svelte:89` (14), `AddBar.svelte:48` (16 = `--r-tile`), `.tag` 7 px, `Sheet.svelte:245` 3 px.
- Varigheder uden token: `SwipeRow` 160 ms (både CSS og JS), `Fold.svelte:35` 0,15 s, `routes/indkob/+page.svelte:484` 0,3 s. `--t-sheet` og `--t-tick` findes, men dækker ikke disse.
- Højder: input `min-height: 48px` er ikke et token (`--btn-h` er 50), `--btn-sm-h` 40.
- Tallerkenpaletten i `Plate.svelte` er bevidst fast (illustration) og er i orden.
- **Forslag:** `--shadow-sm`, `--r-xs`/`--r-seg`, `--t-slide`, `--field-h`; mørk variant af `--shadow-sm` som en kant.

### UI-10 Samme mønster, forskellig komponent (Lav)
- **Tilbage:** øverst til højre i `ScreenHeader` (en cirkel ved siden af handlinger), men øverst til venstre i `Hero` (`/opskrift`, `/lav`). Samme `BackButton`, to placeringer.
- **Vælg ét af flere:** filtre på Opskrifter er `.chip[aria-pressed]` (`routes/opskrifter/+page.svelte:113-121`), mængde i dagsarket er `Segmented` (radiogruppe). Begge er enkeltvalg.
- **Afkrydsning:** `Tick` (26/30 px, egen tegning) i ingredienser og indkøb, men indbygget afkrydsningsfelt med `accent-color` og 22 px i `Reminders.svelte:225` og `IngredientForm.svelte:34`.
- **Søgefelt:** globalt felt på Opskrifter, egen `.find` i `ChooserSheet`, egen `.bar` i `AddBar`. Tre udseender.
- **Logo:** loginsidens SVG (`login/+page.svelte:30`, skål `M14 30h36a18 18 0 0 1-36 0z`) er ikke identisk med `static/icon.svg` (`M12 30h40a20 20 0 0 1-40 0z`).
- **Destruktivt:** "Fjern", "Slet denne uge" og bekræftknappen i `ConfirmDialog` bruger alle samme tomat som "Lav mad". Det er et dokumenteret valg i `app.css` ("kun én handlingsfarve"), og bekræftelsesdialogen afbøder det. Nævnt for fuldstændighedens skyld.

### UI-11 Al tekst i px (Lav)
- Ingen `font-size` i `rem`/`em` (kun `6.5rem` og `max(16px, 1rem)`). Sidezoom virker (kontrolleret ned til 320 px bredde = 400 % på 1280, ingen vandret scroll på nogen side), men en bruger, der har hævet browserens standardskriftstørrelse, får ingen effekt. Faste højder (`.chip` 36 px, `.btn` 50 px, linjehøjder i px) betyder også, at tekstafstand ikke kan åbnes op.
- **Forslag:** Tokens i `rem` (`--fs-body: 1.0625rem` osv.). Lav prioritet, fordi zoom fungerer.

### UI-12 Luk-knappen er usynlig i visse ark (Lav)
- `Sheet.svelte:160` og `:258-266`: når der er en `aside` (tallerken i dagsarket, "Færdig"), er Luk reduceret til 1x1 px og vises kun ved tastaturfokus. Verificeret: "Luk" er 1x1 i arket for Lørdag 17. okt.
- Skærmlæsere og tastatur har den; mus-, switch- og talestyringsbrugere kan kun lukke med baggrund, Escape eller træk (sidstnævnte kun på telefon). Talestyring ("klik Luk") finder den, men uden synligt mærke.
- **Forslag:** Vis Luk altid på computer (`@media (min-width: 700px)`), eller læg den ved siden af `aside`.

### UI-13 Synlig tekst i ugedagsknap (Lav)
- `WeekGrid.svelte:56`: knappen viser "I aften" eller "Lør 17.", men `aria-label` er "fredag 16. oktober: Frikadeller...". Talestyring ("klik I aften") og WCAG 2.5.3 (Label in Name) rammes. Samme i `DayRow` ("Lør 17. Pasta ...") er i orden, fordi navnet er den synlige tekst.
- **Forslag:** Start labelen med det synlige: "I aften, fredag 16. oktober: ...".

### UI-14 Overskrifter og lister (Lav)
- `h2.sl` får en `<span>` og i et tilfælde en `<button>` med: "FIND FREM 0 af 4", "FREMGANGSMÅDE Trin for trin" (`lav/[dato]/+page.svelte:255-257`), "INGREDIENSER stjerne = hovedingrediens". Overskriftens navn bliver hele strengen, og en knap inde i en overskrift er uheldig i overskriftsnavigation.
- Ugens dage (`DayRow`) og ingredienser i opskriften er ikke i `<ul>` (Uge har 0 lister), så skærmlæsere får ikke "liste, 7 punkter".
- **Forslag:** Flyt tællere/knapper ud af `h2` (en `div.sl` med `h2` + `span`). Gør dagene til `<ul><li>`.

### UI-15 Glidende scroll ignorerer reduceret bevægelse (Lav)
- Den globale `prefers-reduced-motion`-regel sætter `scroll-behavior: auto`, men `scrollIntoView({ behavior: 'smooth' })` i `RecipeEditor.svelte:214` og `IngredientList.svelte:105` angiver adfærden eksplicit og overstyrer den. Ark og swipe respekterer indstillingen korrekt (JS tjekker `matchMedia`).
- **Forslag:** `behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'`.

### UI-16 PWA (Lav, delvist uverificeret)
- Manifest: ikoner 192/512 findes, `icon-512` er `any maskable`, og motivet ligger inden for den maskable sikre zone (tjekket: yderste punkt 166 px fra midten af 205). Fint. Mangler `id`, `scope`, `orientation`. `theme_color` og `background_color` er kun `#FAFAF7`: i mørk tilstand giver Android en hvid splash. `<meta name="theme-color">` har begge temaer (godt) i `app.html`.
- iOS: `apple-mobile-web-app-status-bar-style` er `default`, og der er ingen `apple-touch-startup-image`, så iOS viser hvid startskærm i mørk tilstand. Koden (`Hero.svelte`: "fladen går op bag telefonens statuslinje", `env(safe-area-inset-top)` i `main`) er skrevet til en gennemsigtig statuslinje, men `default` placerer indholdet under linjen. Hvordan statuslinjen ser ud i mørk PWA på iPhone **kunne ikke efterprøves** her.
- **Forslag:** Test på en iPhone i lys og mørk. Overvej `black-translucent` kun hvis hero-flader og tekstfarve er afstemt, ellers fjern safe-area-top-tricket. Tilføj `<meta name="color-scheme" content="light dark">`.

### UI-17 `dvh` og safe-area i siden (Lav)
- `88dvh`/`92dvh` i `Sheet.svelte` har ingen `vh`-fallback (ældre iOS før 15.4 ignorerer reglen, så arket mister sin maksimale højde). `.dock` bruger `left: max(12px, ...)` uden `env(safe-area-inset-left/right)`: på en iPhone på langs kan feltet røre notchen. `nav` har heller ikke safe-area i siderne (indholdet er centreret og påvirkes sjældent).
- Landskab 667x375: dagsarket giver kun 177 px til indholdet (header 85 + søgefelt i bunden). Brugbart, men trangt.

### UI-18 Små tekster og svage indikatorer (Lav)
- Badge på Indkøb: 11 px (`+layout.svelte:154`); "Har hjemme" under swipe: 12 px. Under det øvrige minimum (12,5-13,5 px).
- Fremdriftslinjen på Indkøb og trin-stregerne i Lav mad bruger `--line` mod `--paper`: 1,15:1 lys / 1,31:1 mørk. Mængden står også som tekst ("0 af 4", "TRIN 1 AF 3"), så ingen information går tabt, men selve stregen ses næsten ikke (mørk tilstand tydeligst).
- Kantlinjen om `.chip` (`--chipline`, 1,3-1,6:1) og pil-knapper er i orden, fordi tekst bærer betydningen.

### UI-19 ARIA-detaljer (Lav)
- `ReviewCard.svelte:44`: fire knapper hedder alle "vis alle" uden kontekst. Giv `aria-label="Vis alle opskrifter med {vare}"`.
- `routes/indkob/+page.svelte:416`: `role="alert"` og `aria-live="assertive"` er dobbelt (alert er allerede assertive).
- `ConfirmDialog.svelte`: er en `<dialog>` med `aria-labelledby`; en bekræftelse ville være mere præcis som `role="alertdialog"` med `aria-describedby`. Fokus lander korrekt på "Annullér".

## 4. Hvad der er tjekket og fundet i orden

**Farvekontrast (regnet, WCAG 1.4.3 / 1.4.11)**

| Par | Lys | Mørk |
|---|---|---|
| `--ink` på `--paper` | 16,5 | 15,5 |
| `--muted` på paper / card / band / soft | 5,3 / 5,5 / 4,8 / 4,9 | 6,9 / 6,1 / 6,4 / 5,6 |
| `--tomat` på paper / card / soft / tomat-soft | 5,1 / 5,3 / 4,7 / 4,7 | 6,0 / 5,3 / 4,8 / 5,0 |
| `--ontomat` på `--tomat` (primærknap) | 5,3 | 6,3 |
| `--onkobt` på `--kobt` (swipe, flueben) | 5,5 | 7,6 |
| `--paper` på `--ink` (valgt chip) | 16,5 | 15,5 |
| `--ring` mod paper / card (afkrydsningsring, 3:1) | 3,4 / 3,6 | 5,2 / 4,6 |
| `--faint` (kun ikon "mere", 3:1) | 3,4 | 5,2 |

`--faint` bruges kun til et ikon (`ItemRow.svelte:107`), aldrig til tekst, som kommentaren lover. Deaktiverede knapper er undtaget.

**Fokus og tastatur**
- `:focus-visible` er 2 px `--ink` med 2 px afstand og ses tydeligt i lys og mørk (set på Indkøb i mørk). Rækker i beskårne rammer bruger `outline-offset: -2px` korrekt. Skjulte afkrydsningsfelter (`.sr`) viser ringen på rækken via `:has(input:focus-visible)`.
- Ark: rigtige `<dialog>` med `showModal()`, `aria-labelledby`, Escape lukker, Tab holdes inde, fokus går tilbage til den, der åbnede (verificeret med Escape på Uge). `Segmented` har roving tabindex og piletaster. Piletaster i Lav mad overtager ikke fra felter.
- Swipe-rækken har ikke noget, der kun kan gøres med træk: "Har hjemme" findes i rækkens ark. Langt tryk (`longpress`) har knappen "Mere om ..." ved siden af og åbner også med højreklik/menutast.
- Ugens drag-and-drop på computer har alternativ i dagens ark ("Flyt") og ønskelisten (WCAG 2.5.7).

**Trykflader (målt i browseren)**
- Alle knapper og links er mindst 24 px; synlige mål på 36-40 px (`.rnd` 40, `.chip` 36, `.btn.sm` 40, `Segmented` 38, `Tick`-rækker) har usynlige forlængelser til 44 px (`::after`). Rækker, `kv`, `op` og store knapper er 44-60 px. Små knapper i tekst (`vis alle`, "Ret felterne") har forlænget trykflade.
- Ingen side har vandret scroll ved 320 px (tjekket: Uge, Indkøb, Opskrifter, opskrift, rediger, ny, importer, Ryd op, Alle varer, Basisvarer, Butik, Lav mad).

**Semantik**
- `lang="da"`, `<main>`, `<nav aria-label="Hovedmenu">`, `aria-current="page"` på aktiv fane, ét `<h1>` pr. side, `role="progressbar"` på indkøbsstregen, `role="status"`/`alert` til beskeder (32 steder), `aria-pressed` på filtre og indkøbsrækker, `aria-expanded` på "vis alle", skjulte ikoner (`aria-hidden`), `alt=""` på dekorative billeder. Felter har synlig ledetekst eller `aria-label`. Indkøbsfanens tal er en del af linkets navn.
- Zoom er ikke slået fra (`viewport` uden `maximum-scale`). Inputs er mindst 16 px, så iPhone ikke zoomer ind.

**Reduceret bevægelse**
- Global regel i `app.css:103` plus JS-tjek i `Sheet` og `SwipeRow`. (Undtagelse: UI-15.)

**Responsivt**
- Telefon 375: Uge, Indkøb, Opskrifter, Lav mad (oversigt og trin), ark, login ser rene ud i lys og mørk. Tablet 768: enkelt kolonne på 640 px, centreret. Computer 1280: ugen som 7 kort med indkøbssøjle ved siden af, to spalter fra 900 px.
- Lange titler bryder over flere linjer i rækker og kort (tjekket med 85 tegn på 320 px). Sikre områder: `env(safe-area-inset-*)` bruges i `main`, nav, `.fab`, `Hero`, ark og knapper nederst i Lav mad.
- Håndtaget i arkets top, træk-for-at-lukke og tastaturløft (`--kb`) er gennemtænkt.

## 5. Hvad der ikke kunne testes

- **Rigtig iPhone** (safe-area, statuslinje i PWA, tastaturløft med `visualViewport`, swipe fra kanten, `-webkit-touch-callout`). Kun emuleret viewport i desktopbrowser.
- **Skærmlæser** (VoiceOver/TalkBack) er ikke kørt. ARIA er vurderet i kode og tilgængelighedstræ.
- **Touch-bevægelser** (swipe, langt tryk, træk i ark) er gennemgået i koden, ikke fysisk udført; browserværktøjet sender musehændelser.
- **Android-installation og splash** (manifest) og **ikon på hjemmeskærm** er ikke prøvet.
- **Beskeder (push)** og `Reminders`-kortet vises ikke i en browser uden push-understøttelse; kun koden er set.
- **Billeder fra importerede opskrifter** (`Hero` med foto, `Plate` med `img`) er ikke set med rigtige fotos; kun de tegnede tallerkener.
- Testdata blev lavet via API'et i den lokale kopi (fem opskrifter, én uge); katalogvarerne i indkøb står derfor som "appen kender ikke varen", hvilket er en følge af testdata og ikke et designfund.
- Bemærkning om testmiljøet: browserpanelet deles med andre agenter. Jeg brugte en egen fane og værtsnavnet `ui.localhost:8102` for ikke at dele cookies med de andre kopier på `127.0.0.1`.
