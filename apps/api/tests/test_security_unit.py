"""Unit tests for password and token helpers (no database needed)."""

from uuid import uuid4

from newton.core.security import (
    create_access_token,
    decode_access_token,
    generate_temporary_password,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_hash_is_argon2id_and_verifies():
    h = hash_password("Some-Password-1")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "Some-Password-1")
    assert not verify_password(h, "some-password-1")
    assert not verify_password(None, "Some-Password-1")
    assert not verify_password("not-a-hash", "x")


def test_password_strength_rules():
    assert validate_password_strength("Short1A") is not None
    assert validate_password_strength("alllowercase123") is not None
    assert validate_password_strength("NoDigitsHereAtAll") is not None
    assert validate_password_strength("Good-Password-42") is None


def test_generated_temporary_passwords_are_strong_and_unique():
    pwds = {generate_temporary_password() for _ in range(50)}
    assert len(pwds) == 50
    assert all(validate_password_strength(p) is None for p in pwds)


def test_access_token_roundtrip_and_tamper():
    uid, cid, sid = uuid4(), uuid4(), uuid4()
    token = create_access_token(user_id=uid, company_id=cid, session_id=sid)
    claims = decode_access_token(token)
    assert claims and claims["sub"] == str(uid) and claims["cid"] == str(cid)
    head, body, sig = token.split(".")
    assert decode_access_token(f"{head}.{body}.{sig[:-2]}xx") is None
    assert decode_access_token("garbage") is None
