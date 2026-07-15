"""Rapid SCADA BaseDAT file parser.

Preserves the exact binary format from the legacy ``rs_userdat.py`` parser,
which reimplements ``BaseTableAdapter.cs`` from the Rapid SCADA v6 source.
"""

from __future__ import annotations

import dataclasses
import struct
from pathlib import Path
from typing import Any

# Format constants (from BaseTableAdapter.cs)
TABLE_TYPE_BASE: int = 1
MAJOR_VERSION: int = 4
MINOR_VERSION: int = 0
HEADER_SIZE: int = 20
FIELD_DEF_SIZE: int = 60
MAX_FIELD_NAME_LENGTH: int = 50
BLOCK_MARKER: int = 0x0E0E

# Data type codes (from ColumnDataType.cs)
TYPE_INTEGER: int = 1
TYPE_DOUBLE: int = 2
TYPE_BOOLEAN: int = 3
TYPE_DATETIME: int = 4
TYPE_STRING: int = 5

FIXED_SIZE_BY_TYPE: dict[int, int] = {
    TYPE_INTEGER: 4,
    TYPE_DOUBLE: 8,
    TYPE_BOOLEAN: 1,
    TYPE_DATETIME: 8,
    TYPE_STRING: 0,
}


def crc16_modbus(data: bytes) -> int:
    """Compute CRC-16/MODBUS checksum.

    Matches ``ScadaUtils.CRC16()`` from the Rapid SCADA source.

    Args:
        data: Bytes to checksum.

    Returns:
        16-bit CRC value.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


@dataclasses.dataclass(frozen=True)
class FieldDef:
    """Definition of a single column in a BaseDAT table."""

    name: str
    data_type: int
    allow_null: bool

    @property
    def fixed_size(self) -> int:
        """Byte width for fixed-size types, 0 for variable-length strings."""
        return FIXED_SIZE_BY_TYPE[self.data_type]


class FormatError(Exception):
    """Raised when the file doesn't match the expected BaseTableAdapter format."""


