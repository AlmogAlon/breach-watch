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

CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected');

CREATE TABLE findings (
    id            BIGSERIAL PRIMARY KEY,

    article_id    BIGINT NOT NULL
                  REFERENCES articles(id)
                  ON DELETE CASCADE,

    software_name TEXT,
    company_name  TEXT,
    domain        TEXT,

    evidence      TEXT NOT NULL,

    review_status review_status NOT NULL DEFAULT 'pending',

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    reviewed_at   TIMESTAMPTZ,
    reviewed_by   TEXT
);

CREATE UNIQUE INDEX findings_unique_article_breach
ON findings (
    article_id,
    COALESCE(software_name, ''),
    COALESCE(domain, '')
);
