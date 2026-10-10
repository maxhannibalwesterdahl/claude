# Prøveudgave: det nye design ved siden af driften

Det nye design (Rolig) bygges på grenen `rolig` og køres som en **prøveudgave**
med egen adresse og egen kopi af data. Den rigtige app på `main` kører uændret
imens og kan stadig rettes og deployes som normalt.

| | Drift | Prøve |
|---|---|---|
| Adresse | `https://madplan.tailea8ae3.ts.net` | `https://madplan-proeve.tailea8ae3.ts.net` |
| Gren | `main` | `rolig` |
| Kode i LXC'en | `/opt/madplan` | `/opt/madplan-proeve` |
| Compose-projekt | `deploy` | `proeve` |
| Data | volumen `deploy_madplan-data` | volumen `proeve_madplan-data` (en kopi) |
| Opdatering | `deploy/deploy.sh` | `deploy/proeve/deploy.sh` |

Fordi adresserne er forskellige, er login, hjemmeskærms-app og offline-liste
også adskilt på telefonen. De to kan ligge side om side.

## Data: sådan flyttes det, der allerede ligger i appen

Det nye design bruger den samme database som i dag. Der er derfor ikke noget,
der skal oversættes eller flyttes, når det går i drift: driftens database
bliver liggende, hvor den er.

- **Til prøven:** `deploy/proeve/kopier-data.sh` kopierer driftens database og
  billeder til prøveudgaven. Opskrifter, madplaner, indkøbslister, varer og
  brugere kommer med. Kør det igen for at få friske data.
- **Kun én vej:** intet fra prøveudgaven kommer tilbage til driften. Brug
  prøven til at prøve, ikke til ugens rigtige indkøb.
- **Ændringer i databasen:** kræver det nye design en ny tabel eller kolonne,
  laves det som en almindelig Alembic-migration. Den køres først på kopien i
  prøveudgaven, hvor den kan fejle uden skade. I driften tager appen selv en
  kopi (`premigrate-*.db`), før migrationen kører.

## Sæt prøveudgaven op (én gang)

I LXC'en:

```sh
git clone --branch rolig https://github.com/maxhannibalwesterdahl/madplan.git /opt/madplan-proeve
cd /opt/madplan-proeve/deploy/proeve
cp .env.example .env      # udfyld: ny TS_AUTHKEY og ny APP_SECRET
./deploy.sh
./kopier-data.sh
```

Slå *key expiry* fra for maskinen `madplan-proeve` i Tailscale-admin, og tjek,
at Funnel er slået til for den:

```sh
docker compose exec tailscale tailscale funnel status
```

## Gå i drift med det nye design

1. Kør `kopier-data.sh` en sidste gang, og gennemgå prøveudgaven med friske data.
2. Merge `rolig` til `main` via en PR.
3. Kør `/opt/madplan/deploy/deploy.sh` som ved enhver anden opdatering.

Går det galt, rulles der tilbage som beskrevet i [drift.md](drift.md): det
forrige image ligger som `deploy-app:forrige`, og databasen har en kopi fra
lige før.

## Fjern prøveudgaven igen

```sh
cd /opt/madplan-proeve/deploy/proeve
docker compose down -v
rm -rf /opt/madplan-proeve
```

Fjern også maskinen `madplan-proeve` i Tailscale-admin.
