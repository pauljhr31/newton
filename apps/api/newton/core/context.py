"""Authenticated request context and role checks.

Each authenticated request:
1. reads the short-lived access token from an httpOnly cookie,
2. sets the RLS tenant context (user + company) for the transaction,
3. checks the session is not revoked and the membership is still active.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from newton.core.db import get_db, set_tenant_context
from newton.core.errors import api_error
from newton.core.models import AuthSession, Membership, User
from newton.core.security import decode_access_token

Role = Literal["admin", "estimator", "viewer"]
ROLES: tuple[Role, ...] = ("admin", "estimator", "viewer")

ACCESS_COOKIE = "newton_access"
REFRESH_COOKIE = "newton_refresh"


@dataclass(frozen=True)
class RequestContext:
    user_id: UUID
    company_id: UUID
    session_id: UUID
    role: Role
    email: str
    full_name: str
    must_change_password: bool
    ip: str | None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _unauthenticated() -> Exception:
    return api_error(401, "not_authenticated", "Veuillez vous connecter.")


def get_context_allow_password_change(
    request: Request, db: Session = Depends(get_db)
) -> RequestContext:
    token = request.cookies.get(ACCESS_COOKIE)
    payload = decode_access_token(token) if token else None
    if payload is None:
        raise _unauthenticated()
    try:
        user_id = UUID(payload["sub"])
        company_id = UUID(payload["cid"])
        session_id = UUID(payload["sid"])
    except (KeyError, ValueError):
        raise _unauthenticated() from None

    set_tenant_context(db, user_id=user_id, company_id=company_id)

    session_row = db.execute(
        select(AuthSession.revoked_at, AuthSession.expires_at).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.company_id == company_id,
        )
    ).first()
    if (
        session_row is None
        or session_row.revoked_at is not None
        or session_row.expires_at <= datetime.now(UTC)
    ):
        raise _unauthenticated()

    row = db.execute(
        select(User.email, User.full_name, User.must_change_password, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            Membership.company_id == company_id,
            Membership.is_active.is_(True),
        )
    ).first()
    if row is None:
        raise _unauthenticated()

    return RequestContext(
        user_id=user_id,
        company_id=company_id,
        session_id=session_id,
        role=row.role,
        email=row.email,
        full_name=row.full_name,
        must_change_password=row.must_change_password,
        ip=client_ip(request),
    )


def get_context(
    ctx: RequestContext = Depends(get_context_allow_password_change),
) -> RequestContext:
    if ctx.must_change_password:
        raise api_error(
            403,
            "password_change_required",
            "Vous devez changer votre mot de passe provisoire avant de continuer.",
        )
    return ctx


def require_role(*allowed: Role) -> Callable[..., RequestContext]:
    def checker(ctx: RequestContext = Depends(get_context)) -> RequestContext:
        if ctx.role not in allowed:
            raise api_error(403, "forbidden", "Votre rôle ne permet pas cette action.")
        return ctx

    return checker
