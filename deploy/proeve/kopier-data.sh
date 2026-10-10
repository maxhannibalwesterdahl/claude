#!/bin/sh
# Kopiér driftens data til prøveudgaven. Kør i LXC'en:
#   /opt/madplan-proeve/deploy/proeve/kopier-data.sh
#
# 1. Driften tager en kopi af sin database (sikkert, mens appen kører).
# 2. Prøveudgaven stoppes, og dens database og billeder ERSTATTES af driftens.
# 3. Prøveudgaven startes og kører selv eventuelle nye migrationer på kopien.
#
# Går kun én vej: driftens data monteres skrivebeskyttet. Alt, der er lavet i
# prøveudgaven, forsvinder. Kan køres igen, når som helst.
set -eu
cd "$(dirname "$0")"

DRIFT=/opt/madplan/deploy
FRA=deploy_madplan-data
TIL=proeve_madplan-data

kopi=$(cd "$DRIFT" && docker compose exec -T app madplan-admin backup --keep 14 | tr -d '\r' | tail -n 1)
fil=$(basename "$kopi")
echo "Driftens kopi: $fil"

docker compose stop app
docker run --rm --user 0 \
  -v "$FRA":/fra:ro -v "$TIL":/til \
  --entrypoint sh deploy-app:latest -c "
    set -eu
    cp /fra/backups/$fil /til/madplan.db
    rm -f /til/madplan.db-wal /til/madplan.db-shm
    rm -rf /til/images
    if [ -d /fra/images ]; then cp -a /fra/images /til/images; fi
    chown -R app /til
  "
docker compose up -d app
echo "Data kopieret. Log ind i prøveudgaven med de samme brugere og kodeord som i driften."
