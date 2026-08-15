CREATE TYPE article_status AS ENUM ('processing', 'completed', 'failed');

CREATE TABLE articles (
    id          BIGSERIAL PRIMARY KEY,
    url         TEXT NOT NULL,
    url_hash    TEXT NOT NULL UNIQUE,
    source      TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    status      article_status NOT NULL DEFAULT 'processing',
    last_error  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
