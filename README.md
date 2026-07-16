# rapidscada-admin

[![CI](https://github.com/Shadow21AR/rapidscada-admin/actions/workflows/ci.yml/badge.svg)](https://github.com/Shadow21AR/rapidscada-admin/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/rapidscada-admin)](https://pypi.org/project/rapidscada-admin/)
[![Python](https://img.shields.io/pypi/pyversions/rapidscada-admin)](https://pypi.org/project/rapidscada-admin/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Linux command-line utility for administering [Rapid SCADA](https://rapidscada.org/) v6 BaseDAT configuration files.

## What is Rapid SCADA?

[Rapid SCADA](https://rapidscada.org/) is an open-source industrial automation and SCADA system. It stores configuration -- users, roles, rights, and other tables -- in binary BaseDAT (`.dat`) files. Editing these files normally requires the Windows Administrator application. This tool fills the gap for Linux environments.

## Why this tool?

- Automate user management from shell scripts and Ansible playbooks
- Inspect and modify `user.dat` without the Windows GUI
- Validate file integrity before and after changes
- Export/import user data as JSON for backup and migration
- No third-party dependencies -- pure Python standard library

## Supported platforms

- **Linux** (primary target)
- macOS / Windows (should work, but untested)

Requires **Python 3.11+**.

## Installation

### From PyPI

```bash
pip install rapidscada-admin
```

Or with [pipx](https://pypa.github.io/pipx/) (recommended for CLI tools):

```bash
pipx install rapidscada-admin
```

### From source

```bash
git clone https://github.com/Shadow21AR/rapidscada-admin.git
cd rapidscada-admin
pip install .
```

For development:

```bash
pip install -e .
pip install pytest ruff
```

### Verify installation

```bash
rapidscada-admin --version
```

## Usage

Every command takes the `.dat` file path as a positional argument. No files are hardcoded.

```bash
rapidscada-admin <command> [file] [options]
rapidscada-admin users <file> <subcommand> [options]
```

### User management

```bash
# List all users
rapidscada-admin users user.dat list

# Show one user (displays full details including password hash)
rapidscada-admin users user.dat show --user admin

# Add a user
rapidscada-admin users user.dat add \
    --name operator \
    --password 'S3cur3P@ss!' \
    --role 2 \
    --description "Shift operator"

# Delete a user
rapidscada-admin users user.dat delete --user operator

# Rename a user
rapidscada-admin users user.dat rename --old-name operator --new-name op2

# Change password
rapidscada-admin users user.dat passwd --user admin --password 'NewP@ssw0rd!'

# Enable / disable account
rapidscada-admin users user.dat enable --user admin
rapidscada-admin users user.dat disable --user admin
```

### Export and import

```bash
# Export all users to JSON
rapidscada-admin users user.dat export > users.json

# Import users from JSON
rapidscada-admin users user.dat import --input users.json
```

### Password hashing

Compute a Rapid SCADA password hash without modifying any file:

```bash
rapidscada-admin hash --password secret
rapidscada-admin hash --user-id 11 --password scada
```

### Validation

Check a BaseDAT file for corruption, schema errors, and duplicate entries:

```bash
rapidscada-admin verify user.dat
```

Exit code `0` means valid, `1` means errors found.

## Safety

Every mutating command follows a 7-step safety protocol:

1. **Verify schema** -- required fields (`UserID`, `Enabled`, `Name`, `Password`, `RoleID`) must be present
2. **Create backup** -- timestamped `.bak` file alongside the original, with automatic pruning (keeps last 5)
3. **Write temporary file** -- changes go to a temp file first
4. **Re-read temporary file** -- parse the file we just wrote
5. **Validate** -- check schema, duplicates, integrity
6. **Atomic replace** -- `os.replace()` ensures no partial writes
7. **Preserve permissions** -- original file mode bits are restored after replace

A malformed `.dat` file can prevent Rapid SCADA from starting. **Always verify before and after operations.**

### Backup pruning

By default, a maximum of **5 backup files** are kept per `.dat` file. Older backups are automatically deleted when this limit is exceeded. The backup filename format is `<name>.YYYYMMDD-HHMMSS.bak`.

## Limitations

- Only supports BaseDAT format version 4.x (Rapid SCADA v6)
- Does not support editing the Windows Administrator application's in-memory state
- Password hashing uses MD5 (matching the Rapid SCADA protocol -- not a general security recommendation)
- Does not validate RoleID values against `role.dat` (role table is not yet supported)

## Publishing to PyPI

This project uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) -- no API tokens needed.

### Setup

1. Create an account on [pypi.org](https://pypi.org)
2. Create the project at [pypi.org/manage/project/publishing](https://pypi.org/manage/project/publishing/)
3. Add a GitHub publisher:
   - Owner: `Shadow21AR`
   - Repository: `rapidscada-admin`
   - Workflow: `release.yml`
   - Environment: `pypi`
4. In GitHub repo settings, create an environment named `pypi`

### Release

```bash
git tag v1.0.0
git push origin v1.0.0
```

The CI workflow runs on every push. The release workflow runs only on `v*` tags and publishes to PyPI.

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run `pytest` and `ruff check` before submitting
5. Open a pull request

## License

[MIT](LICENSE)
