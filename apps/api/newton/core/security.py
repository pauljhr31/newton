"""Password hashing (Argon2id) and token helpers."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from newton.core.config import get_settings

_hasher = PasswordHasher()  # argon2-cffi defaults to Argon2id with RFC 9106 parameters
# Used to keep login timing similar when the e-mail does not exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

MIN_PASSWORD_LENGTH = 12
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> str | None:
    """Return an error message in French, or None if acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
    if password.lower() == password or password.upper() == password:
        return "Le mot de passe doit contenir des majuscules et des minuscules."
    if not any(c.isdigit() for c in password):
        return "Le mot de passe doit contenir au moins un chiffre."
    return None


def generate_temporary_password() -> str:
    # Guaranteed to satisfy validate_password_strength.
    return "Tmp-" + secrets.token_urlsafe(12) + "a1B"


def create_access_token(*, user_id: UUID, company_id: UUID, session_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "cid": str(company_id),
        "sid": str(session_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, str] | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    return payload


def new_refresh_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_token(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()
