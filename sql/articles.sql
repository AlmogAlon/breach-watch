-- status is a native enum; values sort in definition order (pipeline order).
CREATE TYPE article_status AS ENUM ('processing', 'completed', 'failed');

CREATE TABLE articles (
    id           BIGSERIAL PRIMARY KEY,
    url          TEXT NOT NULL UNIQUE,
    status       article_status NOT NULL DEFAULT 'processing',
    has_breach   BOOLEAN,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
