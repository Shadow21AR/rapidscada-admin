"""Tests for rapidscada_admin.users — CRUD operations."""

from __future__ import annotations

import pytest

from rapidscada_admin.basetable import BaseTable
from rapidscada_admin.crypto import get_password_hash
from rapidscada_admin.users import (
    add_user,
    change_password,
    delete_user,
    disable_user,
    enable_user,
    export_users,
    import_users,
    list_users,
    rename_user,
    show_user,
)


class TestAddUser:
    """User creation tests."""

    def test_add_user_basic(self, sample_table: BaseTable) -> None:
        row = add_user(sample_table, "newuser", "pass123")
        assert row["Name"] == "newuser"
        assert row["UserID"] == 4
        assert row["Enabled"] is True
        assert row["RoleID"] == 0
        assert len(sample_table.rows) == 4

    def test_add_user_with_role(self, sample_table: BaseTable) -> None:
        row = add_user(sample_table, "mgr", "pass", role=5)
        assert row["RoleID"] == 5

    def test_add_user_disabled(self, sample_table: BaseTable) -> None:
        row = add_user(sample_table, "locked", "pass", enabled=False)
        assert row["Enabled"] is False

    def test_add_user_duplicate_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            add_user(sample_table, "admin", "pass")

    def test_add_user_password_is_hashed(self, sample_table: BaseTable) -> None:
        row = add_user(sample_table, "hashed", "mypassword")
        expected = get_password_hash(row["UserID"], "mypassword")
        assert row["Password"] == expected

    def test_add_user_empty_table(self, empty_table: BaseTable) -> None:
        row = add_user(empty_table, "first", "pass")
        assert row["UserID"] == 1
        assert len(empty_table.rows) == 1


class TestDeleteUser:
    """User deletion tests."""

    def test_delete_existing(self, sample_table: BaseTable) -> None:
        delete_user(sample_table, "guest")
        assert len(sample_table.rows) == 2
        assert sample_table.find_by_name("guest") is None

    def test_delete_nonexistent_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            delete_user(sample_table, "nobody")


class TestRenameUser:
    """User rename tests."""

    def test_rename_basic(self, sample_table: BaseTable) -> None:
        rename_user(sample_table, "guest", "visitor")
        assert sample_table.find_by_name("visitor") is not None
        assert sample_table.find_by_name("guest") is None

    def test_rename_nonexistent_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            rename_user(sample_table, "nobody", "someone")

    def test_rename_collision_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            rename_user(sample_table, "guest", "admin")


class TestChangePassword:
    """Password change tests."""

    def test_change_password_updates_hash(self, sample_table: BaseTable) -> None:
        change_password(sample_table, "admin", "newsecret")
        row = sample_table.find_by_name("admin")
        expected = get_password_hash(1, "newsecret")
        assert row["Password"] == expected

    def test_change_password_nonexistent_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            change_password(sample_table, "nobody", "pass")


class TestEnableDisable:
    """Enable/disable tests."""

    def test_enable(self, sample_table: BaseTable) -> None:
        enable_user(sample_table, "guest")
        row = sample_table.find_by_name("guest")
        assert row["Enabled"] is True

    def test_disable(self, sample_table: BaseTable) -> None:
        disable_user(sample_table, "admin")
        row = sample_table.find_by_name("admin")
        assert row["Enabled"] is False

    def test_enable_nonexistent_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            enable_user(sample_table, "nobody")

    def test_disable_nonexistent_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            disable_user(sample_table, "nobody")


class TestExportImport:
    """Export/import roundtrip tests."""

    def test_export_returns_list(self, sample_table: BaseTable) -> None:
        data = export_users(sample_table)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_export_preserves_fields(self, sample_table: BaseTable) -> None:
        data = export_users(sample_table)
        for entry in data:
            assert "UserID" in entry
            assert "Name" in entry
            assert "Password" in entry

    def test_import_roundtrip(self, sample_table: BaseTable) -> None:
        data = export_users(sample_table)
        # Create a fresh table, import into it
        new_table = BaseTable(sample_table.field_defs, [])
        import_users(new_table, data)
        assert len(new_table.rows) == 3

    def test_import_duplicate_name_exits(self, sample_table: BaseTable) -> None:
        data = [{"Name": "admin", "UserID": 10}]
        with pytest.raises(SystemExit):
            import_users(sample_table, data)

    def test_import_missing_name_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            import_users(sample_table, [{"UserID": 10}])


class TestListUsers:
    """list_users output tests."""

    def test_list_users_output(
        self, sample_table: BaseTable, capsys: pytest.CaptureFixture
    ) -> None:
        list_users(sample_table)
        captured = capsys.readouterr()
        assert "admin" in captured.out
        assert "operator" in captured.out
        assert "guest" in captured.out
        assert "Total: 3 user(s)" in captured.out

    def test_list_users_empty(self, empty_table: BaseTable, capsys: pytest.CaptureFixture) -> None:
        list_users(empty_table)
        captured = capsys.readouterr()
        assert "No users found" in captured.out


class TestShowUser:
    """show_user output tests."""

    def test_show_existing(self, sample_table: BaseTable, capsys: pytest.CaptureFixture) -> None:
        show_user(sample_table, "admin")
        captured = capsys.readouterr()
        assert "UserID: 1" in captured.out
        assert "Name: admin" in captured.out
        assert "Password: " in captured.out

    def test_show_nonexistent_exits(self, sample_table: BaseTable) -> None:
        with pytest.raises(SystemExit):
            show_user(sample_table, "nobody")
