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

"""Tests for prompt wildcard preference and file-management persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.prompt_wildcards import (
    PromptWildcardFileManagementService,
    PromptWildcardPreferenceService,
)
from substitute.infrastructure.persistence import (
    FilePromptWildcardFileRepository,
    FilePromptWildcardPreferenceRepository,
)


def test_wildcard_preferences_default_to_curly_resolution_enabled(
    tmp_path: Path,
) -> None:
    """Wildcard preferences should default to native curly resolution."""

    service = PromptWildcardPreferenceService(
        FilePromptWildcardPreferenceRepository(tmp_path)
    )

    preferences = service.load_preferences()

    assert preferences.resolve_on_generation is True
    assert preferences.syntax_profile().delimiters()[0].prefix == "{"


def test_wildcard_preferences_ignore_legacy_custom_activator(
    tmp_path: Path,
) -> None:
    """Persisted legacy activator fields should not change fixed curly behavior."""

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "prompt_wildcards.json").write_text(
        (
            "{\n"
            '  "version": 1,\n'
            '  "resolve_on_generation": false,\n'
            '  "activator_style": "custom",\n'
            '  "custom_prefix": "[[",\n'
            '  "custom_suffix": "]]"\n'
            "}\n"
        ),
        encoding="utf-8",
    )

    service = PromptWildcardPreferenceService(
        FilePromptWildcardPreferenceRepository(config_dir)
    )

    preferences = service.load_preferences()
    assert preferences.resolve_on_generation is False
    assert preferences.syntax_profile().delimiters()[0].prefix == "{"


def test_wildcard_file_management_create_rename_and_delete(
    tmp_path: Path,
) -> None:
    """Wildcard file management should mutate only validated user-root files."""

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
    """Wildcard file management should reject traversal outside the user root."""

    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )

    with pytest.raises(ValueError):
        service.write_file("../escape.txt", "bad")
