CREATE TABLE findings (
    id BIGSERIAL PRIMARY KEY,

    article_id BIGINT NOT NULL
        REFERENCES articles(id)
        ON DELETE CASCADE,

    software_name TEXT,
    company_name TEXT,
    domain TEXT,
    evidence TEXT,

    review_status TEXT NOT NULL DEFAULT 'pending',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,

    CONSTRAINT findings_review_status_check
        CHECK (review_status IN ('pending', 'approved', 'rejected'))
);
