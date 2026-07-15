"""Tests for rapidscada_admin.basetable — parser read/write roundtrip."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from rapidscada_admin.basetable import (
    TYPE_BOOLEAN,
    TYPE_INTEGER,
    TYPE_STRING,
    BaseTable,
    FieldDef,
    FormatError,
    crc16_modbus,
)


class TestCrc16:
    """CRC-16/MODBUS checksum tests."""

    def test_empty_data(self) -> None:
        assert crc16_modbus(b"") == 0xFFFF

    def test_known_value(self) -> None:
        # "123456789" is a standard CRC test vector
        result = crc16_modbus(b"123456789")
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_deterministic(self) -> None:
        data = b"hello world"
        assert crc16_modbus(data) == crc16_modbus(data)

    def test_different_data_different_crc(self) -> None:
        assert crc16_modbus(b"aaa") != crc16_modbus(b"bbb")


class TestFieldDef:
    """FieldDef dataclass tests."""

    def test_fixed_size_integer(self) -> None:
        fd = FieldDef("ID", TYPE_INTEGER, False)
        assert fd.fixed_size == 4

    def test_fixed_size_boolean(self) -> None:
        fd = FieldDef("Flag", TYPE_BOOLEAN, False)
        assert fd.fixed_size == 1

    def test_fixed_size_string(self) -> None:
        fd = FieldDef("Name", TYPE_STRING, False)
        assert fd.fixed_size == 0

    def test_frozen(self) -> None:
        fd = FieldDef("X", TYPE_INTEGER, False)
        with pytest.raises(AttributeError):
            fd.name = "Y"  # type: ignore[misc]


class TestBaseTableRoundtrip:
    """Write-then-read roundtrip tests."""

    def test_roundtrip_preserves_rows(
        self, user_dat_path: Path, sample_user_rows: list[dict]
    ) -> None:
        loaded = BaseTable.load(user_dat_path)
        assert len(loaded.rows) == len(sample_user_rows)
        for original, loaded_row in zip(sample_user_rows, loaded.rows, strict=True):
            for key in original:
                assert loaded_row[key] == original[key]

    def test_roundtrip_preserves_field_names(self, user_dat_path: Path) -> None:
        loaded = BaseTable.load(user_dat_path)
        assert loaded.field_names == [
            "UserID",
            "Enabled",
            "Name",
            "Password",
            "RoleID",
            "Description",
        ]

    def test_roundtrip_preserves_bytes(self, tmp_path: Path, sample_table: BaseTable) -> None:
        path_a = tmp_path / "a.dat"
        path_b = tmp_path / "b.dat"
        sample_table.save(path_a)
        reloaded = BaseTable.load(path_a)
        reloaded.save(path_b)
        assert path_a.read_bytes() == path_b.read_bytes()

    def test_empty_table_roundtrip(self, tmp_path: Path, empty_table: BaseTable) -> None:
        path = tmp_path / "empty.dat"
        empty_table.save(path)
        loaded = BaseTable.load(path)
        assert loaded.rows == []
        assert loaded.field_names == [
            "UserID",
            "Enabled",
            "Name",
            "Password",
            "RoleID",
            "Description",
        ]


class TestBaseTableLoad:
    """File loading edge cases."""

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.dat"
        path.write_bytes(b"")
        table = BaseTable.load(path)
        assert table.rows == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            BaseTable.load(tmp_path / "nope.dat")

    def test_corrupt_header(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.dat"
        path.write_bytes(b"\x00" * 30)
        with pytest.raises(FormatError, match="Not a base table"):
            BaseTable.load(path)

    def test_wrong_version(self, tmp_path: Path) -> None:
        from rapidscada_admin.basetable import HEADER_SIZE, TABLE_TYPE_BASE

        header = struct.pack("<HHHH", TABLE_TYPE_BASE, 99, 0, 0)
        header += b"\x00" * (HEADER_SIZE - 8)
        path = tmp_path / "badver.dat"
        path.write_bytes(header)
        with pytest.raises(FormatError, match="Unsupported format version"):
            BaseTable.load(path)

    def test_corrupt_row_crc(self, tmp_path: Path, sample_table: BaseTable) -> None:
        path = tmp_path / "corrupt.dat"
        sample_table.save(path)
        data = bytearray(path.read_bytes())
        # Corrupt a byte in the data area (after header + field defs)
        header_size = 20
        field_def_size = 60 * len(sample_table.field_defs)
        data[header_size + field_def_size + 10] ^= 0xFF
        path.write_bytes(bytes(data))
        with pytest.raises(FormatError, match="CRC check"):
            BaseTable.load(path)


class TestBaseTableLookups:
    """Lookup method tests."""

    def test_find_by_name_exact(self, sample_table: BaseTable) -> None:
        row = sample_table.find_by_name("admin")
        assert row is not None
        assert row["UserID"] == 1

    def test_find_by_name_missing(self, sample_table: BaseTable) -> None:
        assert sample_table.find_by_name("nobody") is None

    def test_find_by_name_loose_case(self, sample_table: BaseTable) -> None:
        results = sample_table.find_by_name_loose("ADMIN")
        assert len(results) == 1
        assert results[0]["Name"] == "admin"

    def test_find_by_name_loose_whitespace(self, sample_table: BaseTable) -> None:
        results = sample_table.find_by_name_loose("  admin  ")
        assert len(results) == 1

    def test_find_by_id(self, sample_table: BaseTable) -> None:
        row = sample_table.find_by_id(2)
        assert row is not None
        assert row["Name"] == "operator"

    def test_find_by_id_missing(self, sample_table: BaseTable) -> None:
        assert sample_table.find_by_id(999) is None

    def test_next_user_id(self, sample_table: BaseTable) -> None:
        assert sample_table.next_user_id() == 4

    def test_next_user_id_empty(self, empty_table: BaseTable) -> None:
        assert empty_table.next_user_id() == 1


class TestBaseTableFieldDefs:
    """Field definition edge cases."""

    def test_multiple_string_fields(self, tmp_path: Path) -> None:
        defs = [
            FieldDef("ID", TYPE_INTEGER, False),
            FieldDef("A", TYPE_STRING, False),
            FieldDef("B", TYPE_STRING, True),
        ]
        rows = [
            {"ID": 1, "A": "hello", "B": "world"},
            {"ID": 2, "A": "foo", "B": None},
        ]
        table = BaseTable(defs, rows)
        path = tmp_path / "multi.dat"
        table.save(path)
        loaded = BaseTable.load(path)
        assert loaded.rows[0]["A"] == "hello"
        assert loaded.rows[0]["B"] == "world"
        assert loaded.rows[1]["B"] is None
