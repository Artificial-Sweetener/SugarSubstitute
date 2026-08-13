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

"""Recover owned SQLite caches from corruption or incompatible schemas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.cache_lifecycle.sqlite_recovery")


def initialize_recoverable_sqlite(
    database_path: Path,
    *,
    cache_id: str,
    initialize: Callable[[], None],
    select_database: Callable[[Path], None],
) -> None:
    """Initialize SQLite and replace invalid cache files with a clean database."""

    try:
        initialize()
    except (sqlite3.DatabaseError, RuntimeError) as error:
        quarantine_directory = database_path.parent / "quarantine"
        quarantine_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        recovery_path: Path | None = None
        for member in _sqlite_family(database_path):
            if not member.exists():
                continue
            destination = quarantine_directory / (
                f"{member.name}.{timestamp}.{uuid4().hex[:8]}.invalid"
            )
            try:
                member.replace(destination)
            except OSError:
                shutil.copy2(member, destination)
                if member == database_path:
                    recovery_path = database_path.with_name(
                        f"{database_path.stem}.recovered-{uuid4().hex[:8]}"
                        f"{database_path.suffix}"
                    )
        if recovery_path is not None:
            select_database(recovery_path)
        log_warning(
            _LOGGER,
            "Replaced an invalid SQLite persistent cache with an empty database.",
            cache_id=cache_id,
            database_name=database_path.name,
            error=repr(error),
        )
        initialize()


def _sqlite_family(database_path: Path) -> tuple[Path, ...]:
    """Return the database and sidecar paths owned by one SQLite cache."""

    return (
        database_path,
        database_path.with_name(f"{database_path.name}-wal"),
        database_path.with_name(f"{database_path.name}-shm"),
        database_path.with_name(f"{database_path.name}-journal"),
    )


__all__ = ["initialize_recoverable_sqlite"]
