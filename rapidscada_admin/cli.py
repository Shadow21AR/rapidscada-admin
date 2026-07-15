"""Command-line interface for rapidscada-admin.

Uses only the standard library ``argparse`` module.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rapidscada_admin import __version__
from rapidscada_admin.basetable import BaseTable, FormatError
from rapidscada_admin.crypto import get_password_hash
from rapidscada_admin.users import (
    _die,
    _safe_write,
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
from rapidscada_admin.validation import validate_user_file


def _load_table(path: Path) -> BaseTable:
    """Load a BaseTable from *path*, exiting on error.

    Args:
        path: Filesystem path to the .dat file.

    Returns:
        The loaded :class:`BaseTable`.
    """
    try:
        return BaseTable.load(path)
    except FormatError as exc:
        _die(f"Format error: {exc}")
    except FileNotFoundError:
        _die(f"File not found: {path}")
    return BaseTable([], [])  # unreachable, satisfies type checker


# --------------------------------------------------------------------------
# Command handlers
# --------------------------------------------------------------------------


def cmd_hash(args: argparse.Namespace) -> None:
    """Print a Rapid SCADA password hash."""
    print(get_password_hash(args.user_id, args.password))


def cmd_verify(args: argparse.Namespace) -> None:
    """Validate a BaseDAT file."""
    path = Path(args.datfile)
    result = validate_user_file(path)
    result.report()
    sys.exit(0 if result.ok else 1)


def cmd_users_list(args: argparse.Namespace) -> None:
    """List all users in the table."""
    table = _load_table(Path(args.datfile))
    list_users(table)


def cmd_users_show(args: argparse.Namespace) -> None:
    """Show details for one user."""
    table = _load_table(Path(args.datfile))
    show_user(table, args.user)


def cmd_users_add(args: argparse.Namespace) -> None:
    """Add a new user."""
    path = Path(args.datfile)
    table = _load_table(path)
    add_user(
        table,
        name=args.name,
        password=args.password,
        role=args.role,
        enabled=not args.disabled,
        description=args.description or "",
    )
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


def cmd_users_delete(args: argparse.Namespace) -> None:
    """Delete a user."""
    path = Path(args.datfile)
    table = _load_table(path)
    delete_user(table, args.user)
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


def cmd_users_rename(args: argparse.Namespace) -> None:
    """Rename a user."""
    path = Path(args.datfile)
    table = _load_table(path)
    rename_user(table, args.old_name, args.new_name)
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


def cmd_users_passwd(args: argparse.Namespace) -> None:
    """Change a user's password."""
    path = Path(args.datfile)
    table = _load_table(path)
    change_password(table, args.user, args.password)
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


def cmd_users_enable(args: argparse.Namespace) -> None:
    """Enable a user account."""
    path = Path(args.datfile)
    table = _load_table(path)
    enable_user(table, args.user)
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


def cmd_users_disable(args: argparse.Namespace) -> None:
    """Disable a user account."""
    path = Path(args.datfile)
    table = _load_table(path)
    disable_user(table, args.user)
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


def cmd_users_export(args: argparse.Namespace) -> None:
    """Export all users as JSON."""
    table = _load_table(Path(args.datfile))
    data = export_users(table)
    print(json.dumps(data, indent=2, default=str))


def cmd_users_import(args: argparse.Namespace) -> None:
    """Import users from JSON."""
    path = Path(args.datfile)
    table = _load_table(path)

    input_data = args.input.read()
    try:
        data = json.loads(input_data)
    except json.JSONDecodeError as exc:
        _die(f"Invalid JSON input: {exc}")

    if not isinstance(data, list):
        _die("Import JSON must be a list of user objects.")

    import_users(table, data)
    _safe_write(table, path)
    print("Done.", file=sys.stderr)


