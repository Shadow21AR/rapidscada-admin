"""Tests for rapidscada_admin.backup — backup creation and pruning."""

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


class TestBackupPruning:
    """Backup pruning tests."""

    def test_prunes_oldest_when_exceeding_max(self, user_dat_path: Path) -> None:
        for _ in range(7):
            create_backup(user_dat_path, max_backups=3)
            time.sleep(1.1)
        backups = sorted(user_dat_path.parent.glob("user.dat.*.bak"))
        assert len(backups) == 3

    def test_keeps_all_when_under_limit(self, user_dat_path: Path) -> None:
        for _ in range(3):
            create_backup(user_dat_path, max_backups=5)
            time.sleep(1.1)
        backups = sorted(user_dat_path.parent.glob("user.dat.*.bak"))
        assert len(backups) == 3

    def test_max_zero_keeps_none(self, user_dat_path: Path) -> None:
        create_backup(user_dat_path, max_backups=0)
        time.sleep(1.1)
        create_backup(user_dat_path, max_backups=0)
        backups = list(user_dat_path.parent.glob("user.dat.*.bak"))
        assert len(backups) == 0
