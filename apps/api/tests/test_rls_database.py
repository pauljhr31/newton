"""Isolation enforced by PostgreSQL itself (RLS), independently of the API code.

These tests connect as the restricted runtime role `newton_app`, exactly like the API.
"""

from uuid import uuid4

import psycopg
import pytest

from tests.conftest import APP_DSN

TENANT_TABLES = ["companies", "memberships", "users", "sessions", "audit_log"]


def _app_conn() -> psycopg.Connection:
    return psycopg.connect(APP_DSN)


def _ctx(conn: psycopg.Connection, company_id=None, user_id=None) -> None:
    conn.execute(
        "SELECT set_config('app.company_id', %s, true), set_config('app.user_id', %s, true)",
        (str(company_id or ""), str(user_id or "")),
    )


@pytest.fixture
def world(make_company, make_user, admin_conn):
    a, b = make_company("A"), make_company("B")
    ua = make_user("ua@a.example.com", a)
    ub = make_user("ub@b.example.com", b)
    for cid, uid in ((a, ua), (b, ub)):
        admin_conn.execute(
            "INSERT INTO sessions (user_id, company_id, refresh_token_hash, expires_at) "
            "VALUES (%s, %s, 'h', now() + interval '1 day')",
            (uid, cid),
        )
        admin_conn.execute(
            "INSERT INTO audit_log (company_id, actor_type, action, entity_type) "
            "VALUES (%s, 'system', 'test', 'test')",
            (cid,),
        )
    return {"a": a, "b": b, "ua": ua, "ub": ub}


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_no_context_sees_nothing(world, table):
    with _app_conn() as conn:
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608


def test_company_a_context_sees_only_company_a(world):
    a, ua, ub = world["a"], world["ua"], world["ub"]
    with _app_conn() as conn:
        _ctx(conn, a, ua)
        assert [r[0] for r in conn.execute("SELECT id FROM companies")] == [a]
        assert {r[0] for r in conn.execute("SELECT company_id FROM memberships")} == {a}
        users = {r[0] for r in conn.execute("SELECT id FROM users")}
        assert ua in users and ub not in users
        assert {r[0] for r in conn.execute("SELECT company_id FROM sessions")} == {a}
        assert {r[0] for r in conn.execute("SELECT company_id FROM audit_log")} == {a}


def test_spoofed_company_context_without_user_still_sees_only_that_company(world):
    with _app_conn() as conn:
        _ctx(conn, world["b"])
        assert [r[0] for r in conn.execute("SELECT id FROM companies")] == [world["b"]]
        assert world["ua"] not in {r[0] for r in conn.execute("SELECT id FROM users")}


def test_cannot_insert_rows_for_another_company(world):
    a, b, ua = world["a"], world["b"], world["ua"]
    statements = [
        (
            "INSERT INTO memberships (company_id, user_id, role) VALUES (%s, %s, 'admin')",
            (b, ua),
        ),
        (
            "INSERT INTO audit_log (company_id, actor_type, action, entity_type) "
            "VALUES (%s, 'user', 'x', 'x')",
            (b,),
        ),
        (
            "INSERT INTO sessions (user_id, company_id, refresh_token_hash, expires_at) "
            "VALUES (%s, %s, 'h', now())",
            (ua, b),
        ),
    ]
    for stmt, params in statements:
        with _app_conn() as conn:
            _ctx(conn, a, ua)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(stmt, params)


def test_cannot_update_another_company(world):
    a, b, ua, ub = world["a"], world["b"], world["ua"], world["ub"]
    with _app_conn() as conn:
        _ctx(conn, a, ua)
        assert (
            conn.execute("UPDATE companies SET name = 'hacked' WHERE id = %s", (b,)).rowcount == 0
        )
        assert (
            conn.execute(
                "UPDATE memberships SET role = 'viewer' WHERE company_id = %s", (b,)
            ).rowcount
            == 0
        )
        assert conn.execute("UPDATE users SET full_name = 'x' WHERE id = %s", (ub,)).rowcount == 0
        assert (
            conn.execute(
                "UPDATE sessions SET revoked_at = now() WHERE company_id = %s", (b,)
            ).rowcount
            == 0
        )
        # Moving one's own company row to another id/tenant is refused too.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE memberships SET company_id = %s WHERE company_id = %s", (b, a))


def test_cannot_update_other_users_even_in_same_company(make_company, make_user):
    a = make_company("A")
    u1 = make_user("u1@a.example.com", a)
    u2 = make_user("u2@a.example.com", a, role="viewer")
    with _app_conn() as conn:
        _ctx(conn, a, u1)
        assert (
            conn.execute("UPDATE users SET password_hash = 'x' WHERE id = %s", (u2,)).rowcount == 0
        )


@pytest.mark.parametrize(
    "stmt",
    [
        "DELETE FROM companies",
        "DELETE FROM users",
        "DELETE FROM memberships",
        "DELETE FROM sessions",
        "DELETE FROM audit_log",
        "UPDATE audit_log SET action = 'x'",
        "TRUNCATE audit_log",
        "INSERT INTO companies (name) VALUES ('x')",
        "ALTER TABLE companies DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE companies NO FORCE ROW LEVEL SECURITY",
        "DROP POLICY companies_select ON companies",
        "SET ROLE postgres",
        "CREATE TABLE evil (id int)",
    ],
)
def test_app_role_forbidden_statements(world, stmt):
    with _app_conn() as conn:
        _ctx(conn, world["a"], world["ua"])
        with pytest.raises(psycopg.Error):
            conn.execute(stmt)


def test_audit_log_immutable_even_for_owner(world, admin_conn):
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        admin_conn.execute("UPDATE audit_log SET action = 'tampered'")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        admin_conn.execute("DELETE FROM audit_log")


def test_find_user_requires_company_context(world):
    with _app_conn() as conn, pytest.raises(psycopg.errors.RaiseException):
        conn.execute("SELECT newton_find_user_id('ua@a.example.com')")


def test_session_lookup_returns_nothing_for_unknown_id(world):
    with _app_conn() as conn:
        assert (
            conn.execute("SELECT * FROM newton_session_lookup(%s)", (uuid4(),)).fetchone() is None
        )
