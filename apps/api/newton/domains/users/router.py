"""Company members: list, add, change role, deactivate, revoke sessions (admin only)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.orm import Session

from newton.core import audit
from newton.core.context import ROLES, RequestContext, Role, require_role
from newton.core.db import get_db
from newton.core.errors import api_error
from newton.core.models import AuthSession, Membership, User
from newton.core.security import (
    generate_temporary_password,
    hash_password,
    validate_password_strength,
)

router = APIRouter(prefix="/api/users", tags=["users"])


class MemberOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    must_change_password: bool


class MemberCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    temporary_password: str | None = Field(default=None, max_length=256)


class MemberCreateOut(BaseModel):
    member: MemberOut
    existing_account: bool
    # Shown once to the admin; never stored in clear text nor written to the audit log.
    temporary_password: str | None


class MemberUpdateIn(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


def _member(db: Session, company_id: UUID, user_id: UUID) -> MemberOut | None:
    row = db.execute(
        select(
            User.id,
            User.email,
            User.full_name,
            User.must_change_password,
            Membership.role,
            Membership.is_active,
        )
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.company_id == company_id, User.id == user_id)
    ).first()
    if row is None:
        return None
    return MemberOut(
        user_id=row.id,
        email=row.email,
        full_name=row.full_name,
        role=row.role,
        is_active=row.is_active,
        must_change_password=row.must_change_password,
    )


@router.get("", response_model=list[MemberOut])
def list_members(
    ctx: RequestContext = Depends(require_role("admin")), db: Session = Depends(get_db)
):
    rows = db.execute(
        select(
            User.id,
            User.email,
            User.full_name,
            User.must_change_password,
            Membership.role,
            Membership.is_active,
        )
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.company_id == ctx.company_id)
        .order_by(User.full_name)
    ).all()
    return [
        MemberOut(
            user_id=r.id,
            email=r.email,
            full_name=r.full_name,
            role=r.role,
            is_active=r.is_active,
            must_change_password=r.must_change_password,
        )
        for r in rows
    ]


@router.post("", response_model=MemberCreateOut, status_code=201)
def add_member(
    body: MemberCreateIn,
    ctx: RequestContext = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    email = body.email.lower()
    full_name = body.full_name.strip()
    if not full_name:
        raise api_error(400, "invalid_name", "Le nom ne peut pas être vide.")

    existing_id = db.execute(text("SELECT newton_find_user_id(:e)"), {"e": email}).scalar()
    temporary_password: str | None = None

    if existing_id is not None:
        already = db.execute(
            select(Membership.id).where(
                Membership.company_id == ctx.company_id, Membership.user_id == existing_id
            )
        ).first()
        if already is not None:
            raise api_error(
                409, "already_member", "Cet utilisateur fait déjà partie de l'entreprise."
            )
        # Existing account (member of another company): keep its own password.
        user_id = existing_id
    else:
        temporary_password = body.temporary_password or generate_temporary_password()
        problem = validate_password_strength(temporary_password)
        if problem:
            raise api_error(400, "weak_password", problem)
        user_id = uuid4()
        db.execute(
            insert(User).values(
                id=user_id,
                email=email,
                full_name=full_name,
                password_hash=hash_password(temporary_password),
                must_change_password=True,
            )
        )

    db.execute(
        insert(Membership).values(
            id=uuid4(),
            company_id=ctx.company_id,
            user_id=user_id,
            role=body.role,
            created_by=ctx.user_id,
        )
    )
    member = _member(db, ctx.company_id, user_id)
    if member is None:  # pragma: no cover - would mean RLS hid a row we just inserted
        raise api_error(500, "internal", "Erreur interne.")
    audit.record(
        db,
        company_id=ctx.company_id,
        action="membership.created",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=ctx.user_id,
        after={**member.model_dump(mode="json"), "existing_account": existing_id is not None},
        ip=ctx.ip,
    )
    return MemberCreateOut(
        member=member,
        existing_account=existing_id is not None,
        temporary_password=temporary_password if body.temporary_password is None else None,
    )


def _active_admin_count(db: Session, company_id: UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.company_id == company_id,
            Membership.role == "admin",
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
    ).scalar_one()


def _revoke_sessions(db: Session, company_id: UUID, user_id: UUID, reason: str) -> int:
    result = db.execute(
        update(AuthSession)
        .where(
            AuthSession.company_id == company_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )
    return result.rowcount or 0


@router.patch("/{user_id}", response_model=MemberOut)
def update_member(
    user_id: UUID,
    body: MemberUpdateIn,
    ctx: RequestContext = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    before = _member(db, ctx.company_id, user_id)
    if before is None:
        raise api_error(404, "not_found", "Utilisateur introuvable dans cette entreprise.")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "role" in changes and changes["role"] not in ROLES:
        raise api_error(400, "invalid_role", "Rôle inconnu.")
    if not changes:
        return before

    db.execute(
        update(Membership)
        .where(Membership.company_id == ctx.company_id, Membership.user_id == user_id)
        .values(**changes)
    )
    if _active_admin_count(db, ctx.company_id) == 0:
        # Raising rolls the whole transaction back.
        raise api_error(
            400, "last_admin", "L'entreprise doit garder au moins un administrateur actif."
        )
    if changes.get("is_active") is False:
        _revoke_sessions(db, ctx.company_id, user_id, "membership_deactivated")

    after = _member(db, ctx.company_id, user_id)
    if after is None:  # pragma: no cover
        raise api_error(500, "internal", "Erreur interne.")
    audit.record(
        db,
        company_id=ctx.company_id,
        action="membership.updated",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=ctx.user_id,
        before=before.model_dump(mode="json"),
        after=after.model_dump(mode="json"),
        ip=ctx.ip,
    )
    return after


@router.post("/{user_id}/revoke-sessions", status_code=204)
def revoke_member_sessions(
    user_id: UUID,
    ctx: RequestContext = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> Response:
    if _member(db, ctx.company_id, user_id) is None:
        raise api_error(404, "not_found", "Utilisateur introuvable dans cette entreprise.")
    count = _revoke_sessions(db, ctx.company_id, user_id, "revoked_by_admin")
    audit.record(
        db,
        company_id=ctx.company_id,
        action="sessions.revoked",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=ctx.user_id,
        after={"revoked_sessions": count},
        ip=ctx.ip,
    )
    return Response(status_code=204)
