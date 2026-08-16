"""Alembic environment.

The database URL comes from _stack.py rather than alembic.ini, so the password
stays in .env and is never committed.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from _stack import engine  # noqa: E402
from models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ALEMBIC_DB points at a scratch database, so a migration can be generated or
# verified without touching the real one.
TARGET_DB = os.environ.get("ALEMBIC_DB") or None


def run_migrations_offline() -> None:
    context.configure(
        url=engine(TARGET_DB).url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine(TARGET_DB).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # surface type and default changes, not just added/dropped columns
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
