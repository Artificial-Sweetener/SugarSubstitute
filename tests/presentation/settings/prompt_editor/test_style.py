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

"""Verify Prompt Editor Settings visual-state policy."""

from __future__ import annotations
from substitute.presentation.settings.settings_style import (
    settings_card_overlay_color,
)


def test_prompt_editor_rows_use_windows_list_item_state_colors() -> None:
    """Prompt row hover and press colors should match Windows SDK list resources."""

    assert (
        settings_card_overlay_color(
            pressed=False,
            hovered=True,
        ).alpha()
        == 0x19
    )
    assert (
        settings_card_overlay_color(
            pressed=True,
            hovered=True,
        ).alpha()
        == 0x33
    )
