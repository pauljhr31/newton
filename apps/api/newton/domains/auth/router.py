"""Authentication: login, refresh (with rotation), logout, password change, company switch."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session

from newton.core import audit
from newton.core.config import get_settings
from newton.core.context import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    RequestContext,
    client_ip,
    get_context_allow_password_change,
)
from newton.core.db import get_db, set_tenant_context
from newton.core.errors import api_error
from newton.core.models import AuthSession, Company, Membership, User
from newton.core.rate_limit import LoginThrottle
from newton.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_secret,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_settings = get_settings()
email_throttle = LoginThrottle(_settings.login_max_failures, _settings.login_window_minutes * 60)
ip_throttle = LoginThrottle(_settings.login_max_failures * 4, _settings.login_window_minutes * 60)

REFRESH_COOKIE_PATH = "/api/auth"


# ------------------------------------------------------------------ schemas
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    company_id: UUID | None = None


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class SwitchCompanyIn(BaseModel):
    company_id: UUID


class CompanyBrief(BaseModel):
    id: UUID
    name: str
    role: str
    is_demo: bool


class MeOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    must_change_password: bool
    role: str
    company: CompanyBrief
    companies: list[CompanyBrief]


# ------------------------------------------------------------------ helpers
def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=s.access_token_minutes * 60,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=s.refresh_token_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


def _user_companies(db: Session, user_id: UUID) -> list[CompanyBrief]:
    rows = db.execute(
        select(Company.id, Company.name, Company.is_demo, Membership.role)
        .join(Membership, Membership.company_id == Company.id)
        .where(Membership.user_id == user_id, Membership.is_active.is_(True))
        .order_by(Membership.created_at, Company.name)
    ).all()
    return [CompanyBrief(id=r.id, name=r.name, role=r.role, is_demo=r.is_demo) for r in rows]


def _open_session(
    db: Session, request: Request, response: Response, *, user_id: UUID, company_id: UUID
) -> UUID:
    set_tenant_context(db, user_id=user_id, company_id=company_id)
    session_id = uuid4()
    secret = new_refresh_secret()
    db.execute(
        insert(AuthSession).values(
            id=session_id,
            user_id=user_id,
            company_id=company_id,
            refresh_token_hash=hash_token(secret),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
            user_agent=(request.headers.get("user-agent") or "")[:300],
            ip=client_ip(request),
        )
    )
    access = create_access_token(user_id=user_id, company_id=company_id, session_id=session_id)
    _set_auth_cookies(response, access, f"{session_id}.{secret}")
    return session_id


def _revoke(db: Session, session_id: UUID, reason: str) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )


def _parse_refresh_cookie(value: str | None) -> tuple[UUID, str] | None:
    if not value or "." not in value:
        return None
    sid, secret = value.split(".", 1)
    try:
        return UUID(sid), secret
    except ValueError:
        return None


def _me(db: Session, user_id: UUID, company_id: UUID) -> MeOut:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    companies = _user_companies(db, user_id)
    current = next(c for c in companies if c.id == company_id)
    return MeOut(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        must_change_password=user.must_change_password,
        role=current.role,
        company=current,
        companies=companies,
    )


def _unauthorized_response(code: str, message: str) -> JSONResponse:
    resp = JSONResponse(status_code=401, content={"detail": {"code": code, "message": message}})
    _clear_auth_cookies(resp)
    return resp


# ------------------------------------------------------------------ endpoints
@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    ip = client_ip(request) or "unknown"
    keys_email, keys_ip = f"email:{email}", f"ip:{ip}"
    if email_throttle.is_blocked(keys_email) or ip_throttle.is_blocked(keys_ip):
        raise api_error(
            429,
            "too_many_attempts",
            "Trop de tentatives de connexion. Réessayez dans quelques minutes.",
        )

    row = db.execute(
        text("SELECT id, password_hash, is_active FROM newton_auth_lookup(:email)"),
        {"email": email},
    ).first()
    ok = verify_password(row.password_hash if row else None, body.password)
    if not ok or row is None or not row.is_active:
        email_throttle.record_failure(keys_email)
        ip_throttle.record_failure(keys_ip)
        raise api_error(401, "invalid_credentials", "E-mail ou mot de passe incorrect.")

    set_tenant_context(db, user_id=row.id)
    companies = _user_companies(db, row.id)
    if not companies:
        raise api_error(403, "no_company", "Ce compte n'a accès à aucune entreprise active.")
    if body.company_id is None:
        company_id = companies[0].id
    elif any(c.id == body.company_id for c in companies):
        company_id = body.company_id
    else:
        raise api_error(403, "not_a_member", "Vous n'avez pas accès à cette entreprise.")

    email_throttle.reset(keys_email)
    session_id = _open_session(db, request, response, user_id=row.id, company_id=company_id)
    audit.record(
        db,
        company_id=company_id,
        action="auth.login",
        entity_type="session",
        entity_id=session_id,
        actor_user_id=row.id,
        ip=client_ip(request),
    )
    return _me(db, row.id, company_id)


@router.post("/refresh", response_model=MeOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    parsed = _parse_refresh_cookie(request.cookies.get(REFRESH_COOKIE))
    if parsed is None:
        return _unauthorized_response("not_authenticated", "Veuillez vous connecter.")
    session_id, secret = parsed

    row = db.execute(
        text(
            "SELECT user_id, company_id, refresh_token_hash, expires_at, revoked_at "
            "FROM newton_session_lookup(:sid)"
        ),
        {"sid": session_id},
    ).first()
    if row is None or row.revoked_at is not None or row.expires_at <= datetime.now(UTC):
        return _unauthorized_response("session_expired", "Session expirée, reconnectez-vous.")

    set_tenant_context(db, user_id=row.user_id, company_id=row.company_id)

    if hash_token(secret) != row.refresh_token_hash:
        # An old refresh token was replayed: assume theft and kill the session.
        _revoke(db, session_id, "refresh_token_reuse")
        audit.record(
            db,
            company_id=row.company_id,
            action="auth.refresh_reuse_detected",
            entity_type="session",
            entity_id=session_id,
            actor_type="system",
            ip=client_ip(request),
        )
        return _unauthorized_response("session_revoked", "Session révoquée, reconnectez-vous.")

    still_member = db.execute(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.user_id == row.user_id,
            Membership.company_id == row.company_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
    ).first()
    if still_member is None:
        _revoke(db, session_id, "membership_inactive")
        return _unauthorized_response("session_revoked", "Accès retiré, reconnectez-vous.")

    new_secret = new_refresh_secret()
    db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id)
        .values(refresh_token_hash=hash_token(new_secret), last_used_at=datetime.now(UTC))
    )
    access = create_access_token(
        user_id=row.user_id, company_id=row.company_id, session_id=session_id
    )
    _set_auth_cookies(response, access, f"{session_id}.{new_secret}")
    return _me(db, row.user_id, row.company_id)


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    response = Response(status_code=204)
    parsed = _parse_refresh_cookie(request.cookies.get(REFRESH_COOKIE))
    if parsed is not None:
        session_id, secret = parsed
        row = db.execute(
            text("SELECT user_id, company_id, refresh_token_hash FROM newton_session_lookup(:sid)"),
            {"sid": session_id},
        ).first()
        if row is not None and hash_token(secret) == row.refresh_token_hash:
            set_tenant_context(db, user_id=row.user_id, company_id=row.company_id)
            _revoke(db, session_id, "logout")
            audit.record(
                db,
                company_id=row.company_id,
                action="auth.logout",
                entity_type="session",
                entity_id=session_id,
                actor_user_id=row.user_id,
                ip=client_ip(request),
            )
    _clear_auth_cookies(response)
    return response


@router.get("/me", response_model=MeOut)
def me(
    ctx: RequestContext = Depends(get_context_allow_password_change),
    db: Session = Depends(get_db),
):
    return _me(db, ctx.user_id, ctx.company_id)


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordIn,
    ctx: RequestContext = Depends(get_context_allow_password_change),
    db: Session = Depends(get_db),
) -> Response:
    current_hash = db.execute(select(User.password_hash).where(User.id == ctx.user_id)).scalar_one()
    if not verify_password(current_hash, body.current_password):
        raise api_error(400, "wrong_password", "Le mot de passe actuel est incorrect.")
    if body.new_password == body.current_password:
        raise api_error(400, "same_password", "Le nouveau mot de passe doit être différent.")
    problem = validate_password_strength(body.new_password)
    if problem:
        raise api_error(400, "weak_password", problem)

    db.execute(
        update(User)
        .where(User.id == ctx.user_id)
        .values(password_hash=hash_password(body.new_password), must_change_password=False)
    )
    # Log out every other session of this user, in every company.
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == ctx.user_id,
            AuthSession.id != ctx.session_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC), revoked_reason="password_changed")
    )
    audit.record(
        db,
        company_id=ctx.company_id,
        action="user.password_changed",
        entity_type="user",
        entity_id=ctx.user_id,
        actor_user_id=ctx.user_id,
        ip=ctx.ip,
    )
    return Response(status_code=204)


@router.post("/switch-company", response_model=MeOut)
def switch_company(
    body: SwitchCompanyIn,
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(get_context_allow_password_change),
    db: Session = Depends(get_db),
):
    companies = _user_companies(db, ctx.user_id)
    if not any(c.id == body.company_id for c in companies):
        raise api_error(403, "not_a_member", "Vous n'avez pas accès à cette entreprise.")
    _revoke(db, ctx.session_id, "company_switch")
    session_id = _open_session(
        db, request, response, user_id=ctx.user_id, company_id=body.company_id
    )
    audit.record(
        db,
        company_id=body.company_id,
        action="auth.switch_company",
        entity_type="session",
        entity_id=session_id,
        actor_user_id=ctx.user_id,
        ip=ctx.ip,
    )
    return _me(db, ctx.user_id, body.company_id)
