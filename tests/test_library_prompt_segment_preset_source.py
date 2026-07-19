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

"""Tests for global prompt segments used outside workflow editor panels."""

from __future__ import annotations

from substitute.application.user_presets import UserPreset, UserPresetService
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from substitute.presentation.managed_text_assets.library_prompt_segment_preset_source import (
    LibraryPromptSegmentPresetSource,
)


class _MemoryUserPresetRepository:
    """Persist user presets in memory for the library source contract."""

    def __init__(self) -> None:
        """Initialize an empty preset collection."""

        self.presets: tuple[UserPreset, ...] = ()

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return current stored presets."""

        return self.presets

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Replace current stored presets."""

        self.presets = presets


def test_library_prompt_segment_source_lists_and_saves_global_segments() -> None:
    """Library editors should share global saved prompt segments."""

    source = LibraryPromptSegmentPresetSource(
        UserPresetService(_MemoryUserPresetRepository())
    )
    initial = source.list_prompt_segment_presets()
    scope = initial.menu_model.save_scopes[0]

    source.save_prompt_segment(
        label="Portrait",
        text="detailed portrait, studio lighting",
        scope=scope,
    )
    snapshot = source.list_prompt_segment_presets()

    assert scope.association == GLOBAL_PRESET_ASSOCIATION
    assert tuple(section.title for section in snapshot.menu_model.sections) == (
        "Global",
    )
    assert tuple(
        (item.label, item.text) for item in snapshot.menu_model.sections[0].presets
    ) == (("Portrait", "detailed portrait, studio lighting"),)
