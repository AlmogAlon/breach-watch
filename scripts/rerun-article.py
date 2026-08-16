#!/usr/bin/env python3
"""Re-run one article through the pipeline from a clean slate.

    rerun-article.py <link>

Clears the article's Postgres rows and Redis key, narrows the data table to
that row, fires the runner, waits for a terminal status, then restores the
full corpus from testdata/articles.csv.

The row must already be in the CSV — the skill adds it first, once you have
approved the proposed fields.
"""
import hashlib
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stack import REPO, compose, engine, redis  # noqa: E402

WEBHOOK = "http://localhost:5678/webhook/run-dataset"
TERMINAL = ("completed", "failed")
POLL_TIMEOUT_S = 300


def preflight() -> None:
    if compose("exec", "-T", "n8n", "true").returncode != 0:
        sys.exit("error: n8n is not running — `docker compose up -d n8n`")
    active = compose("exec", "-T", "n8n", "n8n", "list:workflow", "--active=true").stdout
    if "run dataset" not in active:
        sys.exit("error: the `run dataset` workflow is not active; its webhook will 404")


def clear(conn, url_hash: str) -> int | None:
    """Delete the article so the pipeline treats it as new. Findings cascade."""
    row = conn.execute(
        text("DELETE FROM articles WHERE url_hash = :h RETURNING id"),
        {"h": url_hash},
    ).first()
    return row.id if row else None


def wait_for_terminal(conn_factory, url_hash: str) -> str | None:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        with conn_factory() as conn:
            status = conn.execute(
                text("SELECT status FROM articles WHERE url_hash = :h"),
                {"h": url_hash},
            ).scalar()
        if status in TERMINAL:
            return status
        time.sleep(5)
    return status


def report(conn, url_hash: str) -> None:
    article = conn.execute(text("""
        SELECT id, status, last_error, raw_payload->>'title' AS title
        FROM articles WHERE url_hash = :h
    """), {"h": url_hash}).first()

    if article is None:
        print("no article row — the run never claimed it")
        return

    print(f"\nstatus : {article.status}")
    print(f"title  : {article.title}")
    if article.last_error:
        print(f"error  : {article.last_error}")

    findings = conn.execute(text("""
        SELECT company_name, software_name, domain, review_status, evidence
        FROM findings WHERE article_id = :aid ORDER BY id
    """), {"aid": article.id}).all()

    if not findings:
        print("finding: none")
        return
    for f in findings:
        print(f"\nfinding: {f.company_name} / {f.software_name or '-'} "
              f"({f.domain or 'no domain'}) [{f.review_status}]")
        print(f"         {f.evidence}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    link = sys.argv[1]
    url_hash = hashlib.sha256(link.encode()).hexdigest()

    preflight()
    eng = engine()

    with eng.begin() as conn:
        deleted = clear(conn, url_hash)
    key = f"article:{url_hash}"
    removed = redis().delete(key)
    print(f"cleared: article row {deleted or '(none)'}, "
          f"redis key {url_hash[:12]}… {'removed' if removed else '(absent)'}")

    load = [sys.executable, str(REPO / "scripts" / "load-articles.py")]
    if subprocess.run(load + [link], cwd=REPO).returncode != 0:
        sys.exit("error: could not narrow the data table to that article")

    try:
        for _ in range(20):
            if subprocess.run(["curl", "-fsS", "-o", "/dev/null", "-X", "POST", WEBHOOK],
                              capture_output=True).returncode == 0:
                break
            time.sleep(3)
        else:
            sys.exit("error: the runner webhook never responded")
        print("running…")

        wait_for_terminal(eng.connect, url_hash)
        with eng.connect() as conn:
            report(conn, url_hash)
    finally:
        subprocess.run(load, cwd=REPO, capture_output=True)
        print("\ndata table restored from testdata/articles.csv")


if __name__ == "__main__":
    main()
