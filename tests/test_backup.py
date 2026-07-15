"""Tests for rapidscada_admin.backup — backup creation."""

from __future__ import annotations

import time
from pathlib import Path

from rapidscada_admin.backup import create_backup


class TestCreateBackup:
    """Backup creation tests."""

    def test_creates_backup_file(self, user_dat_path: Path) -> None:
        backup = create_backup(user_dat_path)
        assert backup.exists()
        assert backup != user_dat_path

    def test_backup_naming_format(self, user_dat_path: Path) -> None:
        backup = create_backup(user_dat_path)
        assert backup.name.startswith("user.dat.")
        assert backup.name.endswith(".bak")

    def test_backup_content_matches_original(self, user_dat_path: Path) -> None:
        backup = create_backup(user_dat_path)
        assert backup.read_bytes() == user_dat_path.read_bytes()

    def test_multiple_backups_unique_names(self, user_dat_path: Path) -> None:
        b1 = create_backup(user_dat_path)
        time.sleep(1.1)  # ensure different timestamp
        b2 = create_backup(user_dat_path)
        assert b1 != b2
        assert b1.exists()
        assert b2.exists()

    def test_backup_in_same_directory(self, user_dat_path: Path) -> None:
        backup = create_backup(user_dat_path)
        assert backup.parent == user_dat_path.parent
