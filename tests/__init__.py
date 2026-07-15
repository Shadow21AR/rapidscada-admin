"""Shared fixtures for rapidscada_admin tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from rapidscada_admin.basetable import (
    TYPE_BOOLEAN,
    TYPE_INTEGER,
    TYPE_STRING,
    BaseTable,
    FieldDef,
)
from rapidscada_admin.crypto import get_password_hash


@pytest.fixture()
def user_field_defs() -> list[FieldDef]:
    """Standard field definitions for a user.dat table."""
    return [
        FieldDef("UserID", TYPE_INTEGER, False),
        FieldDef("Enabled", TYPE_BOOLEAN, False),
        FieldDef("Name", TYPE_STRING, False),
        FieldDef("Password", TYPE_STRING, False),
        FieldDef("RoleID", TYPE_INTEGER, False),
        FieldDef("Description", TYPE_STRING, True),
    ]


@pytest.fixture()
def sample_user_rows() -> list[dict]:
    """Three sample user rows with proper password hashes."""
    return [
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
            "Description": "Operator account",
        },
        {
            "UserID": 3,
            "Enabled": False,
            "Name": "guest",
            "Password": "",
            "RoleID": 3,
            "Description": "Guest user",
        },
    ]


@pytest.fixture()
def sample_table(
    user_field_defs: list[FieldDef],
    sample_user_rows: list[dict],
) -> BaseTable:
    """An in-memory BaseTable with three users."""
    return BaseTable(user_field_defs, sample_user_rows)


@pytest.fixture()
def user_dat_path(
    tmp_path: Path,
    user_field_defs: list[FieldDef],
    sample_user_rows: list[dict],
) -> Path:
    """Path to a temporary user.dat file written to disk."""
    table = BaseTable(user_field_defs, sample_user_rows)
    path = tmp_path / "user.dat"
    table.save(path)
    return path


@pytest.fixture()
def empty_table(user_field_defs: list[FieldDef]) -> BaseTable:
    """An empty BaseTable (no rows)."""
    return BaseTable(user_field_defs, [])
