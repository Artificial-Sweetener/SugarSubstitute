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

"""Format editor cube-section titles from workflow cube state."""

from __future__ import annotations

from substitute.application.display_labels import beautify_label
from substitute.domain.workflow import is_cube_bypassed
from sugarsubstitute_shared.presentation.localization import (
    translate_application_message,
)


def cube_section_title(alias: str, cube_state: object | None) -> str:
    """Return the visible editor title for one cube section."""

    title = beautify_label(alias)
    if cube_state is not None and is_cube_bypassed(cube_state):
        return translate_application_message("%1 (bypassed)", title)
    return title


__all__ = ["cube_section_title"]
