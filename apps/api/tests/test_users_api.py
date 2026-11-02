"""Company and member management, roles and audit entries."""

from tests.conftest import PASSWORD, login


def _audit_actions(admin_conn, company_id) -> list[str]:
    return [
        r[0]
        for r in admin_conn.execute(
            "SELECT action FROM audit_log WHERE company_id = %s ORDER BY id", (company_id,)
        )
    ]


def test_admin_adds_member_with_generated_temporary_password(
    two_tenants, client_factory, admin_conn
):
    t = two_tenants
    r = t["ca"].post(
        "/api/users",
        json={"email": "Tech@A.example.com", "full_name": "Technicien", "role": "estimator"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["existing_account"] is False
    temp = body["temporary_password"]
    assert temp and body["member"]["email"] == "tech@a.example.com"
    assert body["member"]["must_change_password"] is True

    c = client_factory()
    assert login(c, "tech@a.example.com", temp).status_code == 200
    assert c.get("/api/auth/me").json()["role"] == "estimator"

    # The temporary password is never stored in clear text nor audited.
    dump = str(admin_conn.execute("SELECT before, after FROM audit_log").fetchall())
    assert temp not in dump
    stored = admin_conn.execute(
        "SELECT password_hash FROM users WHERE email = 'tech@a.example.com'"
    ).fetchone()[0]
    assert stored.startswith("$argon2id$")
    assert "membership.created" in _audit_actions(admin_conn, t["a"])


def test_admin_provided_weak_temporary_password_rejected(two_tenants):
    r = two_tenants["ca"].post(
        "/api/users",
        json={
            "email": "x@a.example.com",
            "full_name": "X",
            "role": "viewer",
            "temporary_password": "123",
        },
    )
    assert r.status_code == 400


def test_adding_existing_account_keeps_its_password(two_tenants, client_factory):
    t = two_tenants
    # Admin of A adds the admin of B as a viewer of A.
    r = t["ca"].post(
        "/api/users",
        json={"email": "admin@b.example.com", "full_name": "ignored", "role": "viewer"},
    )
    assert r.status_code == 201
    assert r.json()["existing_account"] is True and r.json()["temporary_password"] is None
    # B's admin still logs in with their own password and now sees both companies.
    me = login(client_factory(), "admin@b.example.com").json()
    assert {c["id"] for c in me["companies"]} == {str(t["a"]), str(t["b"])}

    again = t["ca"].post(
        "/api/users",
        json={"email": "admin@b.example.com", "full_name": "x", "role": "viewer"},
    )
    assert again.status_code == 409


def test_roles_enforced(make_company, make_user, client_factory):
    cid = make_company()
    make_user("viewer@a.example.com", cid, role="viewer")
    make_user("estimator@a.example.com", cid, role="estimator")
    for email in ("viewer@a.example.com", "estimator@a.example.com"):
        c = client_factory()
        assert login(c, email).status_code == 200
        assert c.get("/api/company").status_code == 200  # everyone can read
        assert c.get("/api/users").status_code == 403
        assert c.get("/api/audit").status_code == 403
        assert c.patch("/api/company", json={"name": "x"}).status_code == 403
        r = c.post(
            "/api/users", json={"email": "z@a.example.com", "full_name": "z", "role": "admin"}
        )
        assert r.status_code == 403


def test_update_company_is_audited_with_before_after(two_tenants, admin_conn):
    t = two_tenants
    r = t["ca"].patch("/api/company", json={"name": "Elec A SARL", "siret": "12345678901234"})
    assert r.status_code == 200 and r.json()["name"] == "Elec A SARL"
    before, after, actor = admin_conn.execute(
        "SELECT before, after, actor_user_id FROM audit_log WHERE action = 'company.updated'"
    ).fetchone()
    assert before["name"] == "Elec A" and after["name"] == "Elec A SARL"
    assert actor == t["ua"]
    assert t["ca"].patch("/api/company", json={"siret": "123"}).status_code == 422


def test_cannot_remove_last_admin(two_tenants, admin_conn):
    t = two_tenants
    uid = str(t["ua"])
    r = t["ca"].patch(f"/api/users/{uid}", json={"role": "viewer"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "last_admin"
    r = t["ca"].patch(f"/api/users/{uid}", json={"is_active": False})
    assert r.status_code == 400
    role = admin_conn.execute(
        "SELECT role, is_active FROM memberships WHERE user_id = %s", (t["ua"],)
    ).fetchone()
    assert role == ("admin", True)  # rolled back


def test_deactivating_member_cuts_access_immediately(two_tenants, make_user, client_factory):
    t = two_tenants
    uid = make_user("tech@a.example.com", t["a"], role="estimator")
    tech = client_factory()
    assert login(tech, "tech@a.example.com").status_code == 200
    r = t["ca"].patch(f"/api/users/{uid}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert tech.get("/api/company").status_code == 401
    assert tech.post("/api/auth/refresh").status_code == 401
    assert login(client_factory(), "tech@a.example.com").status_code == 403


def test_admin_revokes_sessions(two_tenants, make_user, client_factory, admin_conn):
    t = two_tenants
    uid = make_user("tech@a.example.com", t["a"], role="estimator")
    tech = client_factory()
    login(tech, "tech@a.example.com")
    assert t["ca"].post(f"/api/users/{uid}/revoke-sessions").status_code == 204
    assert tech.get("/api/auth/me").status_code == 401
    assert login(tech, "tech@a.example.com", PASSWORD).status_code == 200
    assert "sessions.revoked" in _audit_actions(admin_conn, t["a"])


def test_audit_endpoint_lists_company_events(two_tenants):
    t = two_tenants
    t["ca"].patch("/api/company", json={"name": "Renamed"})
    entries = t["ca"].get("/api/audit").json()
    actions = [e["action"] for e in entries]
    assert actions[0] == "company.updated" and "auth.login" in actions
    assert entries[0]["actor_email"] == "admin@a.example.com"
    page = t["ca"].get("/api/audit", params={"limit": 1, "before_id": entries[0]["id"]}).json()
    assert len(page) == 1 and page[0]["id"] < entries[0]["id"]
