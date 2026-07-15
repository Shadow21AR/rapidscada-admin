"""Tests for rapidscada_admin.validation — file and schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from rapidscada_admin.basetable import TYPE_INTEGER, BaseTable, FieldDef
from rapidscada_admin.validation import (
    ValidationResult,
    validate_file,
    validate_user_file,
    validate_user_table,
)


class TestValidationResult:
    """ValidationResult dataclass tests."""

    def test_ok_when_no_errors(self) -> None:
        r = ValidationResult()
        assert r.ok is True

    def test_not_ok_with_errors(self) -> None:
        r = ValidationResult(errors=["something is wrong"])
        assert r.ok is False

    def test_report_stderr(self, capsys: pytest.CaptureFixture) -> None:
        r = ValidationResult(errors=["err1"])
        r.report()
        captured = capsys.readouterr()
        assert "ERROR: err1" in captured.err

    def test_report_ok_message(self, capsys: pytest.CaptureFixture) -> None:
        r = ValidationResult()
        r.report()
        captured = capsys.readouterr()
        assert "Validation passed" in captured.err


class TestValidateFile:
    """File-level validation tests."""

    def test_valid_file(self, user_dat_path: Path) -> None:
        result = validate_file(user_dat_path)
        assert result.ok

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        result = validate_file(tmp_path / "nope.dat")
        assert not result.ok
        assert any("does not exist" in e for e in result.errors)

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.dat"
        path.write_bytes(b"")
        result = validate_file(path)
        assert not result.ok
        assert any("empty" in e.lower() for e in result.errors)

    def test_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.dat"
        path.write_bytes(b"\x00" * 50)
        result = validate_file(path)
        assert not result.ok


class TestValidateUserTable:
    """Schema-level validation tests."""

    def test_valid_table(self, sample_table: BaseTable) -> None:
        result = validate_user_table(sample_table)
        assert result.ok

    def test_duplicate_user_ids(self, user_field_defs: list[FieldDef]) -> None:
        rows = [
            {"UserID": 1, "Enabled": True, "Name": "a", "Password": "", "RoleID": 0},
            {"UserID": 1, "Enabled": True, "Name": "b", "Password": "", "RoleID": 0},
        ]
        table = BaseTable(user_field_defs, rows)
        result = validate_user_table(table)
        assert not result.ok
        assert any("Duplicate UserID" in e for e in result.errors)

    def test_duplicate_names(self, user_field_defs: list[FieldDef]) -> None:
        rows = [
            {"UserID": 1, "Enabled": True, "Name": "admin", "Password": "", "RoleID": 0},
            {"UserID": 2, "Enabled": True, "Name": "admin", "Password": "", "RoleID": 0},
        ]
        table = BaseTable(user_field_defs, rows)
        result = validate_user_table(table)
        assert not result.ok
        assert any("Duplicate username" in e for e in result.errors)

    def test_missing_required_field(self) -> None:
        defs = [FieldDef("UserID", TYPE_INTEGER, False)]
        table = BaseTable(defs, [{"UserID": 1}])
        result = validate_user_table(table)
        assert not result.ok
        assert any("Missing required fields" in e for e in result.errors)

    def test_none_userid(self, user_field_defs: list[FieldDef]) -> None:
        rows = [
            {"UserID": None, "Enabled": True, "Name": "x", "Password": "", "RoleID": 0},
        ]
        table = BaseTable(user_field_defs, rows)
        result = validate_user_table(table)
        assert not result.ok
        assert any("UserID is None" in e for e in result.errors)

    def test_none_name(self, user_field_defs: list[FieldDef]) -> None:
        rows = [
            {"UserID": 1, "Enabled": True, "Name": None, "Password": "", "RoleID": 0},
        ]
        table = BaseTable(user_field_defs, rows)
        result = validate_user_table(table)
        assert not result.ok
        assert any("Name is None" in e for e in result.errors)

    def test_warnings_for_optional_none(self, user_field_defs: list[FieldDef]) -> None:
        rows = [
            {"UserID": 1, "Enabled": None, "Name": "x", "Password": None, "RoleID": None},
        ]
        table = BaseTable(user_field_defs, rows)
        result = validate_user_table(table)
        assert len(result.warnings) == 3  # Enabled, Password, RoleID


class TestValidateUserFile:
    """End-to-end user file validation tests."""

    def test_valid_user_dat(self, user_dat_path: Path) -> None:
        result = validate_user_file(user_dat_path)
        assert result.ok

    def test_nonexistent(self, tmp_path: Path) -> None:
        result = validate_user_file(tmp_path / "nope.dat")
        assert not result.ok

    def test_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.dat"
        path.write_bytes(b"corrupt")
        result = validate_user_file(path)
        assert not result.ok
