# Breach Watch

Breach monitoring built on self-hosted n8n, with Redis and Postgres, via
Docker Compose.

## Layout

```
docker-compose.yml   stack definition
.env.example         required secrets (copy to .env)
workflows/           exported workflow definitions — the source of truth in git
sql/                 schema for the Postgres tables the workflows read/write
scripts/             bootstrap + export/import round-trip
files/               bind-mounted into the n8n container at /files
```

The workflow polls the Hacker News RSS feed, runs an AI agent over each
article to flag breach disclosures, writes `articles` / `findings` rows to
Postgres, dedups on `article:*` keys in Redis, and alerts Slack.

## Setup

```bash
cp .env.example .env      # fill in REDIS_PASSWORD and POSTGRES_PASSWORD
./scripts/bootstrap.sh
```

`bootstrap.sh` does the whole thing: starts the containers, waits until
Postgres, Redis and n8n actually answer, applies the schema, imports the
workflows and restores their active flag. Safe to re-run — every step is
skipped if already done.

```bash
./scripts/bootstrap.sh --recreate    # force-recreate containers first
./scripts/bootstrap.sh --no-import   # containers + schema only
```

n8n UI: http://localhost:5678

| service    | container                 | host port |
|------------|---------------------------|-----------|
| `n8n`      | `n8n`                     | 5678      |
| `postgres` | `breach-watch-postgres-1` | **5434**  |
| `redis`    | `breach-watch-redis-1`    | **6380**  |

Postgres and Redis are on non-default host ports, so bare `psql` / `redis-cli`
without `-p` will not find them. Scripts address containers by Compose
*service* name (`docker compose exec postgres …`), so they keep working
regardless of container naming.

## Workflow round-trip

```bash
./scripts/export-workflows.sh   # live n8n  -> workflows/   (run before committing)
./scripts/import-workflows.sh   # workflows/ -> live n8n    (matches on id, updates in place)
```

Exports are written with sorted keys and 2-space indent so diffs stay readable.
