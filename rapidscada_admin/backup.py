"""Backup utilities for BaseDAT files."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

DEFAULT_MAX_BACKUPS: int = 5
"""Maximum number of backup files to retain per .dat file."""


def create_backup(path: Path, max_backups: int = DEFAULT_MAX_BACKUPS) -> Path:
    """Create a timestamped backup of *path* and prune old backups.

    The backup is written alongside the original file with a ``.bak`` suffix
    in the format ``<name>.YYYYMMDD-HHMMSS.bak``.

    After creating the backup, the oldest backups exceeding *max_backups*
    are automatically deleted.

    Args:
        path: Absolute path to the file to back up.
        max_backups: Maximum number of ``.bak`` files to keep (default 5).

    Returns:
        The path of the newly created backup file.

    Raises:
        OSError: If the copy operation fails.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup_path)
    _prune_backups(path, max_backups)
    return backup_path


def _prune_backups(path: Path, max_backups: int) -> None:
    """Remove oldest ``.bak`` files if count exceeds *max_backups*.

    Args:
        path: The original ``.dat`` file path (used to derive the glob).
        max_backups: Keep at most this many backup files.
    """
    pattern = f"{path.name}.*.bak"
    backups = sorted(path.parent.glob(pattern), key=lambda p: p.stat().st_mtime)
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        oldest.unlink(missing_ok=True)
