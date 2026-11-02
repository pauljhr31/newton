"""Authentication flows through the HTTP API."""

from datetime import UTC, datetime, timedelta

import jwt

from newton.core.config import get_settings
from tests.conftest import PASSWORD, add_membership, login


def test_health(client_factory):
    r = client_factory().get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_login_success_sets_httponly_cookies(make_company, make_user, client_factory):
    cid = make_company("Elec A")
    make_user("Boss@A.example.com".lower(), cid)
    c = client_factory()
    r = login(c, "BOSS@a.example.com")  # e-mail is case-insensitive
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company"]["id"] == str(cid) and body["role"] == "admin"
    cookies = r.headers.get_list("set-cookie")
    assert any(h.startswith("newton_access=") and "HttpOnly" in h for h in cookies)
    assert any(
        h.startswith("newton_refresh=") and "HttpOnly" in h and "Path=/api/auth" in h
        for h in cookies
    )
    assert all("SameSite=strict" in h for h in cookies)
    assert c.get("/api/auth/me").status_code == 200


def test_login_wrong_password_and_unknown_email_same_answer(
    make_company, make_user, client_factory
):
    make_user("u@a.example.com", make_company())
    c = client_factory()
    r1 = login(c, "u@a.example.com", "Wrong-Password-1")
    r2 = login(c, "nobody@a.example.com", "Wrong-Password-1")
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_inactive_user_cannot_login(make_company, make_user, client_factory, admin_conn):
    uid = make_user("u@a.example.com", make_company())
    admin_conn.execute("UPDATE users SET is_active = false WHERE id = %s", (uid,))
    assert login(client_factory(), "u@a.example.com").status_code == 401


def test_user_without_company_cannot_login(make_user, client_factory):
    make_user("lonely@a.example.com")
    r = login(client_factory(), "lonely@a.example.com")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "no_company"


def test_login_throttled_after_repeated_failures(make_company, make_user, client_factory):
    make_user("u@a.example.com", make_company())
    c = client_factory()
    for _ in range(get_settings().login_max_failures):
        assert login(c, "u@a.example.com", "Wrong-Password-1").status_code == 401
    r = login(c, "u@a.example.com")  # even the right password is refused for now
    assert r.status_code == 429


def test_protected_endpoints_require_auth(client_factory):
    c = client_factory()
    for path in ("/api/auth/me", "/api/company", "/api/users", "/api/audit"):
        assert c.get(path).status_code == 401, path


def test_tampered_or_expired_token_rejected(two_tenants, client_factory):
    s = get_settings()
    t = two_tenants
    original = t["ca"].cookies.get("newton_access")
    claims = jwt.decode(original, s.jwt_secret, algorithms=["HS256"])

    # Same claims but pointing at company B, signed with a wrong key.
    forged = jwt.encode({**claims, "cid": str(t["b"])}, "wrong-key-" + "y" * 32, algorithm="HS256")
    c = client_factory()
    c.cookies.set("newton_access", forged)
    assert c.get("/api/company").status_code == 401

    # Correctly signed (attacker knows nothing) but expired.
    expired = jwt.encode(
        {**claims, "exp": datetime.now(UTC) - timedelta(seconds=1)}, s.jwt_secret, algorithm="HS256"
    )
    c2 = client_factory()
    c2.cookies.set("newton_access", expired)
    assert c2.get("/api/company").status_code == 401


def test_valid_token_with_swapped_company_rejected(two_tenants, client_factory):
    """Even a correctly signed token is useless for a company the session was not opened for."""
    s = get_settings()
    t = two_tenants
    claims = jwt.decode(t["ca"].cookies.get("newton_access"), s.jwt_secret, algorithms=["HS256"])
    swapped = jwt.encode({**claims, "cid": str(t["b"])}, s.jwt_secret, algorithm="HS256")
    c = client_factory()
    c.cookies.set("newton_access", swapped)
    assert c.get("/api/company").status_code == 401


def test_csrf_header_required(client_factory):
    from fastapi.testclient import TestClient

    from newton.main import app

    with TestClient(app) as raw:
        r = raw.post("/api/auth/login", json={"email": "a@a.example.com", "password": "x"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "csrf"


def test_refresh_rotates_and_detects_reuse(two_tenants):
    c = two_tenants["ca"]
    old_refresh = c.cookies.get("newton_refresh", path="/api/auth")
    r = c.post("/api/auth/refresh")
    assert r.status_code == 200
    new_refresh = c.cookies.get("newton_refresh", path="/api/auth")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the old refresh token revokes the whole session.
    c.cookies.set("newton_refresh", old_refresh, path="/api/auth")
    r = c.post("/api/auth/refresh")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "session_revoked"
    c.cookies.set("newton_refresh", new_refresh, path="/api/auth")
    assert c.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_session(two_tenants):
    c = two_tenants["ca"]
    access = c.cookies.get("newton_access")
    refresh = c.cookies.get("newton_refresh", path="/api/auth")
    assert c.post("/api/auth/logout").status_code == 204
    # Re-using the captured cookies after logout must fail.
    c.cookies.set("newton_access", access)
    c.cookies.set("newton_refresh", refresh, path="/api/auth")
    assert c.get("/api/auth/me").status_code == 401
    assert c.post("/api/auth/refresh").status_code == 401


def test_must_change_password_flow(make_company, make_user, client_factory):
    cid = make_company()
    make_user("new@a.example.com", cid, must_change_password=True)
    c = client_factory()
    assert login(c, "new@a.example.com").status_code == 200
    assert c.get("/api/auth/me").json()["must_change_password"] is True
    r = c.get("/api/company")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "password_change_required"

    weak = c.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"}
    )
    assert weak.status_code == 400 and weak.json()["detail"]["code"] == "weak_password"
    wrong = c.post(
        "/api/auth/change-password",
        json={"current_password": "Not-The-One-1", "new_password": "Brand-New-Pass-9"},
    )
    assert wrong.status_code == 400
    ok = c.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-9"},
    )
    assert ok.status_code == 204
    assert c.get("/api/company").status_code == 200

    c2 = client_factory()
    assert login(c2, "new@a.example.com").status_code == 401
    assert login(c2, "new@a.example.com", "Brand-New-Pass-9").status_code == 200


def test_password_change_logs_out_other_sessions(make_company, make_user, client_factory):
    make_user("u@a.example.com", make_company())
    c1, c2 = client_factory(), client_factory()
    login(c1, "u@a.example.com")
    login(c2, "u@a.example.com")
    r = c1.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-9"},
    )
    assert r.status_code == 204
    assert c1.get("/api/auth/me").status_code == 200
    assert c2.get("/api/auth/me").status_code == 401


def test_multi_company_user_login_and_switch(make_company, make_user, client_factory, admin_conn):
    a, b, other = make_company("A"), make_company("B"), make_company("Other")
    uid = make_user("multi@a.example.com", a, role="admin")
    add_membership(admin_conn, b, uid, "viewer")
    c = client_factory()
    me = login(c, "multi@a.example.com").json()
    assert me["company"]["id"] == str(a)
    assert {x["id"] for x in me["companies"]} == {str(a), str(b)}

    r = c.post("/api/auth/switch-company", json={"company_id": str(b)})
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    assert c.get("/api/company").json()["id"] == str(b)

    r = c.post("/api/auth/switch-company", json={"company_id": str(other)})
    assert r.status_code == 403

    r = login(client_factory(), "multi@a.example.com", company_id=other)
    assert r.status_code == 403
