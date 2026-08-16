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

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stack import REPO, compose, redis, session_factory  # noqa: E402
from models import Article, ArticleStatus  # noqa: E402

WEBHOOK = "http://localhost:5678/webhook/run-dataset"
TERMINAL = {ArticleStatus.completed, ArticleStatus.failed}
POLL_TIMEOUT_S = 300


def preflight() -> None:
    if compose("exec", "-T", "n8n", "true").returncode != 0:
        sys.exit("error: n8n is not running — `docker compose up -d n8n`")
    active = compose("exec", "-T", "n8n", "n8n", "list:workflow", "--active=true").stdout
    if "run dataset" not in active:
        sys.exit("error: the `run dataset` workflow is not active; its webhook will 404")


def by_hash(session, url_hash: str) -> Article | None:
    return session.scalar(select(Article).where(Article.url_hash == url_hash))


def clear(Session, url_hash: str) -> int | None:
    """Delete the article so the pipeline treats it as new. Findings cascade."""
    with Session() as session:
        article = by_hash(session, url_hash)
        if article is None:
            return None
        article_id = article.id
        session.delete(article)
        session.commit()
        return article_id


def wait_for_terminal(Session, url_hash: str) -> None:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        with Session() as session:
            article = by_hash(session, url_hash)
            if article and article.status in TERMINAL:
                return
        time.sleep(5)


def report(Session, url_hash: str) -> None:
    with Session() as session:
        article = by_hash(session, url_hash)
        if article is None:
            print("no article row — the run never claimed it")
            return

        print(f"\nstatus : {article.status.value}")
        print(f"title  : {article.title}")
        if article.last_error:
            print(f"error  : {article.last_error}")

        if not article.findings:
            print("finding: none")
            return
        for f in article.findings:
            print(f"\nfinding: {f.company_name} / {f.software_name or '-'} "
                  f"({f.domain or 'no domain'}) [{f.review_status.value}]")
            print(f"         {f.evidence}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    link = sys.argv[1]
    url_hash = hashlib.sha256(link.encode()).hexdigest()

    preflight()
    Session = session_factory()

    deleted = clear(Session, url_hash)
    removed = redis().delete(f"article:{url_hash}")
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

        wait_for_terminal(Session, url_hash)
        report(Session, url_hash)
    finally:
        subprocess.run(load, cwd=REPO, capture_output=True)
        print("\ndata table restored from testdata/articles.csv")


if __name__ == "__main__":
    main()
