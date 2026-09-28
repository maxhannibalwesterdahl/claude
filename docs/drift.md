# Drift

Madplan kører i LXC-containeren `madplan` (ID 102) i Proxmox med Docker Compose.
Adressen udefra er `https://madplan.tailea8ae3.ts.net` via Tailscale Funnel.
Opsætningen af containeren og Tailscale er beskrevet i
[fase0-drift.md](fase0-drift.md), trin 1-5.

| | |
|---|---|
| Kode | `/opt/madplan` i containeren |
| Driftsfiler | `/opt/madplan/deploy` (`compose.yaml`, `serve.json`, `.env`) |
| Data | Docker-volumen `deploy_madplan-data`, monteret som `/data` i app-containeren |
| Database | `/data/madplan.db` (SQLite) |
| Billeder | `/data/images/` |
| SSH | `ssh root@192.168.1.114` fra Macen (nøgle lagt ind) |

Alle kommandoer herunder køres i containeren fra `/opt/madplan/deploy`.

## Brugere

Der er ingen selvregistrering. Brugere oprettes fra kommandolinjen. Kodeordet
skal være mindst 12 tegn og spørges om uden at blive vist:

```sh
docker compose exec app madplan-admin create-user max
docker compose exec app madplan-admin set-password max   # logger også ud på alle enheder
docker compose exec app madplan-admin list-users
```

Brugernavne gemmes med små bogstaver. Login er begrænset til 5 forkerte forsøg
pr. minut pr. IP.

## Opdatering

```sh
cd /opt/madplan && git pull
cd deploy && docker compose up -d --build
```

Databasen migreres automatisk ved opstart (Alembic). Nye varer i
ingredienstabellen lægges ind automatisk, uden at ændre varer, I selv har rettet.

## Backup

- **Proxmox:** backup af hele LXC'en (Datacenter → Backup). Dækker database,
  billeder og Tailscale-tilstand.
- **Daglig kopi af databasen** (ikke sat op endnu). Tilføj i containerens
  crontab (`crontab -e`):
  ```
  15 3 * * * cd /opt/madplan/deploy && docker compose exec -T app madplan-admin backup --keep 14
  ```
  Kopierne lægges i `/data/backups/madplan-ÅÅÅÅ-MM-DD.db`. Kommandoen er sikker at
  køre, mens appen kører.

Gendannelse: stop appen (`docker compose stop app`), kopiér den ønskede fil til
`/data/madplan.db`, fx med `docker compose cp`, og start igen.

## Fejlsøgning

```sh
docker compose ps                    # begge skal være "Up", app "healthy"
docker compose logs --tail 50 app
docker compose logs --tail 50 tailscale
docker compose exec tailscale tailscale funnel status
```

- **"Server ikke fundet" på telefonen:** Funnel-adressen findes ikke. Tjek, at
  `nodeAttrs` med `funnel` stadig er i Tailscales access controls, og at
  maskinen `madplan` er online i Tailscale-admin.
- **Fejl 502:** tailscale kører, men kan ikke nå appen. Se `docker compose logs app`.
- **Key expiry:** er den ikke slået fra for `madplan` i Tailscale-admin, falder
  maskinen af efter ca. 6 måneder.

## Udvikling på egen computer

```sh
cd backend
uv venv --python 3.12 && uv pip install -r requirements.lock -e '.[dev]'
.venv/bin/pytest
DATA_DIR=data APP_SECRET=$(openssl rand -hex 32) STATIC_DIR=../frontend/build \
  .venv/bin/uvicorn --factory madplan.api:create_app --port 8000

cd frontend
npm ci
npm run dev      # http://localhost:5173, sender /api videre til port 8000
npm run check && npm run build
```

Lokal bruger: `DATA_DIR=data APP_SECRET=... .venv/bin/madplan-admin create-user test`.

Ny migration efter ændring i `models.py`:

```sh
cd backend && .venv/bin/alembic revision --autogenerate -m "beskrivelse"
```
