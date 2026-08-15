-- Referencing side of the FK: speeds up lookups by article and
-- avoids a seq scan on every ON DELETE CASCADE from articles.
CREATE INDEX IF NOT EXISTS findings_article_id_idx ON findings (article_id);

-- Review queue: WHERE review_status = 'pending'
CREATE INDEX IF NOT EXISTS findings_review_status_idx ON findings (review_status);

-- Work queue: WHERE status = 'processing'
CREATE INDEX IF NOT EXISTS articles_status_idx ON articles (status);
