"""Core: companies, users, memberships, sessions, audit log, with Row-Level Security.

Revision ID: 0001
Revises:
Create Date: 2026-11-02
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# The runtime role is `newton_app`. Its LOGIN password is set by `newton.cli bootstrap-db`.
UPGRADE_SQL = r"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'newton_app') THEN
    CREATE ROLE newton_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;

DO $$ BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO newton_app', current_database());
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO newton_app;

-- Tenant context helpers (values set per transaction by the API).
CREATE FUNCTION newton_current_company() RETURNS uuid
  LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.company_id', true), '')::uuid $$;
CREATE FUNCTION newton_current_user() RETURNS uuid
  LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION newton_touch_updated_at() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END $$;

-- ---------------------------------------------------------------- companies
CREATE TABLE companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  siret varchar(14) CHECK (siret ~ '^[0-9]{14}$'),
  is_demo boolean NOT NULL DEFAULT false,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER companies_touch BEFORE UPDATE ON companies
  FOR EACH ROW EXECUTE FUNCTION newton_touch_updated_at();

-- ---------------------------------------------------------------- users (global identities)
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE CHECK (email = lower(email)),
  password_hash text NOT NULL,
  full_name text NOT NULL CHECK (length(trim(full_name)) > 0),
  is_active boolean NOT NULL DEFAULT true,
  must_change_password boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER users_touch BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION newton_touch_updated_at();

-- ---------------------------------------------------------------- memberships
CREATE TABLE memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id),
  user_id uuid NOT NULL REFERENCES users(id),
  role text NOT NULL CHECK (role IN ('admin', 'estimator', 'viewer')),
  is_active boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, user_id)
);
CREATE INDEX memberships_user_idx ON memberships(user_id);
CREATE TRIGGER memberships_touch BEFORE UPDATE ON memberships
  FOR EACH ROW EXECUTE FUNCTION newton_touch_updated_at();

-- ---------------------------------------------------------------- sessions
CREATE TABLE sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  company_id uuid NOT NULL REFERENCES companies(id),
  refresh_token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  revoked_reason text,
  user_agent text,
  ip text,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user_idx ON sessions(user_id);
CREATE INDEX sessions_company_idx ON sessions(company_id);

-- ---------------------------------------------------------------- audit log (append-only)
CREATE TABLE audit_log (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES companies(id),
  actor_type text NOT NULL CHECK (actor_type IN ('user', 'ai', 'system')),
  actor_user_id uuid REFERENCES users(id),
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id text,
  before jsonb,
  after jsonb,
  ip text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_company_created_idx ON audit_log(company_id, created_at DESC);

-- Blocks UPDATE and DELETE for everyone, including the owner role.
CREATE FUNCTION newton_audit_immutable() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit_log is append-only'; END $$;
CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION newton_audit_immutable();

-- ---------------------------------------------------------------- Row-Level Security
ALTER TABLE companies   ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies   FORCE ROW LEVEL SECURITY;
ALTER TABLE users       ENABLE ROW LEVEL SECURITY;
ALTER TABLE users       FORCE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions    FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log   ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log   FORCE ROW LEVEL SECURITY;

-- memberships: rows of the current company, plus the current user's own memberships
CREATE POLICY memberships_select ON memberships FOR SELECT TO newton_app
  USING (company_id = newton_current_company() OR user_id = newton_current_user());
CREATE POLICY memberships_insert ON memberships FOR INSERT TO newton_app
  WITH CHECK (company_id = newton_current_company());
CREATE POLICY memberships_update ON memberships FOR UPDATE TO newton_app
  USING (company_id = newton_current_company())
  WITH CHECK (company_id = newton_current_company());

-- companies: the current company, plus companies the current user belongs to (for switching)
CREATE POLICY companies_select ON companies FOR SELECT TO newton_app
  USING (id = newton_current_company()
         OR id IN (SELECT m.company_id FROM memberships m
                   WHERE m.user_id = newton_current_user() AND m.is_active));
CREATE POLICY companies_update ON companies FOR UPDATE TO newton_app
  USING (id = newton_current_company()) WITH CHECK (id = newton_current_company());

-- users: yourself, or members of the current company
CREATE POLICY users_select ON users FOR SELECT TO newton_app
  USING (id = newton_current_user()
         OR EXISTS (SELECT 1 FROM memberships m
                    WHERE m.user_id = users.id AND m.company_id = newton_current_company()));
-- Inserting a user requires a company context; it only becomes visible once a membership exists.
CREATE POLICY users_insert ON users FOR INSERT TO newton_app
  WITH CHECK (newton_current_company() IS NOT NULL);
-- Only the user can update their own row (e.g. password change).
CREATE POLICY users_update ON users FOR UPDATE TO newton_app
  USING (id = newton_current_user()) WITH CHECK (id = newton_current_user());

-- sessions: your own, or sessions opened in the current company (admin revocation)
CREATE POLICY sessions_select ON sessions FOR SELECT TO newton_app
  USING (user_id = newton_current_user() OR company_id = newton_current_company());
CREATE POLICY sessions_insert ON sessions FOR INSERT TO newton_app
  WITH CHECK (user_id = newton_current_user() AND company_id = newton_current_company());
CREATE POLICY sessions_update ON sessions FOR UPDATE TO newton_app
  USING (user_id = newton_current_user() OR company_id = newton_current_company())
  WITH CHECK (user_id = newton_current_user() OR company_id = newton_current_company());

CREATE POLICY audit_select ON audit_log FOR SELECT TO newton_app
  USING (company_id = newton_current_company());
CREATE POLICY audit_insert ON audit_log FOR INSERT TO newton_app
  WITH CHECK (company_id = newton_current_company());

-- ---------------------------------------------------------------- privileges
GRANT SELECT, UPDATE ON companies TO newton_app;
GRANT SELECT, INSERT, UPDATE ON users TO newton_app;
GRANT SELECT, INSERT, UPDATE ON memberships TO newton_app;
GRANT SELECT, INSERT, UPDATE ON sessions TO newton_app;
GRANT SELECT, INSERT ON audit_log TO newton_app;

-- ---------------------------------------------------------------- narrow pre-auth lookups
-- SECURITY DEFINER functions run as the owner (bypassing RLS) and expose only what is needed.
CREATE FUNCTION newton_auth_lookup(p_email text)
  RETURNS TABLE (id uuid, password_hash text, is_active boolean)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT u.id, u.password_hash, u.is_active FROM users u WHERE u.email = lower(p_email)
  $$;

CREATE FUNCTION newton_find_user_id(p_email text) RETURNS uuid
  LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  BEGIN
    IF newton_current_company() IS NULL THEN
      RAISE EXCEPTION 'company context required';
    END IF;
    RETURN (SELECT u.id FROM users u WHERE u.email = lower(p_email));
  END $$;

CREATE FUNCTION newton_session_lookup(p_session_id uuid)
  RETURNS TABLE (user_id uuid, company_id uuid, refresh_token_hash text,
                 expires_at timestamptz, revoked_at timestamptz)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT s.user_id, s.company_id, s.refresh_token_hash, s.expires_at, s.revoked_at
    FROM sessions s WHERE s.id = p_session_id
  $$;

REVOKE ALL ON FUNCTION newton_auth_lookup(text), newton_find_user_id(text),
  newton_session_lookup(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION newton_auth_lookup(text), newton_find_user_id(text),
  newton_session_lookup(uuid) TO newton_app;
"""

DOWNGRADE_SQL = r"""
DROP FUNCTION IF EXISTS newton_session_lookup(uuid);
DROP FUNCTION IF EXISTS newton_find_user_id(text);
DROP FUNCTION IF EXISTS newton_auth_lookup(text);
DROP TABLE IF EXISTS audit_log;
DROP FUNCTION IF EXISTS newton_audit_immutable();
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS memberships;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS companies;
DROP FUNCTION IF EXISTS newton_touch_updated_at();
DROP FUNCTION IF EXISTS newton_current_user();
DROP FUNCTION IF EXISTS newton_current_company();
REVOKE USAGE ON SCHEMA public FROM newton_app;
"""


def _run_script(sql: str) -> None:
    # Sent straight to psycopg without parameters, so multi-statement scripts and
    # literal '%' / ':' characters are passed to PostgreSQL untouched.
    op.get_bind().connection.driver_connection.execute(sql)


def upgrade() -> None:
    _run_script(UPGRADE_SQL)


def downgrade() -> None:
    _run_script(DOWNGRADE_SQL)
