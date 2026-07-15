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

"""Coordinate user wildcard file management use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PromptWildcardFileEntry:
    """Describe one managed wildcard source file."""

    relative_path: str
    identifier: str
    suffix: str


class PromptWildcardFileRepository(Protocol):
    """Persist and enumerate user-owned wildcard files."""

    def root_path(self) -> Path:
        """Return the managed user wildcard root path."""

    def list_files(self) -> tuple[PromptWildcardFileEntry, ...]:
        """Return managed wildcard files under the user root."""

    def read_file(self, relative_path: str) -> str:
        """Read one managed wildcard file by relative path."""

    def write_file(self, relative_path: str, content: str) -> Path:
        """Create or replace one managed wildcard file by relative path."""

    def delete_file(self, relative_path: str) -> None:
        """Delete one managed wildcard file by relative path."""

    def rename_file(self, old_relative_path: str, new_relative_path: str) -> Path:
        """Rename one managed wildcard file within the user root."""

    def refresh_cache(self) -> None:
        """Invalidate wildcard catalog caches after file changes."""


class PromptWildcardFileManagementService:
    """Expose wildcard file management operations to presentation code."""

    def __init__(self, repository: PromptWildcardFileRepository) -> None:
        """Store the file repository."""

        self._repository = repository

    def root_path(self) -> Path:
        """Return the managed user wildcard root path."""

        return self._repository.root_path()

    def list_files(self) -> tuple[PromptWildcardFileEntry, ...]:
        """Return managed wildcard files under the user root."""

        return self._repository.list_files()

    def read_file(self, relative_path: str) -> str:
        """Read one managed wildcard file by relative path."""

        return self._repository.read_file(relative_path)

    def write_file(self, relative_path: str, content: str) -> Path:
        """Create or replace one managed wildcard file by relative path."""

        path = self._repository.write_file(relative_path, content)
        self._repository.refresh_cache()
        return path

    def create_text_file(self, identifier: str, content: str = "") -> Path:
        """Create or replace a text wildcard file for one identifier."""

        return self.write_file(_file_path_for_identifier(identifier, ".txt"), content)

    def create_csv_file(self, identifier: str, content: str = "value\n") -> Path:
        """Create or replace a CSV wildcard file for one identifier."""

        return self.write_file(_file_path_for_identifier(identifier, ".csv"), content)

    def delete_file(self, relative_path: str) -> None:
        """Delete one managed wildcard file and refresh catalog caches."""

        self._repository.delete_file(relative_path)
        self._repository.refresh_cache()

    def rename_file(self, old_relative_path: str, new_relative_path: str) -> Path:
        """Rename one managed wildcard file and refresh catalog caches."""

        path = self._repository.rename_file(old_relative_path, new_relative_path)
        self._repository.refresh_cache()
        return path

    def refresh_cache(self) -> None:
        """Invalidate wildcard catalog caches."""

        self._repository.refresh_cache()


__all__ = [
    "PromptWildcardFileEntry",
    "PromptWildcardFileManagementService",
    "PromptWildcardFileRepository",
]


def _file_path_for_identifier(identifier: str, suffix: str) -> str:
    """Return a relative file path for a wildcard identifier and desired suffix."""

    path = PurePosixPath(identifier.strip().replace("\\", "/"))
    if path.suffix.lower() in {".txt", ".csv"}:
        path = path.with_suffix("")
    return f"{path.as_posix()}{suffix}"
