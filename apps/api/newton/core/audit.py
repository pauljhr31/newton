"""Append-only audit trail.

Entries are written in the same transaction as the change they describe, so a
change can never be committed without its audit entry (and vice versa).
"""

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.orm import Session

from newton.core.models import AuditLog

ActorType = Literal["user", "ai", "system"]

# Never copy these fields into the audit trail.
_REDACTED_KEYS = {"password", "password_hash", "refresh_token_hash", "temporary_password"}


def _clean(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    return {
        k: (str(v) if isinstance(v, UUID) else v)
        for k, v in data.items()
        if k not in _REDACTED_KEYS
    }


def record(
    db: Session,
    *,
    company_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | str | None = None,
    actor_type: ActorType = "user",
    actor_user_id: UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    db.execute(
        insert(AuditLog).values(
            company_id=company_id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=_clean(before),
            after=_clean(after),
            ip=ip,
        )
    )
