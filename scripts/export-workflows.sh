#!/usr/bin/env bash
# Export live n8n workflows from the container into workflows/ as normalized JSON.
# Credentials are NOT exported — they stay in the n8n volume.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# Addressed by Compose service name, so container naming can change freely.
docker compose exec -T n8n sh -c 'rm -rf /files/_wf && mkdir -p /files/_wf \
  && n8n export:workflow --all --separate --output=/files/_wf' >/dev/null

python3 - "$REPO" <<'PY'
import json, glob, os, re, shutil, sys
repo = sys.argv[1]
src, dst = os.path.join(repo, "files/_wf"), os.path.join(repo, "workflows")
os.makedirs(dst, exist_ok=True)
seen = set()
for f in sorted(glob.glob(src + "/*.json")):
    d = json.load(open(f))
    slug = re.sub(r'[^a-z0-9]+', '-', d.get('name', 'unnamed').lower()).strip('-')
    if slug in seen:                      # disambiguate duplicate names
        slug = f"{slug}-{d.get('id')}"
    seen.add(slug)
    with open(os.path.join(dst, slug + ".json"), "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    print(f"exported {slug}.json  ({d.get('name')}, active={d.get('active')})")
shutil.rmtree(src)
PY
