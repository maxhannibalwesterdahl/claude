# Fase 0.3 – Drift, Funnel og offline: vejledning og testprotokol

Formål: afprøve, før den rigtige app bygges, at

1. appen kan køre i en container i Proxmox,
2. begge telefoner kan åbne den via Tailscale Funnel uden at installere noget,
3. indkøbslisten kan bruges uden dækning og synkroniserer bagefter.

Testappen lå i `spike/offline/` og er fjernet efter testen. Driftsopsætningen i
`deploy/` kører nu den rigtige app. Trin 1-5 herunder gælder stadig for en ny
opsætning. Daglig drift: se [drift.md](drift.md).

**Allerede testet i udviklingsmiljøet:** appen, login med begrænsning af forsøg,
offline-afkrydsning med to "telefoner" i Chromium, Docker-imaget (kører som
almindelig bruger) og compose-filen. **Ikke testet:** Tailscale Funnel og rigtige
telefoner. Det er formålet med denne fase.

---

## Trin 1 – Tailscale

1. Log ind (eller opret gratis konto) på https://login.tailscale.com.
2. **DNS** (https://login.tailscale.com/admin/dns): slå *MagicDNS* og
   *HTTPS Certificates* til.
3. **Access controls** (https://login.tailscale.com/admin/acls): tjek at
   politikken har en `nodeAttrs`-regel med `"attr": ["funnel"]`. Nye konti har
   den som standard. Mangler den, tilføj:
   ```json
   "nodeAttrs": [
     { "target": ["autogroup:member"], "attr": ["funnel"] }
   ]
   ```
4. **Auth key** (https://login.tailscale.com/admin/settings/keys):
   *Generate auth key*. Ikke *Reusable*, ikke *Ephemeral*. Kopiér nøglen
   (`tskey-auth-…`). Den vises kun én gang.

## Trin 2 – Container i Proxmox

1. Hent skabelon: *local → CT Templates → Templates → debian-12-standard*.
2. *Create CT*:
   | Felt | Værdi |
   |---|---|
   | Hostname | `madplan` |
   | Unprivileged container | ✔ |
   | Template | debian-12-standard |
   | Disk | 8 GB |
   | CPU | 1 kerne |
   | Memory / Swap | 1024 MB / 512 MB |
   | Network | vmbr0, DHCP |
3. Før første start: *Options → Features*: slå **nesting** og **keyctl** til
   (kræves for Docker i en unprivileged container).
4. Start containeren og åbn *Console*.

## Trin 3 – Docker og koden

I containerens konsol:

```sh
apt update && apt install -y curl git ca-certificates
curl -fsSL https://get.docker.com | sh
git clone https://github.com/maxhannibalwesterdahl/claude.git /opt/madplan
cd /opt/madplan && git checkout claude/weekly-meal-planner-app-kzmnlj
```

## Trin 4 – Hemmeligheder

```sh
cd /opt/madplan/deploy
cp .env.example .env
openssl rand -hex 32     # kopiér output til APP_SECRET
nano .env                # udfyld TS_AUTHKEY og APP_SECRET
chmod 600 .env
```

`.env` er udelukket i `.gitignore`. Repoet er offentligt, så filen må aldrig
committes.

## Trin 5 – Start

```sh
docker compose up -d --build
docker compose logs -f tailscale     # vent på en linje med "Funnel" / "serve"
```

Adressen er `https://madplan.<dit-tailnet>.ts.net`. Tailnet-navnet står under
*DNS* i Tailscale-admin. Første gang kan certifikat og DNS tage op til ~10
minutter.

## Trin 6 – Telefonerne

1. Åbn adressen i **Safari** (iPhone) eller **Chrome** (Android), og log ind.
2. Læg på hjemmeskærmen:
   - iPhone: *Del → Føj til hjemmeskærm*
   - Android: *⋮ → Installer app* / *Føj til startskærm*
3. Åbn fremover appen fra ikonet på hjemmeskærmen, ikke fra browseren.

---

## Testprotokol

Kryds af og noter afvigelser.

| # | Handling | Forventet |
|---|---|---|
| A | Åbn appen fra hjemmeskærmen på begge telefoner | Listen vises, status "Synkroniseret hh:mm" |
| B | Telefon 1: slå **flytilstand** til. Luk appen helt og åbn den igen fra ikonet | Listen vises stadig. Status "Offline – viser gemt liste" |
| C | Telefon 1 (stadig flytilstand): kryds 3 varer af | Status "Offline – 3 ændringer venter" |
| D | Telefon 1: luk appen helt, åbn igen | De 3 varer er stadig krydset af |
| E | Telefon 2 (online): kryds 1 **anden** vare af | "Synkroniseret" |
| F | Telefon 1: slå flytilstand fra, åbn appen | Inden for ~20 sek. "Synkroniseret". Telefon 2's vare er nu også krydset af |
| G | Telefon 2: luk og åbn appen | Telefon 1's 3 varer er krydset af |
| H | Begge: kryds **samme** vare af/fra på skift, én ad gangen | Den seneste ændring vinder på begge |
| I | En computer uden for Tailscale: indtast forkert kodeord 6 gange | "For mange forsøg. Vent et minut." |
| J | Valgfrit: brug listen i Bilka på en rigtig tur | Noter dækning og om noget gik galt |

"Nulstil test"-knappen fjerner alle flueben, så protokollen kan køres igen.

## Kendte forhold

- **Uret på telefonerne** afgør, hvilken ændring der vinder. Telefoner
  synkroniserer uret automatisk, så det er kun et problem, hvis uret er
  stillet manuelt.
- **iPhone** kan slette data for websider, der ikke er brugt i 7 dage. Det gælder
  ikke apps, der er lagt på hjemmeskærmen, derfor trin 6.2.
- Spiken har **ét fælles kodeord**. Den rigtige app får et login pr. person.

## Bagefter

Gjort 28-09-2026: testappen er erstattet af fase 1-appen i samme container og
med samme Tailscale-tilstand (ingen ny auth key). Den gamle testdata-volumen
`deploy_app-data` kan slettes med `docker volume rm deploy_app-data`.

**Brug aldrig `docker compose down -v`** fremover. Det sletter databasen og
Tailscale-tilstanden.
