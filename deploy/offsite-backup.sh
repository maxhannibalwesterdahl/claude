#!/bin/sh
# Kopi af databasen og billederne uden for maskinen. Kør natligt fra cron i LXC'en
# EFTER den daglige kopi (03:15), fx kl. 04:00:
#
#   0 4 * * * root /usr/local/sbin/madplan-offsite-backup >> /var/log/madplan-offsite.log 2>&1
#
# Sæt ÉT mål i offsite.env (ikke i git; ligger ved siden af scriptet, eller peg på den med OFFSITE_ENV):
#   OFFSITE_GIT=git@github-backup:bruger/madplan-backup.git   (privat git-repo, kun krypterede filer)
#   OFFSITE_RSYNC=bruger@vært:/sti/madplan/                   (rsync over ssh, nøgle uden kodeord)
#   OFFSITE_RCLONE=fjernbetjening:madplan                     (rclone: Backblaze B2, Google Drive, ...)
# Kopien SKAL være krypteret, når målet ikke er dit eget (git og sky):
#   OFFSITE_AGE_RECIPIENT=age1...      (offentlig nøgle; den hemmelige nøgle gemmes ikke på serveren)
# Kør fra et andet sted end scriptets mappe: MADPLAN_DEPLOY_DIR=/opt/madplan/deploy (der, hvor compose.yaml ligger).
#
# Scriptet tager den nyeste daglige kopi, tjekker at den kan åbnes, krypterer og sender den
# med billederne. Git-målet gemmer de seneste 7 dage og har kun ét commit (historikken rulles).
# Afprøv:  OFFSITE_DRY_RUN=1 ./offsite-backup.sh   (viser, hvad der ville ske)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
envfile="${OFFSITE_ENV:-$here/offsite.env}"
[ -f "$envfile" ] && . "$envfile"
cd "${MADPLAN_DEPLOY_DIR:-$here}"

: "${OFFSITE_GIT:=}" "${OFFSITE_RSYNC:=}" "${OFFSITE_RCLONE:=}" "${OFFSITE_AGE_RECIPIENT:=}" "${OFFSITE_DRY_RUN:=}"
if [ -z "$OFFSITE_GIT" ] && [ -z "$OFFSITE_RSYNC" ] && [ -z "$OFFSITE_RCLONE" ]; then
  echo "Sæt OFFSITE_GIT, OFFSITE_RSYNC eller OFFSITE_RCLONE i offsite.env." >&2
  exit 1
fi
if [ -n "$OFFSITE_GIT$OFFSITE_RCLONE" ] && [ -z "$OFFSITE_AGE_RECIPIENT" ]; then
  echo "Git og sky kræver kryptering: sæt OFFSITE_AGE_RECIPIENT." >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work" "$work.git"' EXIT

latest=$(docker compose exec -T app sh -c 'ls -1 /data/backups/madplan-*.db | tail -n 1' | tr -d '\r')
[ -n "$latest" ] || { echo "Ingen daglig kopi fundet i /data/backups." >&2; exit 1; }
# Tjek kopien i containeren (python findes dér), før den sendes. Skrivebeskyttet, så der ikke
# opstår -wal/-shm ved siden af.
docker compose exec -T app python - "$latest" <<'PY'
import sqlite3, sys
try:
    con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro&immutable=1", uri=True)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity_check fejlede"
    print("kopien kan åbnes:", con.execute("select count(*) from recipe").fetchone()[0], "opskrifter")
except Exception as e:
    sys.exit(f"Kopien er ødelagt eller ulæselig ({e}). Intet sendt.")
PY
docker compose cp "app:$latest" "$work/$(basename "$latest")"
docker compose exec -T app sh -c 'cd /data && tar -cf - images 2>/dev/null' > "$work/billeder.tar" || true

if [ -n "$OFFSITE_AGE_RECIPIENT" ]; then
  for f in "$work"/*; do age -r "$OFFSITE_AGE_RECIPIENT" -o "$f.age" "$f" && rm "$f"; done
fi

if [ -n "$OFFSITE_DRY_RUN" ]; then
  echo "Ville sende:"; ls -l "$work"; exit 0
fi

if [ -n "$OFFSITE_GIT" ]; then
  repo="$work.git"
  rm -rf "$repo"
  if ! git clone -q --depth 1 "$OFFSITE_GIT" "$repo" 2>/dev/null; then
    git init -q "$repo" && git -C "$repo" remote add origin "$OFFSITE_GIT"
  fi
  cd "$repo"
  git config user.name "madplan-backup" && git config user.email "backup@madplan.invalid"
  # Behold de seneste 7 databasekopier (datoerne står i filnavnene) og den nyeste billedkopi.
  cp "$work"/* .
  ls -1 madplan-*.db.age 2>/dev/null | sort | head -n -7 | xargs -r rm -f
  # Ét commit uden historik, så repoet ikke vokser.
  git checkout -q --orphan kopi
  git add -A
  git commit -q -m "Kopi $(basename "$latest" .db)"
  git push -q --force origin kopi:main
  cd /; rm -rf "$repo"
elif [ -n "$OFFSITE_RSYNC" ]; then
  rsync -a "$work"/ "$OFFSITE_RSYNC"
else
  rclone copy "$work" "$OFFSITE_RCLONE"
fi
echo "Kopi uden for huset sendt: $(basename "$latest")"
