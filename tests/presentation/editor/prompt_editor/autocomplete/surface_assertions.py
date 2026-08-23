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

"""Inspect autocomplete projection widgets through stable surface boundaries."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt

from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
    PromptAutocompleteRow,
)


def panel_rows(panel: PromptAutocompletePanel) -> list[PromptAutocompleteRow]:
    """Return the direct child row widgets in render order."""

    return cast(
        list[PromptAutocompleteRow],
        panel.findChildren(
            PromptAutocompleteRow,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        ),
    )
