#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Validate legacy SQLite integrity and declared cache schema contracts."""

from __future__ import annotations

from pathlib import Path
import sqlite3


def validate_sqlite(
    path: Path,
    *,
    required_tables: set[str],
    schema_table: str | None = None,
    expected_schema: str | None = None,
) -> None:
    """Reject corrupt or structurally incompatible legacy SQLite databases."""

    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        integrity = connection.execute("pragma integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise sqlite3.DatabaseError(
                f"SQLite integrity check failed for {path.name}"
            )
        if not required_tables.issubset(sqlite_tables(connection)):
            raise sqlite3.DatabaseError(
                f"Required cache tables are missing in {path.name}"
            )
        if schema_table is None:
            return
        row = connection.execute(
            f"select value from {schema_table} where key = 'schema_version'"
        ).fetchone()
        if row is None or str(row[0]) != expected_schema:
            raise sqlite3.DatabaseError(f"Cache schema is incompatible in {path.name}")


def sqlite_tables(connection: sqlite3.Connection) -> set[str]:
    """Return user table names from one SQLite connection."""

    return {
        str(row[0])
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    }


__all__ = ["sqlite_tables", "validate_sqlite"]
