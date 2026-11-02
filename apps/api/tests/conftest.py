"""Test setup: a dedicated, freshly migrated database `newton_test` on a real PostgreSQL.

Required environment variable:
    TEST_DATABASE_ADMIN_URL  admin URL of the server, e.g.
                             postgresql+psycopg://newton_admin:...@db:5432/postgres
    NEWTON_APP_DB_PASSWORD   password for the restricted role `newton_app`
"""

import os
from collections.abc import Callable, Iterator
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.engine import make_url

TEST_DB = "newton_test"

_admin_server_url = make_url(os.environ["TEST_DATABASE_ADMIN_URL"])
_admin_test_url = _admin_server_url.set(database=TEST_DB)
_app_test_url = _admin_test_url.set(
    username="newton_app", password=os.environ["NEWTON_APP_DB_PASSWORD"]
)

os.environ["DATABASE_ADMIN_URL"] = _admin_test_url.render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = _app_test_url.render_as_string(hide_password=False)
os.environ["NEWTON_ENV"] = "test"
os.environ.setdefault("JWT_SECRET", "test-only-secret-" + "x" * 32)


def _dsn(url) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


ADMIN_DSN = _dsn(_admin_test_url)
APP_DSN = _dsn(_app_test_url)

TABLES = ["audit_log", "sessions", "memberships", "users", "companies"]
PASSWORD = "Correct-Horse-42"


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    with psycopg.connect(_dsn(_admin_server_url), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    from newton.cli import migrate

    migrate()
    yield


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
    from newton.domains.auth.router import email_throttle, ip_throttle

    email_throttle.clear()
    ip_throttle.clear()
    yield


@pytest.fixture
def admin_conn() -> Iterator[psycopg.Connection]:
    """Owner connection (bypasses RLS) used to arrange test data and inspect results."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        yield conn


@pytest.fixture
def make_company(admin_conn: psycopg.Connection) -> Callable[..., UUID]:
    def _make(name: str = "Entreprise", is_demo: bool = False) -> UUID:
        cid = uuid4()
        admin_conn.execute(
            "INSERT INTO companies (id, name, is_demo) VALUES (%s, %s, %s)", (cid, name, is_demo)
        )
        return cid

    return _make


@pytest.fixture
def make_user(admin_conn: psycopg.Connection) -> Callable[..., UUID]:
    from newton.core.security import hash_password

    hashed = hash_password(PASSWORD)

    def _make(
        email: str,
        company_id: UUID | None = None,
        role: str = "admin",
        must_change_password: bool = False,
        password_hash: str | None = None,
    ) -> UUID:
        uid = uuid4()
        admin_conn.execute(
            "INSERT INTO users (id, email, full_name, password_hash, must_change_password) "
            "VALUES (%s, %s, %s, %s, %s)",
            (uid, email, email.split("@")[0], password_hash or hashed, must_change_password),
        )
        if company_id is not None:
            add_membership(admin_conn, company_id, uid, role)
        return uid

    return _make


def add_membership(conn: psycopg.Connection, company_id: UUID, user_id: UUID, role: str) -> None:
    conn.execute(
        "INSERT INTO memberships (company_id, user_id, role) VALUES (%s, %s, %s)",
        (company_id, user_id, role),
    )


@pytest.fixture
def client_factory() -> Iterator[Callable[[], object]]:
    from fastapi.testclient import TestClient

    from newton.main import app

    clients: list[TestClient] = []

    def _make() -> TestClient:
        c = TestClient(app, headers={"x-newton-csrf": "1"})
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.close()


def login(client, email: str, password: str = PASSWORD, company_id: UUID | None = None):
    body: dict[str, str] = {"email": email, "password": password}
    if company_id:
        body["company_id"] = str(company_id)
    return client.post("/api/auth/login", json=body)


@pytest.fixture
def two_tenants(make_company, make_user, client_factory):
    """Company A and company B, each with an admin logged in on its own client."""
    a = make_company("Elec A")
    b = make_company("Elec B")
    ua = make_user("admin@a.example.com", a)
    ub = make_user("admin@b.example.com", b)
    ca, cb = client_factory(), client_factory()
    assert login(ca, "admin@a.example.com").status_code == 200
    assert login(cb, "admin@b.example.com").status_code == 200
    return {"a": a, "b": b, "ua": ua, "ub": ub, "ca": ca, "cb": cb}
