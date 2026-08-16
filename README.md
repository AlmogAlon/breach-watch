# Breach Watch

Breach monitoring built on self-hosted n8n, with Redis and Postgres, via
Docker Compose.

## Layout

```
docker-compose.yml   stack definition
.env.example         required secrets (copy to .env)
workflows/           exported workflow definitions — the source of truth in git
db/migrations/       Alembic migrations (schema history)
scripts/models.py    the ORM models — source of truth for the schema
scripts/             bootstrap + export/import round-trip
files/               bind-mounted into the n8n container at /files
```

## How it works

Two workflows. `rss feed` produces findings, `slack review` records human
verdicts on them.

```
RSS trigger → claim article → Apify scrape → AI agent → Create finding
                                                      → Slack alert
                                                            ↓
                                          [Approve] [Reject] clicked
                                                            ↓
Slack → webhook → UPDATE findings → rewrite the message, drop the buttons
```

The article is claimed in Postgres *before* the scrape and the model call, so
duplicates cost nothing. The agent decides but never writes: it returns the
breach fields and the workflow inserts them, which is what keeps `article_id`
correct when a batch of articles is in flight.

Reviewed findings feed back in — the agent queries recent approved/rejected
findings as few-shot examples before judging a new article, so each verdict
you give in Slack shapes the next run.

### Data model

One row per **article**, not per breach: two articles covering the same
incident are two rows. An article can name several breaches, so `findings`
hangs off `articles` many-to-one.

```
articles   url_hash is the dedup key; raw_payload keeps the whole source event
findings   the agent's extraction + the human verdict (pending/approved/rejected)
```

## Setup

```bash
cp .env.example .env      # fill in REDIS_PASSWORD and POSTGRES_PASSWORD
./scripts/bootstrap.sh
```

`bootstrap.sh` creates `.venv` from `requirements.txt` if it is missing, then
runs `alembic upgrade head`.

Credentials are not in this repo — they hold live API keys and stay encrypted
in the `n8n_data` volume. On a fresh install, recreate them in the UI
(OpenAI, Slack, Apify, Postgres, Redis). Workflow JSON references them by id,
so either match the old ids or re-link each node after importing.

It does the whole thing: starts the containers, waits until Postgres, Redis and
n8n actually answer, migrates the schema, imports the workflows and restores
their active flag. Safe to re-run — every step is idempotent.

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

## Slack review setup

Slack must reach n8n over public HTTPS, so a tunnel is needed for local runs:

```bash
ngrok http 5678
```

Put the public host in `.env` and restart n8n, or it keeps minting `localhost`
webhook URLs:

```bash
WEBHOOK_URL=https://<your-host>/
docker compose up -d n8n
```

Then in the Slack app — **Interactivity & Shortcuts** → Enable Interactivity →
Request URL:

```
https://<your-host>/webhook/slack-review
```

Note `/webhook/`, not `/webhook-test/`. The test URL accepts a single request
and only while you are listening in the editor. The production URL requires the
`slack review` workflow to be **active**.

On the free ngrok tier the host changes on every restart, and both `.env` and
the Slack setting have to be updated.

### Review semantics

`review_status` moves out of `pending` exactly once — the update is guarded by
`AND review_status = 'pending'`, so a double click or a replayed request
changes nothing. That guard is the source of truth, not the presence of the
buttons; removing them from the message is cosmetic.

Button values carry `finding_id`. Because Slack bakes the value in at send
time, alerts posted before a change to that field keep their old value forever.

> **Not implemented:** the webhook does not verify Slack's request signature.
> `x-slack-signature` and `x-slack-request-timestamp` arrive on every request
> and are ignored, so anyone who learns the URL can approve or reject any
> finding. Fine behind a private tunnel you control; close this before running
> it anywhere persistent.

## Known gaps

- Failure handling is partial. An empty scrape is caught and recorded as
  `failed` with a reason, but an execution that dies for any other reason —
  or an item silently dropped mid-pipeline — still leaves a row stuck in
  `processing` that blocks its own retry via `ON CONFLICT`. There is no sweep
  for stale claims.
- `findings` records no `model` or `prompt_version`, so a change in accuracy
  cannot be attributed to a prompt change rather than to different articles.
- Dedup exists in both Redis and Postgres; the two can be cleared
  independently and disagree.
- `url_hash` is taken over the raw link, so `?utm_source=` variants of one
  article are scraped and billed twice.

## Schema changes

`scripts/models.py` is the source of truth. Edit it, then generate a migration:

```bash
.venv/bin/alembic revision --autogenerate -m "what changed"
.venv/bin/alembic upgrade head
```

Read the generated file before applying it — autogenerate misses some things
(renames look like drop + add, and it cannot see CHECK constraints added
outside the models).

`ALEMBIC_DB=<name>` points Alembic at another database on the same server, for
generating or rehearsing a migration without touching the real one.
