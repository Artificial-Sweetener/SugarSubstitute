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

"""Test source-backed application regional prompt naming policy."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor.document.views import (
    PromptRegionSeparatorView,
)
from substitute.application.prompt_editor.editing.region_naming import (
    PromptRegionNamingService,
)


def _separator(*, named: bool) -> PromptRegionSeparatorView:
    """Return one plain or named separator view for focused policy tests."""

    if named:
        return PromptRegionSeparatorView(0, 10, 0, 11, 5, 9, "Face")
    return PromptRegionSeparatorView(0, 5, 0, 6)


def test_region_naming_wraps_plain_separator_without_deleting_marker() -> None:
    """A plain marker should become named through one atomic replacement."""

    replacement = PromptRegionNamingService().replacement_for(
        _separator(named=False), "Subject"
    )

    assert (replacement.source_start, replacement.source_end) == (0, 5)
    assert replacement.replacement_text == "[SEP|Subject]"


def test_region_naming_replaces_only_existing_authored_name() -> None:
    """Renaming should preserve the existing marker characters exactly."""

    replacement = PromptRegionNamingService().replacement_for(
        _separator(named=True), "背景"
    )

    assert (replacement.source_start, replacement.source_end) == (5, 9)
    assert replacement.replacement_text == "背景"


def test_region_naming_empty_name_restores_plain_separator() -> None:
    """Clearing a name should retain the structural marker."""

    replacement = PromptRegionNamingService().replacement_for(
        _separator(named=True), ""
    )

    assert (replacement.source_start, replacement.source_end) == (0, 10)
    assert replacement.replacement_text == "[SEP]"


@pytest.mark.parametrize("invalid_name", ("bad]name", "two\nlines", "two\rlines"))
def test_region_naming_rejects_structurally_ambiguous_names(invalid_name: str) -> None:
    """Names must never be able to terminate or split their marker."""

    with pytest.raises(ValueError):
        PromptRegionNamingService().replacement_for(
            _separator(named=False), invalid_name
        )
