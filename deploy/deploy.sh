#!/bin/sh
# Opdatér Madplan på serveren. Kør i LXC'en:  /opt/madplan/deploy/deploy.sh
#
# 1. Kopi af databasen (også selvom appen selv tager én før migrationer).
# 2. Det nuværende image gemmes som deploy-app:forrige, så der kan rulles tilbage.
# 3. Ny kode hentes og bygges. Scriptet venter på, at appen melder sig sund.
set -eu
cd "$(dirname "$0")"

if docker compose ps --status running --services | grep -qx app; then
  docker compose exec -T app madplan-admin backup --keep 14
else
  echo "Appen kører ikke: springer kopien over." >&2
fi

if docker image inspect deploy-app:latest >/dev/null 2>&1; then
  docker tag deploy-app:latest deploy-app:forrige
fi

git -C .. pull --ff-only
docker compose up -d --build

printf "Venter på, at appen melder sig sund"
i=0
while [ $i -lt 40 ]; do
  status=$(docker inspect -f '{{.State.Health.Status}}' deploy-app-1 2>/dev/null || echo "?")
  if [ "$status" = "healthy" ]; then
    echo " ok."
    docker image prune -f >/dev/null
    docker builder prune -f --keep-storage 1GB >/dev/null
    git -C .. log --oneline -1
    exit 0
  fi
  printf "."
  sleep 3
  i=$((i + 1))
done

cat >&2 <<MSG

Appen blev ikke sund. Se: docker compose logs --tail 80 app
Rul tilbage til det forrige image:
  docker tag deploy-app:forrige deploy-app:latest && docker compose up -d --no-build app
Har en migration ændret databasen, så gendan også den seneste kopi (se docs/drift.md).
MSG
exit 1
