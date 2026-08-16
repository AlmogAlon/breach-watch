"""Shared connections to the breach-watch stack.

Postgres and Redis are reachable from the host on their published ports, so
they are used directly rather than through `docker compose exec`. The n8n
data table lives in SQLite inside a Docker volume, which the host cannot
reach, so that one still goes through a container.
"""
import re
import subprocess
from pathlib import Path

import redis as redis_lib
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

REPO = Path(__file__).resolve().parent.parent

POSTGRES_PORT = 5434
REDIS_PORT = 6380
DB_USER = DB_NAME = "n8n"


def env() -> dict[str, str]:
    """Read .env without needing python-dotenv."""
    text = (REPO / ".env").read_text()
    return dict(re.findall(r"^(\w+)=(.*)$", text, re.M))


def engine():
    pw = env()["POSTGRES_PASSWORD"]
    return create_engine(
        f"postgresql+psycopg://{DB_USER}:{pw}@localhost:{POSTGRES_PORT}/{DB_NAME}",
        future=True,
    )


def session_factory() -> sessionmaker[Session]:
    return sessionmaker(engine(), expire_on_commit=False)


def redis():
    return redis_lib.Redis(
        host="localhost", port=REDIS_PORT, password=env()["REDIS_PASSWORD"],
        decode_responses=True,
    )


def compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args],
                          cwd=REPO, capture_output=True, text=True)