class BaseTable:
    """In-memory representation of a Rapid SCADA base table .dat file.

    Rows are plain ``dict[str, Any]`` keyed by column name.  The parser is
    fully generic — nothing is hardcoded to the Users schema.
    """

    def __init__(self, field_defs: list[FieldDef], rows: list[dict[str, Any]]) -> None:
        self.field_defs = field_defs
        self.rows = rows

    @property
    def field_names(self) -> list[str]:
        """Ordered list of column names."""
        return [f.name for f in self.field_defs]

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> BaseTable:
        """Parse a BaseDAT file from *path*.

        Args:
            path: Filesystem path to the .dat file.

        Returns:
            A populated :class:`BaseTable` instance.

        Raises:
            FormatError: If the file cannot be parsed.
            FileNotFoundError: If *path* does not exist.
        """
        data = path.read_bytes()
        if not data:
            return cls([], [])

        pos = 0
        table_type, major, _minor, field_count = struct.unpack_from("<HHHH", data, pos)
        pos += HEADER_SIZE

        if table_type != TABLE_TYPE_BASE:
            raise FormatError(f"Not a base table (type={table_type}); is this the right file?")
        if major != MAJOR_VERSION:
            raise FormatError(f"Unsupported format version {major}.x (expected {MAJOR_VERSION}.x)")

        field_defs, pos = cls._read_field_defs(data, pos, field_count)
        rows, pos = cls._read_rows(data, pos, field_defs)
        return cls(field_defs, rows)

    @staticmethod
    def _read_field_defs(data: bytes, pos: int, field_count: int) -> tuple[list[FieldDef], int]:
        """Deserialize column definitions from the binary stream."""
        field_defs: list[FieldDef] = []
        for i in range(field_count):
            chunk = data[pos : pos + FIELD_DEF_SIZE]
            pos += FIELD_DEF_SIZE

            stored_crc = struct.unpack_from("<H", chunk, FIELD_DEF_SIZE - 2)[0]
            actual_crc = crc16_modbus(chunk[: FIELD_DEF_SIZE - 2])
            if stored_crc != actual_crc:
                raise FormatError(f"Field definition #{i} failed CRC check — file may be corrupt.")

            name_len = chunk[0]
            name = chunk[1 : 1 + name_len].decode("ascii")
            data_type = chunk[1 + MAX_FIELD_NAME_LENGTH]
            allow_null = chunk[1 + MAX_FIELD_NAME_LENGTH + 1] != 0
            field_defs.append(FieldDef(name, data_type, allow_null))
        return field_defs, pos

    @staticmethod
    def _read_rows(
        data: bytes, pos: int, field_defs: list[FieldDef]
    ) -> tuple[list[dict[str, Any]], int]:
        """Deserialize data rows from the binary stream."""
        rows: list[dict[str, Any]] = []
        while pos < len(data):
            marker = struct.unpack_from("<H", data, pos)[0]
            if marker != BLOCK_MARKER:
                raise FormatError(f"Expected row marker at offset {pos}; file may be corrupt.")
            row_data_size = struct.unpack_from("<i", data, pos + 2)[0]
            full_row_size = row_data_size + 6

            row_bytes = data[pos : pos + full_row_size]
            stored_crc = struct.unpack_from("<H", row_bytes, full_row_size - 2)[0]
            actual_crc = crc16_modbus(row_bytes[: full_row_size - 2])
            if stored_crc != actual_crc:
                raise FormatError(f"Row at offset {pos} failed CRC check — file may be corrupt.")

            row, _ = BaseTable._decode_row_fields(row_bytes, 6, field_defs)
            rows.append(row)
            pos += full_row_size
        return rows, pos

    @staticmethod
    def _decode_row_fields(
        buf: bytes, idx: int, field_defs: list[FieldDef]
    ) -> tuple[dict[str, Any], int]:
        """Decode a single row's field values from *buf* starting at *idx*."""
        row: dict[str, Any] = {}
        for fd in field_defs:
            is_null = buf[idx] != 0
            idx += 1
            if is_null:
                row[fd.name] = None
                continue

            size = fd.fixed_size
            if size == 0:
                size = struct.unpack_from("<H", buf, idx)[0]
                idx += 2

            if fd.data_type == TYPE_INTEGER:
                row[fd.name] = struct.unpack_from("<i", buf, idx)[0]
            elif fd.data_type == TYPE_BOOLEAN:
                row[fd.name] = buf[idx] != 0
            elif fd.data_type == TYPE_STRING:
                row[fd.name] = buf[idx : idx + size].decode("utf-8")
            else:
                raise FormatError(f"Unsupported field type {fd.data_type} for field '{fd.name}'")
            idx += size
        return row, idx

    # -- saving -----------------------------------------------------------

    def save(self, path: Path) -> None:
        """Serialize this table to a BaseDAT file at *path*.

        Args:
            path: Destination file path (overwritten if it exists).
        """
        out = bytearray()
        out += struct.pack(
            "<HHHH", TABLE_TYPE_BASE, MAJOR_VERSION, MINOR_VERSION, len(self.field_defs)
        )
        out += bytes(12)  # reserved

        for fd in self.field_defs:
            out += self._encode_field_def(fd)

        for row in self.rows:
            out += self._encode_row(row)

        path.write_bytes(out)

    @staticmethod
    def _encode_field_def(fd: FieldDef) -> bytes:
        """Serialize a single column definition."""
        chunk = bytearray(FIELD_DEF_SIZE)
        name_bytes = fd.name.encode("ascii")
        chunk[0] = len(name_bytes)
        chunk[1 : 1 + len(name_bytes)] = name_bytes
        chunk[1 + MAX_FIELD_NAME_LENGTH] = fd.data_type
        chunk[1 + MAX_FIELD_NAME_LENGTH + 1] = 1 if fd.allow_null else 0
        crc = crc16_modbus(bytes(chunk[: FIELD_DEF_SIZE - 2]))
        struct.pack_into("<H", chunk, FIELD_DEF_SIZE - 2, crc)
        return bytes(chunk)

    def _encode_row(self, row: dict[str, Any]) -> bytes:
        """Serialize a single data row."""
        body = bytearray()
        for fd in self.field_defs:
            value = row.get(fd.name)
            if value is None:
                body += b"\x01"
                continue

            body += b"\x00"
            if fd.data_type == TYPE_INTEGER:
                body += struct.pack("<i", int(value))
            elif fd.data_type == TYPE_BOOLEAN:
                body += b"\x01" if value else b"\x00"
            elif fd.data_type == TYPE_STRING:
                encoded = str(value).encode("utf-8")
                body += struct.pack("<H", len(encoded))
                body += encoded
            else:
                raise FormatError(f"Unsupported field type {fd.data_type} for field '{fd.name}'")

        row_data_size = len(body) + 2
        full_row_size = row_data_size + 6

        buf = bytearray()
        buf += struct.pack("<H", BLOCK_MARKER)
        buf += struct.pack("<i", row_data_size)
        buf += body
        crc = crc16_modbus(bytes(buf))
        buf += struct.pack("<H", crc)

        assert len(buf) == full_row_size
        return bytes(buf)

    # -- lookups -----------------------------------------------------------

    def find_by_name(self, name: str) -> dict[str, Any] | None:
        """Exact match on the Name field.

        Args:
            name: The username to search for.

        Returns:
            The matching row, or ``None``.
        """
        for row in self.rows:
            if row.get("Name") == name:
                return row
        return None

    def find_by_name_loose(self, name: str) -> list[dict[str, Any]]:
        """Case/whitespace-insensitive matches on the Name field.

        Args:
            name: The username to search for (flexible matching).

        Returns:
            List of matching rows.
        """
        wanted = name.strip().casefold()
        return [r for r in self.rows if (r.get("Name") or "").strip().casefold() == wanted]

    def find_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Find a row by its UserID primary key.

        Args:
            user_id: The integer UserID.

        Returns:
            The matching row, or ``None``.
        """
        for row in self.rows:
            if row.get("UserID") == user_id:
                return row
        return None

    def next_user_id(self) -> int:
        """Compute the next available UserID (max + 1).

        Returns:
            The next integer ID, or 1 if the table is empty.
        """
        if not self.rows:
            return 1
        return max(int(r.get("UserID", 0)) for r in self.rows) + 1
