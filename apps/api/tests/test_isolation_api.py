"""Cross-tenant isolation through the HTTP API: a user of A never reads or changes B."""


def test_company_endpoint_returns_own_company_only(two_tenants):
    t = two_tenants
    assert t["ca"].get("/api/company").json()["id"] == str(t["a"])
    assert t["cb"].get("/api/company").json()["id"] == str(t["b"])


def test_users_list_never_contains_other_company(two_tenants):
    t = two_tenants
    emails = {u["email"] for u in t["ca"].get("/api/users").json()}
    assert emails == {"admin@a.example.com"}


def test_cannot_modify_member_of_other_company(two_tenants, admin_conn):
    t = two_tenants
    ub = str(t["ub"])
    assert t["ca"].patch(f"/api/users/{ub}", json={"role": "viewer"}).status_code == 404
    assert t["ca"].post(f"/api/users/{ub}/revoke-sessions").status_code == 404
    row = admin_conn.execute(
        "SELECT role FROM memberships WHERE user_id = %s", (t["ub"],)
    ).fetchone()
    assert row[0] == "admin"
    assert t["cb"].get("/api/auth/me").status_code == 200  # B still logged in


def test_company_update_only_touches_own_company(two_tenants, admin_conn):
    t = two_tenants
    t["ca"].patch("/api/company", json={"name": "A renamed"})
    names = dict(admin_conn.execute("SELECT id, name FROM companies").fetchall())
    assert names[t["a"]] == "A renamed" and names[t["b"]] == "Elec B"


def test_audit_never_shows_other_company(two_tenants):
    t = two_tenants
    t["cb"].patch("/api/company", json={"name": "B secret rename"})
    entries = t["ca"].get("/api/audit", params={"limit": 200}).json()
    assert entries
    assert all("B secret rename" not in str(e) for e in entries)
    assert all(e["action"] != "company.updated" for e in entries)


def test_cannot_switch_into_other_company(two_tenants):
    t = two_tenants
    r = t["ca"].post("/api/auth/switch-company", json={"company_id": str(t["b"])})
    assert r.status_code == 403
    assert t["ca"].get("/api/company").json()["id"] == str(t["a"])
