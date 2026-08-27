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

"""Contract tests for persisted prompt wildcard preferences."""

from __future__ import annotations

from pathlib import Path

from substitute.application.prompt_wildcards import PromptWildcardPreferenceService
from substitute.infrastructure.persistence import FilePromptWildcardPreferenceRepository


def test_wildcard_preferences_default_to_curly_resolution_enabled(
    tmp_path: Path,
) -> None:
    """Default preferences should enable native curly wildcard resolution."""

    service = PromptWildcardPreferenceService(
        FilePromptWildcardPreferenceRepository(tmp_path)
    )

    preferences = service.load_preferences()

    assert preferences.resolve_on_generation is True
    assert preferences.syntax_profile().delimiters()[0].prefix == "{"


def test_wildcard_preferences_ignore_legacy_custom_activator(
    tmp_path: Path,
) -> None:
    """Keep fixed curly syntax when loading legacy custom-activator fields."""

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
