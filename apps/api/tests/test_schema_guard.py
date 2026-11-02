"""Guards that fail as soon as a future migration forgets tenant isolation.

Every new table must: enable + force RLS, have at least one policy, carry a
`company_id` column (unless explicitly allow-listed below), and never grant
DELETE / TRUNCATE to the runtime role without a documented reason.
"""

# Tables without company_id, with the reason they are safe.
NO_COMPANY_ID_ALLOWLIST = {
    "companies": "is the tenant table itself (policy on id)",
    "users": "global identities; visibility is derived from memberships",
}
IGNORED_TABLES = {"alembic_version"}


def _tables(conn) -> list[str]:
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in IGNORED_TABLES]


def test_every_table_has_rls_enabled_and_forced(admin_conn):
    rows = admin_conn.execute(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'"
    ).fetchall()
    assert rows, "no tables found"
    bad = [r[0] for r in rows if not (r[1] and r[2])]
    assert bad == [], f"tables without ENABLE+FORCE ROW LEVEL SECURITY: {bad}"


def test_every_table_has_policies(admin_conn):
    with_policies = {r[0] for r in admin_conn.execute("SELECT DISTINCT tablename FROM pg_policies")}
    missing = [t for t in _tables(admin_conn) if t not in with_policies]
    assert missing == [], f"tables without RLS policies: {missing}"


def test_every_business_table_has_company_id(admin_conn):
    cols = {
        r[0]
        for r in admin_conn.execute(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'company_id'"
        )
    }
    missing = [t for t in _tables(admin_conn) if t not in cols and t not in NO_COMPANY_ID_ALLOWLIST]
    assert missing == [], f"tables without company_id: {missing}"


def test_app_role_is_restricted(admin_conn):
    row = admin_conn.execute(
        "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles "
        "WHERE rolname = 'newton_app'"
    ).fetchone()
    assert row == (False, False, False, False)


def test_app_role_owns_nothing(admin_conn):
    # A table owner bypasses non-forced RLS and can ALTER it: the app must own nothing.
    owned = admin_conn.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
        "WHERE r.rolname = 'newton_app'"
    ).fetchall()
    assert owned == []


def test_app_role_has_no_delete_or_truncate(admin_conn):
    rows = admin_conn.execute(
        "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
        "WHERE grantee = 'newton_app' AND privilege_type IN ('DELETE', 'TRUNCATE')"
    ).fetchall()
    assert rows == []


def test_audit_log_is_insert_and_select_only(admin_conn):
    privs = {
        r[0]
        for r in admin_conn.execute(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = 'newton_app' AND table_name = 'audit_log'"
        )
    }
    assert privs == {"SELECT", "INSERT"}


def test_security_definer_functions_pin_search_path(admin_conn):
    rows = admin_conn.execute(
        "SELECT p.proname, p.proconfig FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.prosecdef"
    ).fetchall()
    assert rows, "expected SECURITY DEFINER functions"
    for name, config in rows:
        assert config and any(c.startswith("search_path=") for c in config), name
