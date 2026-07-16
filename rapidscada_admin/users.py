"""High-level user administration operations on BaseDAT user tables.

All mutating functions follow the safety protocol:

1. Verify schema
2. Create backup
3. Write temporary file
4. Re-read temporary file
5. Validate
6. Atomically replace original
7. Print backup location
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, TextIO

from rapidscada_admin.backup import create_backup
from rapidscada_admin.basetable import BaseTable
from rapidscada_admin.crypto import get_password_hash
from rapidscada_admin.validation import REQUIRED_USER_FIELDS, validate_user_table


def _die(msg: str) -> None:
    """Print *msg* to stderr and exit with code 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def _require_user_table(table: BaseTable) -> None:
    """Abort if *table* does not contain the required user fields."""
    missing = REQUIRED_USER_FIELDS - set(table.field_names)
    if missing:
        _die(f"Schema check failed — missing required fields: {sorted(missing)}")


def _resolve_user(table: BaseTable, name: str) -> dict[str, Any]:
    """Resolve a username, trying exact then case-insensitive match.

    Exits with an error if no unique match is found.

    Args:
        table: The loaded user table.
        name: The username to look up.

    Returns:
        The matching row dict.
    """
    target = table.find_by_name(name)
    if target is not None:
        return target

    loose = table.find_by_name_loose(name)
    if len(loose) == 1:
        print(
            f"Note: matched {loose[0].get('Name')!r} case-insensitively (you passed {name!r}).",
            file=sys.stderr,
        )
        return loose[0]

    if len(loose) > 1:
        _die(
            f"Multiple users match {name!r} case-insensitively: "
            f"{[r.get('Name') for r in loose]}. Re-run with the exact name."
        )

    available = [row.get("Name") for row in table.rows]
    _die(f"User {name!r} not found.\nAvailable usernames: {available!r}")


def _safe_write(table: BaseTable, path: Path) -> None:
    """Write *table* to *path* using the safety protocol.

    Creates a backup, writes to a temp file, re-reads, validates,
    then atomically replaces.

    Args:
        table: The table to save.
        path: Destination file path.
    """
    _require_user_table(table)

    orig_mode = os.stat(path).st_mode

    backup_path = create_backup(path)
    print(f"Backup written to: {backup_path}", file=sys.stderr)

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.close(fd)
        tmp = Path(tmp_path)
        table.save(tmp)

        reloaded = BaseTable.load(tmp)
        validation = validate_user_table(reloaded)
        if not validation.ok:
            tmp.unlink(missing_ok=True)
            validation.report()
            _die("Aborted — re-read validation failed after write.")

        os.replace(tmp, path)
        os.chmod(path, orig_mode)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def list_users(table: BaseTable, dest: TextIO | None = None) -> None:
    """Print a formatted table of all users to *dest*.

    Args:
        table: The loaded user table.
        dest: Output stream (defaults to stdout).
    """
    if dest is None:
        dest = sys.stdout

    if not table.rows:
        print("No users found.", file=dest)
        return

    print(
        f"{'UserID':<8} {'Enabled':<10} {'Name':<24} {'RoleID':<8} {'Description'}",
        file=dest,
    )
    print("-" * 80, file=dest)
    for row in table.rows:
        enabled = "Yes" if row.get("Enabled") else "No"
        desc = row.get("Description", "") or ""
        print(
            f"{row.get('UserID', ''):<8} {enabled:<10} "
            f"{row.get('Name', ''):<24} {row.get('RoleID', ''):<8} {desc}",
            file=dest,
        )
    print(f"\nTotal: {len(table.rows)} user(s)", file=dest)


def show_user(table: BaseTable, name: str) -> None:
    """Display details for a single user.

    Args:
        table: The loaded user table.
        name: The username to display.
    """
    row = _resolve_user(table, name)
    for key, value in row.items():
        print(f"  {key}: {value}")


