#!/usr/bin/env python3
"""Load testdata/articles.csv into the domain_breaches data table.

    load-articles.py                 load every row
    load-articles.py <link>          load only the row with that exact link

n8n caches data-table contents in memory, so the container is stopped for the
write and started again afterwards.
"""
import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV = REPO / "testdata" / "articles.csv"
TABLE = "data_table_user_PQYKeoIovociR6CS"
COLS = ["link", "title", "pubDate", "isoDate", "comments", "content", "contentSnippet"]


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def rows_from_csv(only_link=None):
    with CSV.open() as fh:
        rows = list(csv.DictReader(fh))
    if only_link:
        rows = [r for r in rows if r["link"] == only_link]
        if not rows:
            sys.exit(f"error: {only_link} is not in {CSV.relative_to(REPO)}")
    return rows


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    rows = rows_from_csv(only)

    esc = lambda s: (s or "").replace("'", "''")
    sql = [f"DELETE FROM {TABLE};",
           f"DELETE FROM sqlite_sequence WHERE name='{TABLE}';"]
    for r in rows:
        vals = ", ".join(f"'{esc(r.get(c))}'" for c in COLS)
        sql.append(f"INSERT INTO {TABLE} (createdAt, updatedAt, {', '.join(COLS)}) "
                   f"VALUES (datetime('now'), datetime('now'), {vals});")

    seed = Path("/tmp/_load_articles.sql")
    seed.write_text("\n".join(sql) + "\n")

    run(["docker", "compose", "stop", "n8n"])
    res = run(["docker", "run", "--rm",
               "-v", "breach-watch_n8n_data:/d", "-v", "/tmp:/host", "alpine",
               "sh", "-c",
               "apk add --no-cache sqlite >/dev/null 2>&1; "
               "sqlite3 /d/database.sqlite < /host/_load_articles.sql && "
               f"sqlite3 /d/database.sqlite 'SELECT count(*) FROM {TABLE};'"])
    run(["docker", "compose", "up", "-d", "n8n"])
    seed.unlink(missing_ok=True)

    if res.returncode != 0:
        sys.exit(f"error loading data table:\n{res.stderr.strip()}")
    print(f"loaded {res.stdout.strip()} row(s) into domain_breaches")


if __name__ == "__main__":
    main()
