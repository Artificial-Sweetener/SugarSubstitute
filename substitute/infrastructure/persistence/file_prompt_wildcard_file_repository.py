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

"""Manage Substitute-owned wildcard files under the user wildcard root."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from substitute.application.prompt_wildcards import PromptWildcardFileEntry
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.util.path_safety import ensure_within_root

from .file_prompt_wildcard_catalog_gateway import clear_prompt_wildcard_catalog_caches

_LOGGER = get_logger("infrastructure.persistence.file_prompt_wildcard_file_repository")
_ALLOWED_SUFFIXES = frozenset({".txt", ".csv"})


class FilePromptWildcardFileRepository:
    """Read and mutate user-owned wildcard files with fail-closed path validation."""

    def __init__(self, user_wildcards_root: Path) -> None:
        """Store the managed wildcard root."""

        self._root = Path(user_wildcards_root)

    def root_path(self) -> Path:
        """Return the managed user wildcard root path."""

        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    def list_files(self) -> tuple[PromptWildcardFileEntry, ...]:
        """Return all managed `.txt` and `.csv` wildcard files."""

        root = self.root_path()
        entries: list[PromptWildcardFileEntry] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            try:
                safe_path = ensure_within_root(
                    path,
                    root_path=root,
                    subject="prompt wildcard file",
                )
            except ValueError:
                log_warning(
                    _LOGGER,
                    "Skipping wildcard file outside user wildcard root.",
                    file_name=path.name,
                )
                continue
            relative_path = safe_path.relative_to(root).as_posix()
            identifier = PurePosixPath(relative_path).with_suffix("").as_posix()
            entries.append(
                PromptWildcardFileEntry(
                    relative_path=relative_path,
                    identifier=identifier,
                    suffix=safe_path.suffix.lower(),
                )
            )
        return tuple(entries)

    def read_file(self, relative_path: str) -> str:
        """Read one managed wildcard file by relative path."""

        return self._safe_file_path(relative_path).read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> Path:
        """Create or replace one managed wildcard file by relative path."""

        path = self._safe_file_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def delete_file(self, relative_path: str) -> None:
        """Delete one managed wildcard file by relative path."""

        path = self._safe_file_path(relative_path)
        if path.exists():
            path.unlink()

    def rename_file(self, old_relative_path: str, new_relative_path: str) -> Path:
        """Rename one managed wildcard file within the user root."""

        old_path = self._safe_file_path(old_relative_path)
        new_path = self._safe_file_path(new_relative_path)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        return new_path

    def refresh_cache(self) -> None:
        """Invalidate process-wide wildcard metadata caches."""

        clear_prompt_wildcard_catalog_caches()

    def _safe_file_path(self, relative_path: str) -> Path:
        """Return a validated wildcard file path inside the managed root."""

        normalized = _normalize_relative_file_path(relative_path)
        root = self.root_path()
        candidate = root / Path(*PurePosixPath(normalized).parts)
        return ensure_within_root(
            candidate,
            root_path=root,
            subject="prompt wildcard file",
        )


def _normalize_relative_file_path(relative_path: str) -> str:
    """Validate and normalize one user wildcard relative file path."""

    normalized = relative_path.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute():
        raise ValueError("Wildcard file path must be relative.")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Wildcard file path must not contain traversal parts.")
    if any(":" in part for part in path.parts):
        raise ValueError("Wildcard file path must not contain drive qualifiers.")
    if path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ValueError("Wildcard file path must end with .txt or .csv.")
    return path.as_posix()


__all__ = ["FilePromptWildcardFileRepository"]
