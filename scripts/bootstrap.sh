#!/usr/bin/env bash
# Bring the whole stack up from nothing: containers, schema, workflows.
# Safe to re-run — every step is skipped if it is already done.
#
#   ./scripts/bootstrap.sh              full bootstrap
#   ./scripts/bootstrap.sh --recreate   force-recreate containers first
#   ./scripts/bootstrap.sh --no-import  skip the workflow import
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

RECREATE=0
IMPORT=1
for arg in "$@"; do
  case "$arg" in
    --recreate)  RECREATE=1 ;;
    --no-import) IMPORT=0 ;;
    -h|--help)   sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
step "Preflight"

command -v docker >/dev/null || die "docker not found on PATH"
docker info >/dev/null 2>&1 || die "Docker daemon is not running — start Docker Desktop"
ok "docker is running"

if [[ ! -f .env ]]; then
  cp .env.example .env
  die ".env was missing — created it from .env.example.
       Fill in REDIS_PASSWORD and POSTGRES_PASSWORD, then re-run.
       Generate values with:  openssl rand -base64 24"
fi

set -a; . ./.env; set +a
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is empty in .env}"
: "${REDIS_PASSWORD:?REDIS_PASSWORD is empty in .env}"
ok ".env loaded"

# ---------------------------------------------------------------- containers
step "Starting containers"

if [[ $RECREATE -eq 1 ]]; then
  docker compose up -d --force-recreate
else
  docker compose up -d
fi

# Compose only waits on healthchecks it was told to depend on, so poll here.
wait_for() {
  local name="$1" probe="$2" tries="${3:-60}" i=0
  printf '    waiting for %s' "$name"
  until eval "$probe" >/dev/null 2>&1; do
    i=$((i + 1))
    [[ $i -ge $tries ]] && { printf ' timeout\n'; die "$name never became ready"; }
    printf '.'
    sleep 2
  done
  printf '\n'
  ok "$name ready"
}

wait_for "postgres" 'docker compose exec -T postgres pg_isready -U n8n -d n8n'
wait_for "redis"    'docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping'
wait_for "n8n"      'curl -fsS http://localhost:5678/healthz'

# ---------------------------------------------------------------- schema
step "Migrating schema"

# Alembic is idempotent: already-applied revisions are skipped, so this is
# safe on every run. The venv holds alembic and the Postgres driver.
if [[ ! -x .venv/bin/alembic ]]; then
  warn "no .venv — creating it"
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi

.venv/bin/alembic upgrade head
ok "schema at $(.venv/bin/alembic current 2>/dev/null | tail -1)"

# ---------------------------------------------------------------- workflows
if [[ $IMPORT -eq 1 ]]; then
  step "Importing workflows"
  if compgen -G "workflows/*.json" >/dev/null; then
    ./scripts/import-workflows.sh
  else
    warn "no workflows/*.json to import"
  fi
else
  step "Skipping workflow import (--no-import)"
fi

# ---------------------------------------------------------------- summary
step "Ready"

printf '    n8n UI    http://localhost:5678\n'
printf '    postgres  localhost:5434  (db=n8n user=n8n)\n'
printf '    redis     localhost:6380  (requirepass)\n\n'

printf '    workflows:\n'
docker compose exec -T n8n n8n list:workflow 2>/dev/null | sed 's/^/      /' || true

cat <<'EOF'

    Credentials are NOT provisioned by this script — they hold live API keys
    and are not in the repo. On a fresh install, add them in the UI at
    Settings -> Credentials, then re-link the nodes (or match the old ids).
EOF
