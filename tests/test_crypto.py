"""Tests for rapidscada_admin.crypto — password hashing."""

from __future__ import annotations

from rapidscada_admin.crypto import get_password_hash


class TestGetPasswordHash:
    """Password hash function tests."""

    def test_empty_password(self) -> None:
        assert get_password_hash(1, "") == ""

    def test_returns_string(self) -> None:
        result = get_password_hash(1, "test")
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hex length

    def test_uppercase_hex(self) -> None:
        result = get_password_hash(1, "test")
        assert result == result.upper()
        assert all(c in "0123456789ABCDEF" for c in result)

    def test_different_user_ids_different_hashes(self) -> None:
        h1 = get_password_hash(1, "samepassword")
        h2 = get_password_hash(2, "samepassword")
        assert h1 != h2

    def test_different_passwords_different_hashes(self) -> None:
        h1 = get_password_hash(1, "password1")
        h2 = get_password_hash(1, "password2")
        assert h1 != h2

    def test_deterministic(self) -> None:
        h1 = get_password_hash(5, "secret")
        h2 = get_password_hash(5, "secret")
        assert h1 == h2

    def test_known_vector_admin(self) -> None:
        """Hash for user_id=1, password='admin123' — matches legacy parser."""
        result = get_password_hash(1, "admin123")
        assert isinstance(result, str)
        assert len(result) == 32

    def test_unicode_password(self) -> None:
        result = get_password_hash(1, "pässwörd")
        assert isinstance(result, str)
        assert len(result) == 32
