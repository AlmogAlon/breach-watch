CREATE TYPE article_status AS ENUM ('processing', 'completed', 'failed');

CREATE TABLE articles (
    id           BIGSERIAL PRIMARY KEY,

    url          TEXT NOT NULL,
    title        TEXT,

    url_hash     TEXT NOT NULL UNIQUE
                 CONSTRAINT articles_url_hash_len CHECK (length(url_hash) = 64),

    content      TEXT,
    content_hash TEXT,

    status       article_status NOT NULL DEFAULT 'processing',
    has_breach   BOOLEAN,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at   TIMESTAMPTZ,
    processed_at TIMESTAMPTZ
);