# --------------------------------------------------------------------------
# Argument parser
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all sub-commands.

    Returns:
        A fully configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="rapidscada-admin",
        description="Administer Rapid SCADA BaseDAT files from the command line.",
        epilog=(
            "examples:\n"
            "  rapidscada-admin users user.dat list\n"
            "  rapidscada-admin users user.dat passwd --user admin --password NewPass\n"
            "  rapidscada-admin hash --password secret\n"
            "  rapidscada-admin verify user.dat"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    # -- hash --------------------------------------------------------------
    p_hash = sub.add_parser(
        "hash",
        help="Print a Rapid SCADA password hash (no file needed)",
    )
    p_hash.add_argument(
        "--user-id",
        type=int,
        default=0,
        help="Numeric UserID for the hash (default: 0)",
    )
    p_hash.add_argument("--password", required=True, help="Plaintext password to hash")
    p_hash.set_defaults(func=cmd_hash)

    # -- verify ------------------------------------------------------------
    p_verify = sub.add_parser(
        "verify",
        help="Validate a BaseDAT file for integrity and schema",
    )
    p_verify.add_argument("datfile", help="Path to the BaseDAT file")
    p_verify.set_defaults(func=cmd_verify)

    # -- users -------------------------------------------------------------
    p_users = sub.add_parser(
        "users",
        help="User administration commands",
        usage="%(prog)s FILE <command> [options]",
        description="Manage users in a Rapid SCADA BaseDAT file.",
        epilog=(
            "examples:\n"
            "  %(prog)s user.dat list\n"
            "  %(prog)s user.dat show --user admin\n"
            "  %(prog)s user.dat add --name operator --password Secret123\n"
            "  %(prog)s user.dat passwd --user admin --password NewPass\n"
            "  %(prog)s user.dat delete --user olduser\n"
            "  %(prog)s user.dat export > users.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_users.add_argument("datfile", help="Path to the BaseDAT file")
    users_sub = p_users.add_subparsers(dest="users_command", required=True)

    # -- users list --------------------------------------------------------
    users_sub.add_parser("list", help="List all users").set_defaults(
        func=cmd_users_list,
    )

    # -- users show --------------------------------------------------------
    p_show = users_sub.add_parser("show", help="Show details for one user")
    p_show.add_argument("--user", required=True, help="Username to display")
    p_show.set_defaults(func=cmd_users_show)

    # -- users add ---------------------------------------------------------
    p_add = users_sub.add_parser("add", help="Add a new user")
    p_add.add_argument("--name", required=True, help="Username")
    p_add.add_argument("--password", required=True, help="Plaintext password")
    p_add.add_argument("--role", type=int, default=0, help="RoleID (default: 0)")
    p_add.add_argument(
        "--disabled",
        action="store_true",
        help="Create the account as disabled (default: enabled)",
    )
    p_add.add_argument("--description", default="", help="Optional description")
    p_add.set_defaults(func=cmd_users_add)

    # -- users delete ------------------------------------------------------
    p_del = users_sub.add_parser("delete", help="Delete a user")
    p_del.add_argument("--user", required=True, help="Username to delete")
    p_del.set_defaults(func=cmd_users_delete)

    # -- users rename ------------------------------------------------------
    p_rename = users_sub.add_parser("rename", help="Rename a user")
    p_rename.add_argument("--old-name", required=True, help="Current username")
    p_rename.add_argument("--new-name", required=True, help="New username")
    p_rename.set_defaults(func=cmd_users_rename)

    # -- users passwd ------------------------------------------------------
    p_passwd = users_sub.add_parser("passwd", help="Change a user's password")
    p_passwd.add_argument("--user", required=True, help="Username")
    p_passwd.add_argument("--password", required=True, help="New plaintext password")
    p_passwd.set_defaults(func=cmd_users_passwd)

    # -- users enable ------------------------------------------------------
    p_enable = users_sub.add_parser("enable", help="Enable a user account")
    p_enable.add_argument("--user", required=True, help="Username to enable")
    p_enable.set_defaults(func=cmd_users_enable)

    # -- users disable -----------------------------------------------------
    p_disable = users_sub.add_parser("disable", help="Disable a user account")
    p_disable.add_argument("--user", required=True, help="Username to disable")
    p_disable.set_defaults(func=cmd_users_disable)

    # -- users export ------------------------------------------------------
    users_sub.add_parser("export", help="Export users as JSON").set_defaults(
        func=cmd_users_export,
    )

    # -- users import ------------------------------------------------------
    p_import = users_sub.add_parser("import", help="Import users from JSON")
    p_import.add_argument(
        "--input",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="JSON file to import (default: stdin)",
    )
    p_import.set_defaults(func=cmd_users_import)

    return parser


def main() -> None:
    """Entry point for the ``rapidscada-admin`` CLI."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
