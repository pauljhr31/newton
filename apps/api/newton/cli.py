"""Administration commands. They connect with the admin (owner) role.

Usage (inside the API container):
    python -m newton.cli migrate
    python -m newton.cli create-company --name "..." --admin-email ... --admin-name "..."
    python -m newton.cli seed-demo [--reset-passwords]
"""

import argparse
import os
import sys
from uuid import UUID, uuid4

import psycopg
from psycopg import sql

from newton.core.security import generate_temporary_password, hash_password

APP_ROLE = "newton_app"

DEMO_COMPANIES = [
    ("DÉMO - Électricité Alpha", "alpha"),
    ("DÉMO - Électricité Bêta", "beta"),
]
DEMO_ROLES = [("admin", "Admin"), ("estimator", "Chargé d'affaires"), ("viewer", "Lecture")]


def _admin_dsn() -> str:
    url = os.environ.get("DATABASE_ADMIN_URL")
    if not url:
        sys.exit("DATABASE_ADMIN_URL is not set")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def bootstrap_db() -> None:
    """Create or update the restricted runtime role with its LOGIN password."""
    password = os.environ.get("NEWTON_APP_DB_PASSWORD")
    if not password or len(password) < 16:
        sys.exit("NEWTON_APP_DB_PASSWORD must be set (16+ characters)")
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,)).fetchone()
        verb = sql.SQL("ALTER") if exists else sql.SQL("CREATE")
        conn.execute(
            sql.SQL(
                "{} ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}"
            ).format(verb, sql.Identifier(APP_ROLE), sql.Literal(password))
        )
    print(f"Role {APP_ROLE}: ready")


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    bootstrap_db()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "migrations"))
    command.upgrade(cfg, "head")
    print("Migrations: up to date")


def _audit(cur: psycopg.Cursor, company_id: UUID, action: str, entity: str, eid: UUID) -> None:
    cur.execute(
        "INSERT INTO audit_log (company_id, actor_type, action, entity_type, entity_id) "
        "VALUES (%s, 'system', %s, %s, %s)",
        (company_id, action, entity, str(eid)),
    )


def _ensure_user(cur: psycopg.Cursor, email: str, full_name: str) -> tuple[UUID, str | None]:
    """Return (user_id, temporary password if the account was created)."""
    cur.execute("SELECT id FROM users WHERE email = %s", (email.lower(),))
    row = cur.fetchone()
    if row:
        return row[0], None
    password = generate_temporary_password()
    user_id = uuid4()
    cur.execute(
        "INSERT INTO users (id, email, full_name, password_hash, must_change_password) "
        "VALUES (%s, %s, %s, %s, true)",
        (user_id, email.lower(), full_name, hash_password(password)),
    )
    return user_id, password


def create_company(
    name: str, admin_email: str, admin_name: str, siret: str | None, demo: bool = False
) -> UUID:
    with psycopg.connect(_admin_dsn()) as conn, conn.cursor() as cur:
        company_id = uuid4()
        cur.execute(
            "INSERT INTO companies (id, name, siret, is_demo) VALUES (%s, %s, %s, %s)",
            (company_id, name.strip(), siret, demo),
        )
        _audit(cur, company_id, "company.created", "company", company_id)
        user_id, password = _ensure_user(cur, admin_email, admin_name)
        cur.execute(
            "INSERT INTO memberships (company_id, user_id, role) VALUES (%s, %s, 'admin')",
            (company_id, user_id),
        )
        _audit(cur, company_id, "membership.created", "user", user_id)
    print(f"Company created: {name} ({company_id})")
    print(f"Administrator: {admin_email}")
    if password:
        print(f"Temporary password (shown once, must be changed at first login): {password}")
    else:
        print("This e-mail already had an account: it keeps its current password.")
    return company_id


def seed_demo(reset_passwords: bool) -> None:
    if os.environ.get("NEWTON_ENV") == "production":
        sys.exit("Refusing to create demo data in production.")
    with psycopg.connect(_admin_dsn()) as conn, conn.cursor() as cur:
        for company_name, slug in DEMO_COMPANIES:
            cur.execute("SELECT id FROM companies WHERE name = %s AND is_demo", (company_name,))
            row = cur.fetchone()
            if row:
                company_id = row[0]
                print(f"[demo] {company_name}: already present")
            else:
                company_id = uuid4()
                cur.execute(
                    "INSERT INTO companies (id, name, is_demo) VALUES (%s, %s, true)",
                    (company_id, company_name),
                )
                _audit(cur, company_id, "company.created", "company", company_id)
                print(f"[demo] {company_name}: created")
            for role, label in DEMO_ROLES:
                email = f"{role}.{slug}@example.com"
                user_id, password = _ensure_user(cur, email, f"{label} {slug.capitalize()}")
                cur.execute(
                    "INSERT INTO memberships (company_id, user_id, role) VALUES (%s, %s, %s) "
                    "ON CONFLICT (company_id, user_id) DO NOTHING",
                    (company_id, user_id, role),
                )
                if password is None and reset_passwords:
                    password = generate_temporary_password()
                    cur.execute(
                        "UPDATE users SET password_hash = %s, must_change_password = true "
                        "WHERE id = %s",
                        (hash_password(password), user_id),
                    )
                if password:
                    print(f"  {email:<28} {role:<10} temporary password: {password}")
                else:
                    print(f"  {email:<28} {role:<10} (password unchanged)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="newton.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap-db")
    sub.add_parser("migrate")
    cc = sub.add_parser("create-company")
    cc.add_argument("--name", required=True)
    cc.add_argument("--admin-email", required=True)
    cc.add_argument("--admin-name", required=True)
    cc.add_argument("--siret")
    sd = sub.add_parser("seed-demo")
    sd.add_argument("--reset-passwords", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "bootstrap-db":
        bootstrap_db()
    elif args.cmd == "migrate":
        migrate()
    elif args.cmd == "create-company":
        create_company(args.name, args.admin_email, args.admin_name, args.siret)
    elif args.cmd == "seed-demo":
        seed_demo(args.reset_passwords)


if __name__ == "__main__":
    main()
