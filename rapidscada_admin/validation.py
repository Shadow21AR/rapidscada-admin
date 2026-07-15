"""Validation utilities for BaseDAT table integrity and user-table schema."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidscada_admin.basetable import BaseTable, FormatError

REQUIRED_USER_FIELDS: frozenset[str] = frozenset(
    {"UserID", "Enabled", "Name", "Password", "RoleID"}
)
"""Fields that must be present for a valid user.dat table."""


@dataclass
class ValidationResult:
    """Accumulates validation errors and warnings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when there are no errors."""
        return len(self.errors) == 0

    def report(self, dest: Any = None) -> None:
        """Print the result to *dest* (defaults to stderr).

        Args:
            dest: A file-like object; defaults to ``sys.stderr``.
        """
        if dest is None:
            dest = sys.stderr
        for w in self.warnings:
            print(f"WARNING: {w}", file=dest)
        for e in self.errors:
            print(f"ERROR: {e}", file=dest)
        if self.ok:
            print("Validation passed.", file=dest)
        else:
            print(f"Validation failed with {len(self.errors)} error(s).", file=dest)


def validate_file(path: Path) -> ValidationResult:
    """Perform a basic integrity check on a BaseDAT file.

    Checks:
        - File exists and is readable.
        - File can be parsed (CRC checks, header validation).
        - File is not empty.

    Args:
        path: Path to the .dat file.

    Returns:
        A :class:`ValidationResult` with any issues found.
    """
    result = ValidationResult()
    if not path.exists():
        result.errors.append(f"File does not exist: {path}")
        return result
    if not path.is_file():
        result.errors.append(f"Path is not a regular file: {path}")
        return result
    if path.stat().st_size == 0:
        result.errors.append(f"File is empty: {path}")
        return result
    try:
        BaseTable.load(path)
    except FormatError as exc:
        result.errors.append(f"Format error: {exc}")
    except Exception as exc:
        result.errors.append(f"Unexpected error reading file: {exc}")
    return result


def validate_user_table(table: BaseTable) -> ValidationResult:
    """Validate a parsed user table for correctness.

    Checks:
        - Required fields are present.
        - No duplicate UserIDs.
        - No duplicate usernames (Name field).
        - No missing required field values in rows.

    Args:
        table: A loaded :class:`BaseTable`.

    Returns:
        A :class:`ValidationResult` with any issues found.
    """
    result = ValidationResult()
    field_names = set(table.field_names)

    missing = REQUIRED_USER_FIELDS - field_names
    if missing:
        result.errors.append(f"Missing required fields: {sorted(missing)}")
        return result

    seen_ids: dict[int, int] = {}
    seen_names: dict[str, int] = {}

    for idx, row in enumerate(table.rows):
        uid = row.get("UserID")
        if uid is None:
            result.errors.append(f"Row {idx}: UserID is None")
        elif uid in seen_ids:
            result.errors.append(f"Duplicate UserID {uid} at rows {seen_ids[uid]} and {idx}")
        else:
            seen_ids[uid] = idx

        name = row.get("Name")
        if name is None:
            result.errors.append(f"Row {idx}: Name is None")
        elif name in seen_names:
            result.errors.append(
                f"Duplicate username {name!r} at rows {seen_names[name]} and {idx}"
            )
        else:
            seen_names[name] = idx

        for req in ("Enabled", "Password", "RoleID"):
            if row.get(req) is None:
                result.warnings.append(f"Row {idx} ({name!r}): {req} is None")

    return result


def validate_user_file(path: Path) -> ValidationResult:
    """Validate a user.dat file end-to-end: parse then check schema.

    Args:
        path: Path to user.dat.

    Returns:
        A :class:`ValidationResult` combining file-level and schema-level checks.
    """
    file_result = validate_file(path)
    if not file_result.ok:
        return file_result

    table = BaseTable.load(path)
    return validate_user_table(table)
