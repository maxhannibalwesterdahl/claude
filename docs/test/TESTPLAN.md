# Testplan før go-live: hele systemet igennem

Gren: `rolig`. Udgangspunkt: 211 backend-tests grønne, frontend bygger.

Seks agenter arbejder samtidig, hver med sit fokus. Ingen af dem ændrer
eksisterende kode. Hver skriver sin rapport i `docs/test/`. Bagefter samles
fundene i `docs/test/SAMLET.md` med en prioriteret liste til go-live.

## Hold og ansvar

| # | Rolle | Spørgsmål de skal svare på | Rapport | Port |
|---|---|---|---|---|
| 1 | UX-designer | Kan en ny familie komme fra login til en madplan og en indkøbsliste uden hjælp? Hvor går de i stå? | `ux.md` | 8101 |
| 2 | UI-designer | Er designet ensartet, læsbart og tilgængeligt (WCAG 2.2 AA) på telefon og computer? | `ui.md` | 8102 |
| 3 | Whitehat | Kan én familie se eller ændre en anden families data? Kan man komme ind uden login? Kan input misbruges? | `sikkerhed.md` | 8103 |
| 4 | Senior udvikler (kode) | Er koden korrekt, vedligeholdelig og fri for skjulte fejl? | `kode.md` | – |
| 5 | Senior udvikler (skalering) | Hvad sker der, når 10, 50 og 200 familier bruger appen samtidig? Hvor knækker den først? | `skalering.md` | 8105 |
| 6 | QA og test | Virker alle funktioner fra ende til anden, også kanttilfældene? Hvor mangler der tests? | `qa.md` | 8106 |

## Fælles regler

- **Kun lokalt.** Alt testes mod en lokal kopi på egen port. Driften
  (`madplan.tailea8ae3.ts.net`) og prøven (`madplan-proeve...`) må ikke
  røres – ingen requests, ingen scanning, ingen login.
- **Egen data.** Hver agent bruger sin egen `DATA_DIR` i en midlertidig mappe,
  så de ikke deler database.
- **Ingen ændringer i eksisterende filer.** Ingen commits, ingen branch-skift,
  ingen `npm ci`/`pip install` (miljøet er sat op). QA må tilføje nye
  testfiler `backend/tests/test_qa_*.py`.
- **Fund skal kunne efterprøves:** fil og linje, hvordan man genskaber det,
  hvad der burde ske, og et forslag til rettelse.

## Sådan startes en lokal kopi

Frontend er bygget i `frontend/build`, backend-miljøet ligger i `backend/.venv`.

```sh
cd backend
export DATA_DIR=$(mktemp -d) APP_SECRET=$(openssl rand -hex 32) STATIC_DIR=../frontend/build
.venv/bin/madplan-admin create-user <navn>          # kodeord ≥ 12 tegn, spørges om to gange (kræver en terminal)
.venv/bin/uvicorn --factory madplan.api:create_app --port <PORT>
```

Appen ligger så på `http://127.0.0.1:<PORT>`.

## Alvorlighed

| Niveau | Betydning |
|---|---|
| Kritisk | Blokerer go-live: datalæk mellem familier, tab af data, nedbrud |
| Høj | Skal rettes før go-live eller lige efter: alvorlig fejl eller stor gene |
| Mellem | Bør rettes snart |
| Lav | Pænt at have |

## Rapportformat (alle rapporter)

1. **Kort konklusion** – 3-5 linjer: klar til go-live, ja/nej/med forbehold.
2. **Fund** – tabel: ID, alvor, titel, sted (`fil:linje` eller skærm).
3. **Detaljer pr. fund** – genskabelse, forventet vs. faktisk, forslag.
4. **Hvad der er tjekket og fundet i orden** – så vi ved, hvad der er dækket.
5. **Hvad der ikke kunne testes** – og hvorfor.
