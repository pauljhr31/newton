"""Alembic environment. Migrations run with the admin (owner) role, never the app role."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

url = os.environ.get("DATABASE_ADMIN_URL")
if not url:
    raise RuntimeError("DATABASE_ADMIN_URL is not set")


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
