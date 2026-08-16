#!/usr/bin/env python3
"""Re-run one article through the pipeline from a clean slate.

    rerun-article.py <link>

Clears the article's Postgres rows and Redis key, loads only that row into the
data table, fires the runner, waits for a terminal status, then restores the
full CSV.

The row must already be in testdata/articles.csv — the skill adds it first,
after you approve the proposed fields.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WEBHOOK = "http://localhost:5678/webhook/run-dataset"
TIMEOUT_S = 300


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def psql(sql):
    # -tA still emits the command tag (`DELETE 1`) after the returned rows
    out = run(["docker", "compose", "exec", "-T", "postgres",
               "psql", "-U", "n8n", "-d", "n8n", "-tA", "-c", sql]).stdout.strip()
    lines = [l for l in out.splitlines()
             if not l.split(" ")[0] in ("INSERT", "UPDATE", "DELETE", "SELECT")]
    return "\n".join(lines).strip()


def redis(*args):
    pw = ""
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith("REDIS_PASSWORD="):
            pw = line.split("=", 1)[1].strip()
    return run(["docker", "compose", "exec", "-T", "redis", "redis-cli",
                "-a", pw, "--no-auth-warning", *args]).stdout.strip()


def preflight():
    if run(["docker", "compose", "exec", "-T", "n8n", "true"]).returncode != 0:
        sys.exit("error: n8n is not running — start it with `docker compose up -d n8n`")
    active = run(["docker", "compose", "exec", "-T", "n8n",
                  "n8n", "list:workflow", "--active=true"]).stdout
    if "run dataset" not in active:
        sys.exit("error: the `run dataset` workflow is not active; the webhook will 404")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    link = sys.argv[1]
    url_hash = hashlib.sha256(link.encode()).hexdigest()

    preflight()

    # 1. clear this article's traces so it is treated as new
    deleted = psql(f"DELETE FROM articles WHERE url_hash = '{url_hash}' RETURNING id;")
    redis("DEL", f"article:{url_hash}")
    print(f"cleared: postgres row {deleted or '(none)'}, redis key article:{url_hash[:12]}…")

    # 2. narrow the data table to just this article
    if run([sys.executable, "scripts/load-articles.py", link]).returncode != 0:
        sys.exit("error: could not load the article into the data table")

    try:
        # 3. fire the runner and wait for a terminal status
        for _ in range(20):
            if run(["curl", "-fsS", "-o", "/dev/null", "-X", "POST", WEBHOOK]).returncode == 0:
                break
            time.sleep(3)
        else:
            sys.exit("error: the runner webhook never responded")
        print("running…")

        deadline = time.time() + TIMEOUT_S
        status = ""
        while time.time() < deadline:
            status = psql(f"SELECT status FROM articles WHERE url_hash = '{url_hash}';")
            if status in ("completed", "failed"):
                break
            time.sleep(5)

        # 4. report
        row = psql(
            "SELECT json_build_object("
            "  'status', a.status, 'last_error', coalesce(a.last_error,''),"
            "  'title', a.raw_payload->>'title',"
            "  'findings', coalesce(json_agg(json_build_object("
            "     'company', f.company_name, 'software', f.software_name,"
            "     'domain', f.domain, 'review', f.review_status,"
            "     'evidence', f.evidence)) FILTER (WHERE f.id IS NOT NULL), '[]'))"
            " FROM articles a LEFT JOIN findings f ON f.article_id = a.id"
            f" WHERE a.url_hash = '{url_hash}' GROUP BY a.id;")
        if not row:
            print("no article row — the run never claimed it")
        else:
            d = json.loads(row)
            print(f"\nstatus : {d['status'] or 'still processing'}")
            print(f"title  : {d['title']}")
            if d["last_error"]:
                print(f"error  : {d['last_error']}")
            if d["findings"]:
                for f in d["findings"]:
                    print(f"\nfinding: {f['company']} / {f['software'] or '-'} "
                          f"({f['domain'] or 'no domain'}) [{f['review']}]")
                    print(f"         {f['evidence']}")
            else:
                print("finding: none")
    finally:
        # 5. always put the full corpus back
        run([sys.executable, "scripts/load-articles.py"])
        print("\ndata table restored from testdata/articles.csv")


if __name__ == "__main__":
    main()
