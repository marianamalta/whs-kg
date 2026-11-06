#!/bin/sh
# Run daily on the endpoint VM (cron), e.g.:
#   23 4 * * * /opt/whs-kg/endpoint/vm-update.sh >> /var/log/whs-update.log 2>&1
# Pulls the newest GitHub release; if it is new, reloads the store from scratch
# (full rebuild + full reload: the dataset is small, this takes seconds).
set -e
REPO=marianamalta/whs-kg
DIR=$(cd "$(dirname "$0")" && pwd)
STATE="$DIR/data/.release"

latest=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
         | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
[ -n "$latest" ] || { echo "$(date -u) no release found"; exit 0; }
[ "$latest" = "$(cat "$STATE" 2>/dev/null)" ] && { echo "$(date -u) up to date ($latest)"; exit 0; }

echo "$(date -u) updating to $latest"
curl -fsSL -o "$DIR/data/whs-all.trig.new" \
  "https://github.com/$REPO/releases/download/$latest/whs-all.trig"
mv "$DIR/data/whs-all.trig.new" "$DIR/data/whs-all.trig"
cd "$DIR" && docker compose restart      # load.sh reloads the store on start
echo "$latest" > "$STATE"
echo "$(date -u) done"
