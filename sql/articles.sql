-- One row per article the pipeline has seen. The unit of record is the
-- article, not the breach: two articles covering the same incident are two
-- rows. Breaches named by an article live in findings.

-- status is a native enum; values sort in definition order (pipeline order).
CREATE TYPE article_status AS ENUM ('processing', 'completed', 'failed');

CREATE TABLE articles (
    id           BIGSERIAL PRIMARY KEY,

    url          TEXT NOT NULL,
    title        TEXT,

    -- Dedup key: sha256 of the link, matching what formated_json computes.
    -- Claimed on discovery, so INSERT ... ON CONFLICT (url_hash) DO NOTHING
    -- RETURNING id returns a row only when the article is new — claiming and
    -- deduping in one statement.
    --
    -- The CHECK pins the digest length. A workflow expression that emitted
    -- the hash twice produced 128-char keys in Redis, which went unnoticed
    -- because Redis has no schema; here it fails on write.
    url_hash     TEXT NOT NULL UNIQUE
                 CONSTRAINT articles_url_hash_len CHECK (length(url_hash) = 64),

    -- Exactly the text the agent was given, kept so a prompt change can be
    -- re-run against identical input. Re-scraping later yields different
    -- text (link rot, paywalls), which would confound the comparison.
    -- Postgres TOASTs this out-of-line, so it does not slow queue scans.
    content      TEXT,
    content_hash TEXT,

    status       article_status NOT NULL DEFAULT 'processing',
    has_breach   BOOLEAN,        -- NULL until the agent has judged it

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at   TIMESTAMPTZ,    -- when content was scraped
    processed_at TIMESTAMPTZ     -- when the agent finished
);
