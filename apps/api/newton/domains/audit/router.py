"""Read access to the audit trail of the current company (admin only)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from newton.core.context import RequestContext, require_role
from newton.core.db import get_db
from newton.core.models import AuditLog, User

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditEntryOut(BaseModel):
    id: int
    created_at: datetime
    actor_type: str
    actor_user_id: UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None


@router.get("", response_model=list[AuditEntryOut])
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    ctx: RequestContext = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.company_id == ctx.company_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        stmt = stmt.where(AuditLog.id < before_id)
    return [
        AuditEntryOut(
            id=a.id,
            created_at=a.created_at,
            actor_type=a.actor_type,
            actor_user_id=a.actor_user_id,
            actor_email=email,
            action=a.action,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            before=a.before,
            after=a.after,
            ip=a.ip,
        )
        for a, email in db.execute(stmt).all()
    ]