def add_user(
    table: BaseTable,
    name: str,
    password: str,
    role: int = 0,
    enabled: bool = True,
    description: str = "",
) -> dict[str, Any]:
    """Add a new user to *table*.

    Args:
        table: The loaded user table (modified in-place).
        name: Username for the new account.
        password: Plaintext password.
        role: RoleID (default 0).
        enabled: Whether the account is enabled (default True).
        description: Optional description.

    Returns:
        The newly created row dict.

    Raises:
        SystemExit: If the username already exists.
    """
    if table.find_by_name(name) is not None:
        _die(f"User {name!r} already exists.")

    user_id = table.next_user_id()
    row: dict[str, Any] = {
        "UserID": user_id,
        "Enabled": enabled,
        "Name": name,
        "Password": get_password_hash(user_id, password),
        "RoleID": role,
        "Description": description,
    }
    table.rows.append(row)
    print(f"Added user {name!r} with UserID {user_id}.", file=sys.stderr)
    return row


def delete_user(table: BaseTable, name: str) -> None:
    """Remove a user from *table*.

    Args:
        table: The loaded user table (modified in-place).
        name: The username to delete.

    Raises:
        SystemExit: If the user is not found.
    """
    target = _resolve_user(table, name)
    table.rows = [r for r in table.rows if r.get("UserID") != target.get("UserID")]
    print(f"Deleted user {name!r}.", file=sys.stderr)


def rename_user(table: BaseTable, old_name: str, new_name: str) -> None:
    """Rename a user.

    Args:
        table: The loaded user table (modified in-place).
        old_name: Current username.
        new_name: Desired new username.

    Raises:
        SystemExit: If old_name not found or new_name already taken.
    """
    target = _resolve_user(table, old_name)
    if table.find_by_name(new_name) is not None:
        _die(f"User {new_name!r} already exists.")
    target["Name"] = new_name
    print(f"Renamed {old_name!r} to {new_name!r}.", file=sys.stderr)


def change_password(table: BaseTable, name: str, new_password: str) -> None:
    """Change a user's password.

    Args:
        table: The loaded user table (modified in-place).
        name: The username.
        new_password: The new plaintext password.
    """
    target = _resolve_user(table, name)
    user_id = target["UserID"]
    new_hash = get_password_hash(user_id, new_password)
    target["Password"] = new_hash
    print(
        f"UserID {user_id} ({target.get('Name')!r}): password hash updated.",
        file=sys.stderr,
    )


def enable_user(table: BaseTable, name: str) -> None:
    """Enable a user account.

    Args:
        table: The loaded user table (modified in-place).
        name: The username to enable.
    """
    target = _resolve_user(table, name)
    target["Enabled"] = True
    print(f"User {name!r} enabled.", file=sys.stderr)


def disable_user(table: BaseTable, name: str) -> None:
    """Disable a user account.

    Args:
        table: The loaded user table (modified in-place).
        name: The username to disable.
    """
    target = _resolve_user(table, name)
    target["Enabled"] = False
    print(f"User {name!r} disabled.", file=sys.stderr)


def export_users(table: BaseTable) -> list[dict[str, Any]]:
    """Export all users as a JSON-serialisable list.

    Args:
        table: The loaded user table.

    Returns:
        A list of row dicts (suitable for ``json.dumps``).
    """
    return [dict(row) for row in table.rows]


def import_users(table: BaseTable, data: list[dict[str, Any]]) -> None:
    """Import users from a JSON structure, appending to *table*.

    Args:
        table: The loaded user table (modified in-place).
        data: List of row dicts as produced by :func:`export_users`.

    Raises:
        SystemExit: If any imported username conflicts with an existing one.
    """
    for entry in data:
        name = entry.get("Name")
        if name is None:
            _die("Import entry missing 'Name' field.")
        if table.find_by_name(name) is not None:
            _die(f"Import aborted — user {name!r} already exists in table.")
    for entry in data:
        table.rows.append(entry)
    print(f"Imported {len(data)} user(s).", file=sys.stderr)
