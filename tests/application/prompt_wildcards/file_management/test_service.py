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

"""Contract tests for prompt wildcard file management."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository


def test_wildcard_file_management_create_rename_and_delete(
    tmp_path: Path,
) -> None:
    """Mutate only validated text files below the user wildcard root."""

    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )

    path = service.create_text_file("nested/animal", "fox\n")

    entries = service.list_files()
    assert path.name == "animal.txt"
    assert entries[0].relative_path == "nested/animal.txt"
    assert entries[0].identifier == "nested/animal"
    assert service.read_file("nested/animal.txt") == "fox\n"

    renamed_path = service.rename_file("nested/animal.txt", "animal.txt")
    service.delete_file("animal.txt")

    assert renamed_path.name == "animal.txt"
    assert service.list_files() == ()


def test_wildcard_file_management_rejects_escape_paths(tmp_path: Path) -> None:
    """Reject write paths that would escape the user wildcard root."""

    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )

    with pytest.raises(ValueError):
        service.write_file("../escape.txt", "bad")
