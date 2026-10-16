#!/bin/sh
# Kopi af databasen og billederne uden for maskinen. Kør natligt fra cron i LXC'en
# EFTER den daglige kopi (03:15), fx kl. 04:00:
#
#   0 4 * * * root /opt/madplan/deploy/offsite-backup.sh >> /var/log/madplan-offsite.log 2>&1
#
# Sæt ÉT mål i /opt/madplan/deploy/offsite.env (ikke i git):
#   OFFSITE_RSYNC=bruger@vært:/sti/madplan/        (rsync over ssh, nøgle uden kodeord)
#   OFFSITE_RCLONE=fjernbetjening:madplan          (rclone: Backblaze B2, Google Drive, ...)
# Valgfrit: OFFSITE_AGE_RECIPIENT=age1...          (krypterer kopien, før den forlader maskinen)
#
# Scriptet tager den nyeste kopi, tjekker at den kan åbnes, og sender den med billederne.
# Afprøv:  OFFSITE_DRY_RUN=1 ./offsite-backup.sh   (viser, hvad der ville ske)
set -eu
cd "$(dirname "$0")"
[ -f offsite.env ] && . ./offsite.env

: "${OFFSITE_RSYNC:=}" "${OFFSITE_RCLONE:=}" "${OFFSITE_AGE_RECIPIENT:=}" "${OFFSITE_DRY_RUN:=}"
if [ -z "$OFFSITE_RSYNC" ] && [ -z "$OFFSITE_RCLONE" ]; then
  echo "Sæt OFFSITE_RSYNC eller OFFSITE_RCLONE i offsite.env." >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

latest=$(docker compose exec -T app sh -c 'ls -1 /data/backups/madplan-*.db | tail -n 1' | tr -d '\r')
[ -n "$latest" ] || { echo "Ingen daglig kopi fundet i /data/backups." >&2; exit 1; }
docker compose cp "app:$latest" "$work/$(basename "$latest")"
docker compose exec -T app sh -c 'cd /data && tar -cf - images 2>/dev/null' > "$work/billeder.tar" || true

python3 - "$work/$(basename "$latest")" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "kopien er ødelagt"
print("kopien kan åbnes:", con.execute("select count(*) from recipe").fetchone()[0], "opskrifter")
PY

if [ -n "$OFFSITE_AGE_RECIPIENT" ]; then
  for f in "$work"/*; do age -r "$OFFSITE_AGE_RECIPIENT" -o "$f.age" "$f" && rm "$f"; done
fi

if [ -n "$OFFSITE_DRY_RUN" ]; then
  echo "Ville sende:"; ls -l "$work"; exit 0
fi
if [ -n "$OFFSITE_RSYNC" ]; then
  rsync -a "$work"/ "$OFFSITE_RSYNC"
else
  rclone copy "$work" "$OFFSITE_RCLONE"
fi
echo "Kopi uden for huset sendt: $(basename "$latest")"
