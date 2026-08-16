---
name: rerun-article
description: Re-run one article through the breach-watch pipeline from a clean slate. Use when the user asks to rerun, retest or re-check an article or URL, or wants to see what the agent makes of a new page. Clears the article's Postgres rows and Redis key first so it is processed as if never seen.
---

# Re-run an article

The user gives a URL. It may already be in the test corpus or be brand new.

## 1. Find or propose the row

The corpus is `testdata/articles.csv`, with the same columns an RSS item has:
`link, title, pubDate, isoDate, comments, content, contentSnippet`.

**If the URL is already in the CSV**, show that row and go to step 2.

**If it is new**, fetch the page and propose the fields. Do not invent values
silently — show the whole proposed row and let the user approve or edit it.

- `title` — the page's `<title>`, trimmed the way a submitter would write it.
  Drop a trailing site name after ` | `, ` - `, ` — ` or ` – `. For a PDF or an
  archive, describe it and keep the `[pdf]` / `[zip]` marker.
- `pubDate` — now, RFC 2822: `Sat, 16 Aug 2026 09:12:00 +0000`
- `isoDate` — the same instant: `2026-08-16T09:12:00.000Z`
- `comments` — look for the Hacker News discussion:
  `https://hn.algolia.com/api/v1/search?tags=story&restrictSearchableAttributes=url&query=<url>`
  Use `https://news.ycombinator.com/item?id=<objectID>` from the first hit;
  leave empty if there is none.
- `content` — `<a href="{comments}">Comments</a>`, or empty when there is no
  discussion link.
- `contentSnippet` — `Comments`, matching what the RSS parser produces.

Fetching the page may fail (a dead domain, a 403). That is fine and worth
testing — say so, propose a descriptive title, and carry on.

**Only after the user approves**, append the row to `testdata/articles.csv`.
Keep the existing column order and quote with `csv.writer` so embedded commas
and quotes survive.

## 2. Run it

```bash
python3 scripts/rerun-article.py '<link>'
```

The script does all of this, and always restores the full CSV at the end even
if the run fails:

1. `DELETE FROM articles WHERE url_hash = sha256(link)` — findings cascade
2. `DEL article:<url_hash>` in Redis
3. narrows `domain_breaches` to just this row
4. `POST /webhook/run-dataset`
5. polls until the row reaches `completed` or `failed` (5 min ceiling)
6. prints status, `last_error` and any finding
7. reloads the whole CSV into `domain_breaches`

## 3. Report

Give the user the status, the finding if there is one, and — when it matters —
whether that matches what they expected. Two failure modes read as success and
are worth calling out explicitly:

- `status = failed`, `last_error = scrape returned no article text` means the
  page yielded nothing to analyse. Common for PDFs, JS-rendered pages and dead
  domains. No model call was made.
- `status = completed` with no finding means the agent read the article and
  judged it not a breach. That is a real decision, not a failure.

## Related

- `python3 scripts/load-articles.py` reloads the whole corpus on its own.
- `python3 scripts/load-articles.py '<link>'` narrows the table to one row.

Both stop and restart n8n, because it caches data-table contents in memory.

## Requirements

n8n must be up and the `run dataset` workflow active — the script checks both
and exits with a clear message rather than failing obscurely.
