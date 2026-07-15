"""Backup utilities for BaseDAT files."""

from __future__ import annotations

import shutil
import time
from pathlib import Path


def create_backup(path: Path) -> Path:
    """Create a timestamped backup of *path*.

    The backup is written alongside the original file with a ``.bak`` suffix
    in the format ``<name>.YYYYMMDD-HHMMSS.bak``.

    Args:
        path: Absolute path to the file to back up.

    Returns:
        The path of the newly created backup file.

    Raises:
        OSError: If the copy operation fails.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path
