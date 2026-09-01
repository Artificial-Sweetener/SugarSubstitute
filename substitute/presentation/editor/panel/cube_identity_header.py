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

"""Build editor cube identity headers from canonical cube metadata."""

from __future__ import annotations

from substitute.application.cubes import cube_target_model
from substitute.presentation.editor.panel.cube_section_title import cube_section_title
from substitute.presentation.editor.panel.widgets.cube_title_label import CubeTitleLabel


def build_cube_identity_header(
    route_key: str,
    cube_state: object | None,
) -> CubeTitleLabel:
    """Return an editor title whose model pill survives alias changes."""

    header = CubeTitleLabel(cube_section_title(route_key, cube_state))
    header.setTargetModel(cube_target_model(cube_state))
    return header


__all__ = ["build_cube_identity_header"]
