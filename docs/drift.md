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
/opt/madplan/deploy/deploy.sh
```

Scriptet:
1. tager en kopi af databasen
2. gemmer det kørende image som `deploy-app:forrige`
3. henter ny kode (`git pull --ff-only` på `main`) og bygger
4. venter på, at appen melder sig sund, og rydder gamle images op

Bliver appen ikke sund, skriver scriptet, hvordan man ruller tilbage:

```sh
docker tag deploy-app:forrige deploy-app:latest && docker compose up -d --no-build app
```

Databasen migreres automatisk ved opstart (Alembic). Før en migration tages en
kopi (`/data/backups/premigrate-<version>-<tidspunkt>.db`), og migrationen kører
med fremmednøgler slået fra, så SQLite ikke sletter rækker, når en tabel
genopbygges. Nye varer i ingredienstabellen lægges ind automatisk, uden at ændre
varer, I selv har rettet.

## Backup

Sat op og afprøvet 30-09-2026.

| Hvad | Hvornår | Hvor | Gemmes |
|---|---|---|---|
| Kopi af databasen (`madplan-admin backup`) | 03:15 hver nat, cron i LXC'en (`/etc/cron.d/madplan`) | `/data/backups/madplan-ÅÅÅÅ-MM-DD.db` i volumen `deploy_madplan-data` | 14 dage |
| Kopi før migration | automatisk ved opstart, når der er en ny migration | `/data/backups/premigrate-*.db` | ryddes ikke automatisk |
| Hele LXC 102 (vzdump, snapshot, zstd) | 03:30 hver nat, Proxmox-job `madplan-nightly` | `local` på Proxmox-værten (`/var/lib/vz/dump`) | 7 daglige + 4 ugentlige |

Log for den daglige kopi: `/var/log/madplan-backup.log` i LXC'en.

**Mangler: en kopi uden for maskinen.** Alt ovenfor ligger på værtens ene
NVMe-disk. Dør disken, er alt væk. Vælg et sted (Macen med Time Machine,
en USB-disk eller cloud), så sættes en natlig kopi op. OMV-containeren har i dag
ingen datadisk og er derfor ikke et alternativ.

### Gendan databasen fra en daglig kopi

Mister man højst et døgn, er det den hurtigste vej. I LXC'en:

```sh
cd /opt/madplan/deploy
docker compose exec -T app ls /data/backups          # vælg en fil
docker compose stop app
docker compose run --rm --no-deps -T app sh -c \
  'cp /data/backups/madplan-2026-09-30.db /data/madplan.db && rm -f /data/madplan.db-wal /data/madplan.db-shm'
docker compose start app
```

`docker compose run` kører som appens egen bruger, så filen ejes af den rigtige
bruger (med `docker cp` bliver den root-ejet, og appen kan så ikke skrive).
WAL-filerne skal slettes, ellers kan en gammel WAL blive lagt oven på den
gendannede database.

### Gendan hele containeren

I Proxmox: *LXC 102 → Backup →* vælg en backup → *Restore*. Eller på værten:

```sh
pct stop 102
pct restore 102 /var/lib/vz/dump/vzdump-lxc-102-<dato>.tar.zst --storage local-lvm --force 1
pct start 102
```

Afprøvet 30-09-2026 ved at gendanne til en midlertidig container (9102, aldrig
startet): database (integritet ok, alle rækker), billeder og `.env` var med.

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
