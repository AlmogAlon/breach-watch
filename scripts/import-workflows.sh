#!/usr/bin/env bash
# Import workflows/ into the running n8n container.
# Matches on workflow id, so existing workflows are UPDATED in place.
# Credentials must already exist in the target n8n (referenced by id).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# ./files is bind-mounted to /files in the container, so staging a subdir
# there is enough — no docker cp needed. Scoped to its own directory so
# nothing else in files/ is touched.
STAGE="files/_import"
trap 'rm -rf "$REPO/$STAGE"' EXIT

rm -rf "$STAGE"; mkdir -p "$STAGE"
cp workflows/*.json "$STAGE/"

docker compose exec -T n8n n8n import:workflow --separate --input=/files/_import

# import:workflow force-deactivates everything it touches, so restore the
# active flag from the committed JSON — otherwise importing silently turns
# off live triggers.
ACTIVE_IDS=$(python3 -c "
import json, glob
for f in sorted(glob.glob('workflows/*.json')):
    d = json.load(open(f))
    if d.get('active') and d.get('id'):
        print(d['id'])
")

if [[ -n "$ACTIVE_IDS" ]]; then
  # `docker compose exec` reads stdin, so feeding the loop from a here-string
  # let it eat the remaining ids and only the first workflow was reactivated.
  for id in $ACTIVE_IDS; do
    docker compose exec -T n8n n8n update:workflow --id="$id" --active=true >/dev/null 2>&1 </dev/null
    echo "reactivated $id"
  done
  # Activation only takes effect on restart; this is what registers triggers.
  docker compose restart n8n >/dev/null
  echo "restarted n8n to register triggers"
else
  echo "no workflows marked active — nothing to reactivate"
fi
