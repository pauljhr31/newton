"""Administration commands: company creation and clearly separated demo data."""

import pytest

from newton import cli
from tests.conftest import login


def test_create_company_with_admin(admin_conn, client_factory, capsys):
    cid = cli.create_company(
        "Elec Réelle", "Patron@Real.example.com", "Le Patron", "12345678901234"
    )
    out = capsys.readouterr().out
    temp = next(line.split(": ", 1)[1] for line in out.splitlines() if "Temporary password" in line)
    row = admin_conn.execute(
        "SELECT name, is_demo, siret FROM companies WHERE id = %s", (cid,)
    ).fetchone()
    assert row == ("Elec Réelle", False, "12345678901234")
    c = client_factory()
    me = login(c, "patron@real.example.com", temp).json()
    assert me["role"] == "admin" and me["must_change_password"] is True
    actions = {
        r[0]
        for r in admin_conn.execute("SELECT action FROM audit_log WHERE company_id = %s", (cid,))
    }
    assert actions == {"company.created", "membership.created", "auth.login"}


def test_seed_demo_is_flagged_and_idempotent(admin_conn, capsys):
    cli.seed_demo(reset_passwords=False)
    cli.seed_demo(reset_passwords=False)
    out = capsys.readouterr().out
    assert "already present" in out
    rows = admin_conn.execute("SELECT name, is_demo FROM companies ORDER BY name").fetchall()
    assert len(rows) == 2 and all(is_demo for _, is_demo in rows)
    assert all(name.startswith("DÉMO") for name, _ in rows)
    assert admin_conn.execute("SELECT count(*) FROM users").fetchone()[0] == 6
    assert admin_conn.execute("SELECT count(*) FROM memberships").fetchone()[0] == 6


def test_demo_users_can_log_in_and_see_demo_flag(client_factory, capsys):
    cli.seed_demo(reset_passwords=False)
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if "admin.alpha@example.com" in ln)
    password = line.rsplit(": ", 1)[1]
    me = login(client_factory(), "admin.alpha@example.com", password).json()
    assert me["company"]["is_demo"] is True


def test_seed_demo_refused_in_production(monkeypatch):
    monkeypatch.setenv("NEWTON_ENV", "production")
    with pytest.raises(SystemExit):
        cli.seed_demo(reset_passwords=False)
