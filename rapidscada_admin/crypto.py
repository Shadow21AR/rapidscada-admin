"""Rapid SCADA password hashing.

Port of ScadaCommon/ScadaCommon/ScadaUtils.Crypto.cs.
"""

from __future__ import annotations

import hashlib
import struct

PASSWORD_SALT: str = "aEGnwn3CCSFdth7kNXc3"
"""Static salt from the Rapid SCADA source."""


def _md5_upper(data: bytes) -> str:
    """MD5 hash as uppercase hex string."""
    return hashlib.md5(data).hexdigest().upper()


def get_password_hash(user_id: int, password: str) -> str:
    """Compute the Rapid SCADA password hash for a given user ID and plaintext.

    Reproduces ``ScadaUtils.GetPasswordHash(int itemKey, string password)``::

        hash1 = MD5(UTF8(password))
        hash2 = MD5(int32-little-endian(userId))
        return MD5(hash1 + hash2 + PASSWORD_SALT)

    Args:
        user_id: The row primary key (Users.UserID).
        password: The plaintext password.

    Returns:
        Uppercase hex MD5 hash string, or empty string if password is empty.
    """
    if not password:
        return ""
    hash1 = _md5_upper(password.encode("utf-8"))
    hash2 = _md5_upper(struct.pack("<i", user_id))
    return _md5_upper((hash1 + hash2 + PASSWORD_SALT).encode("utf-8"))
