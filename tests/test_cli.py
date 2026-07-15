"""Tests for rapidscada_admin.cli — end-to-end CLI tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rapidscada_admin.basetable import TYPE_BOOLEAN, TYPE_INTEGER, TYPE_STRING, BaseTable, FieldDef
from rapidscada_admin.crypto import get_password_hash


@pytest.fixture()
def cli_dat_path(tmp_path: Path) -> Path:
    """Create a test .dat file and return its path."""
    defs = [
        FieldDef("UserID", TYPE_INTEGER, False),
        FieldDef("Enabled", TYPE_BOOLEAN, False),
        FieldDef("Name", TYPE_STRING, False),
        FieldDef("Password", TYPE_STRING, False),
        FieldDef("RoleID", TYPE_INTEGER, False),
        FieldDef("Description", TYPE_STRING, True),
    ]
    rows = [
        {
            "UserID": 1,
            "Enabled": True,
            "Name": "admin",
            "Password": get_password_hash(1, "admin123"),
            "RoleID": 1,
            "Description": "Administrator",
        },
        {
            "UserID": 2,
            "Enabled": True,
            "Name": "operator",
            "Password": get_password_hash(2, "op123"),
            "RoleID": 2,
            "Description": "Operator",
        },
    ]
    table = BaseTable(defs, rows)
    path = tmp_path / "user.dat"
    table.save(path)
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "rapidscada_admin", *args],
        capture_output=True,
        text=True,
        cwd="/tmp",
    )


class TestCliVersion:
    """Version flag tests."""

    def test_version(self) -> None:
        result = run_cli("--version")
        assert result.returncode == 0
        assert "rapidscada-admin" in result.stdout


class TestCliHash:
    """Hash command tests."""

    def test_hash_output(self) -> None:
        result = run_cli("hash", "--password", "test")
        assert result.returncode == 0
        assert len(result.stdout.strip()) == 32

    def test_hash_with_user_id(self) -> None:
        result = run_cli("hash", "--password", "scada", "--user-id", "11")
        assert result.returncode == 0
        expected = get_password_hash(11, "scada")
        assert result.stdout.strip() == expected


class TestCliUsersList:
    """users list command tests."""

    def test_list_users(self, cli_dat_path: Path) -> None:
        result = run_cli("users", str(cli_dat_path), "list")
        assert result.returncode == 0
        assert "admin" in result.stdout
        assert "operator" in result.stdout
        assert "Total: 2 user(s)" in result.stdout


class TestCliUsersShow:
    """users show command tests."""

    def test_show_user(self, cli_dat_path: Path) -> None:
        result = run_cli("users", str(cli_dat_path), "show", "--user", "admin")
        assert result.returncode == 0
        assert "UserID: 1" in result.stdout
        assert "Name: admin" in result.stdout

    def test_show_nonexistent(self, cli_dat_path: Path) -> None:
        result = run_cli("users", str(cli_dat_path), "show", "--user", "nobody")
        assert result.returncode != 0


class TestCliUsersAdd:
    """users add command tests."""

    def test_add_user(self, cli_dat_path: Path) -> None:
        result = run_cli(
            "users",
            str(cli_dat_path),
            "add",
            "--name",
            "newuser",
            "--password",
            "pass123",
        )
        assert result.returncode == 0
        result2 = run_cli("users", str(cli_dat_path), "list")
        assert "newuser" in result2.stdout
        assert "Total: 3 user(s)" in result2.stdout

    def test_add_duplicate_exits(self, cli_dat_path: Path) -> None:
        result = run_cli(
            "users",
            str(cli_dat_path),
            "add",
            "--name",
            "admin",
            "--password",
            "pass",
        )
        assert result.returncode != 0


class TestCliUsersDelete:
    """users delete command tests."""

    def test_delete_user(self, cli_dat_path: Path) -> None:
        result = run_cli("users", str(cli_dat_path), "delete", "--user", "operator")
        assert result.returncode == 0
        result2 = run_cli("users", str(cli_dat_path), "list")
        assert "operator" not in result2.stdout
        assert "Total: 1 user(s)" in result2.stdout


class TestCliUsersPasswd:
    """users passwd command tests."""

    def test_change_password(self, cli_dat_path: Path) -> None:
        result = run_cli(
            "users",
            str(cli_dat_path),
            "passwd",
            "--user",
            "admin",
            "--password",
            "NewPass456!",
        )
        assert result.returncode == 0


class TestCliUsersEnableDisable:
    """users enable/disable command tests."""

    def test_disable_then_enable(self, cli_dat_path: Path) -> None:
        f = str(cli_dat_path)
        r1 = run_cli("users", f, "disable", "--user", "admin")
        assert r1.returncode == 0
        r2 = run_cli("users", f, "show", "--user", "admin")
        assert "Enabled: False" in r2.stdout

        r3 = run_cli("users", f, "enable", "--user", "admin")
        assert r3.returncode == 0
        r4 = run_cli("users", f, "show", "--user", "admin")
        assert "Enabled: True" in r4.stdout


class TestCliUsersExportImport:
    """users export/import command tests."""

    def test_export_json(self, cli_dat_path: Path) -> None:
        result = run_cli("users", str(cli_dat_path), "export")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2


class TestCliVerify:
    """verify command tests."""

    def test_verify_valid(self, cli_dat_path: Path) -> None:
        result = run_cli("verify", str(cli_dat_path))
        assert result.returncode == 0

    def test_verify_corrupt(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.dat"
        path.write_bytes(b"garbage")
        result = run_cli("verify", str(path))
        assert result.returncode != 0
