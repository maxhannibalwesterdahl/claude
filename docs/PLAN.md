# Madplan – byggeplan

Rækkefølgen er valgt, så de største risici testes først, og så hver fase
efterlader noget, der kan bruges. Se [SPEC.md](SPEC.md) for hvad og hvorfor.

Hver fase har et **færdigt-kriterie**. En fase er ikke færdig, før kriteriet er
opfyldt på den rigtige server og en rigtig telefon.

---

## Fase 0 – Afklar risici (før rigtig kode)

Formål: finde ud af, om de tre ting, der kan vælte projektet, holder.

1. **Dansk ingredienslæser** – ✅ færdig: 93,6 % i blind måling, se
   [fase0-ingredienslaeser.md](fase0-ingredienslaeser.md)
   - Hent ingredienslinjer fra ca. 30 forskellige Valdemarsro-opskrifter
     (≥ 200 linjer) og gem dem som testdata.
   - Skriv den regelbaserede parser (§4 i SPEC) og tests mod testdataene.
   - *Færdig:* ≥ 90 % af linjerne giver korrekt mængde, enhed og vare.
     Fejlene er listet og kategoriseret.
2. **Bilka-tilbud** – ✅ færdig: tilbud hentes, varekobling god nok, tilbudskobling
   delvis. Se [fase0-tilbud-og-kobling.md](fase0-tilbud-og-kobling.md)
   - Script, der henter alle Bilka-tilbud for ugen fra Tjek med sideinddeling.
   - Første udgave af tilbudsmatchning mod en lille ingredienstabel
     (ca. 50 almindelige varer).
   - Kobling af læserens varenavne til ingredienstabellen, målt på varerne fra
     fase 0.1 ("citron", "øko citron", "citronsaft" osv.). Det er her,
     AI-spørgsmålet reelt afgøres.
   - *Færdig:* ugens tilbud hentes komplet. Andelen af madvaretilbud, der
     matches korrekt, er målt og noteret.
3. **Drift, Funnel og offline**
   - LXC i Proxmox med Docker. Tailscale-container med Funnel foran en minimal
     PWA (én side med en liste, der kan krydses af).
   - *Færdig:* åbnes fra begge telefoner uden Tailscale, kan lægges på
     hjemmeskærmen, og afkrydsning virker i flytilstand og synkroniserer
     bagefter.

**Beslutningspunkt:** Hvis parseren ligger langt under 90 %, tages AI-matchning
op igen, før vi fortsætter.

## Fase 1 – Opskrifter

- Projektstruktur: FastAPI + SQLite + Alembic, SvelteKit-frontend, Docker
  Compose, tests i CI.
- Login (to brugere, oprettes fra kommandolinjen).
- Import via link, opskriftsliste, opskriftsvisning, manuel oprettelse og
  redigering.
- Ingredienstabel med startdata (navne, synonymer, afdeling, basisvare,
  omregninger).
- Markering af hovedingredienser (automatisk forslag + ret).
- *Færdig:* jeres 20-30 faste retter er importeret eller oprettet, og deres
  ingredienser er læst korrekt eller rettet.

## Fase 2 – Madplan

- Plan fra valgt indkøbsdag, 7 dage.
- Ret pr. dag: opskrift, fritekst, rester. "Barn får noget andet".
- Gange-knap pr. ret (×½, ×1, ×2).
- "Bruger rest fra" med automatisk afkrydsning og forslag om ×2 på kilderetten.
- Ønskeliste.
- Mobil: én dag ad gangen. Computer: ugegitter med træk og slip.
- Ingredienser pr. dag, med "har hjemme".
- *Færdig:* en hel uge er planlagt på telefonen, og mængderne er kontrolleret
  i hånden for mindst tre retter, inklusive én ret på ×2 og en rest-kobling.

## Fase 3 – Indkøbsliste

- Sammenlægning på tværs af dage og inden for samme opskrift.
- Basisvarer, sammenklappet sektion, "Løbet tør".
- Sortering efter afdeling. Egne varer.
- Offline-afkrydsning med synkronisering (bygger på fase 0).
- *Færdig:* én rigtig indkøbstur i Bilka er gennemført kun med appen.
  Fejl og mangler noteres.

**Herfra er appen brugbar i hverdagen.** Resten er forbedringer.

## Fase 4 – Tilbud

- Dagligt job, der henter Bilka-tilbud.
- Tilbudsmatchning mod ingredienstabellen, med rettelser gemt som synonymer.
- Tilbudsmarkering på indkøbslisten.
- *Færdig:* tilbud vises på listen, og forkerte matches kan rettes med to tryk.

## Fase 5 – Søgning og forslag

- Søgning på Valdemarsro fra appen, med artikler frasorteret, og import med ét
  tryk.
- Retforslag ud fra tilbud: egne opskrifter først, derefter Valdemarsro-søgning
  på hovedingrediensen.
- *Færdig:* ved planlægning vises forslag ud fra ugens tilbud, og mindst ét
  forslag er brugt i en rigtig uge.

## Fase 6 – Senere (ingen rækkefølge)

- Claude-baseret parser/matcher bag de eksisterende grænseflader.
- Netto- og Rema-tilbud (samme kilde), sammenlignet pr. kg/l, kun vist ved
  stor besparelse.
- Indkøbsliste i Home Assistant (to-do-liste via vores API).
- Flere søgekilder (Madens Verden, DR Mad, Spis Bedre).
- Pakningsstørrelser og prisoverslag.
- Frokost og madpakker.

---

## Tjekliste før første brug i hverdagen (efter fase 3)

- [ ] Backup af LXC i Proxmox er sat op og en gendannelse er afprøvet
- [ ] Daglig kopi af SQLite-filen
- [ ] Stærke kodeord for begge brugere
- [ ] Rate limit på login er testet
- [ ] Begge telefoner har appen på hjemmeskærmen
