#!/bin/sh
# Opdatér prøveudgaven. Kør i LXC'en:  /opt/madplan-proeve/deploy/proeve/deploy.sh
#
# Henter den gren, prøve-kopien står på (normalt `rolig`), bygger og venter på,
# at appen melder sig sund. Rører ikke driften.
set -eu
cd "$(dirname "$0")"

case "$(pwd)" in
  /opt/madplan/*)
    echo "Dette er driftens kopi af koden. Kør scriptet fra /opt/madplan-proeve." >&2
    exit 1
    ;;
esac

git -C ../.. pull --ff-only
docker compose up -d --build

printf "Venter på, at prøveudgaven melder sig sund"
i=0
while [ $i -lt 40 ]; do
  status=$(docker inspect -f '{{.State.Health.Status}}' proeve-app-1 2>/dev/null || echo "?")
  if [ "$status" = "healthy" ]; then
    echo " ok."
    git -C ../.. log --oneline -1
    exit 0
  fi
  printf "."
  sleep 3
  i=$((i + 1))
done

echo >&2
echo "Prøveudgaven blev ikke sund. Se: docker compose logs --tail 80 app" >&2
exit 1
