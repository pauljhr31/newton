"""Database engine and per-request tenant context.

The runtime connects as the restricted role `newton_app`, which is subject to
PostgreSQL Row-Level Security (RLS). Every transaction sets the current user and
company with `set_config(..., is_local => true)`, so the values vanish at commit.
"""

from collections.abc import Iterator
from functools import lru_cache
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from newton.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One transaction per request: committed on success, rolled back on error."""
    session = _session_factory()()
    try:
        with session.begin():
            yield session
    finally:
        session.close()


def set_tenant_context(
    db: Session, *, user_id: UUID | None = None, company_id: UUID | None = None
) -> None:
    """Set RLS context for the current transaction only."""
    db.execute(
        text(
            "SELECT set_config('app.user_id', :uid, true), set_config('app.company_id', :cid, true)"
        ),
        {"uid": str(user_id) if user_id else "", "cid": str(company_id) if company_id else ""},
    )
