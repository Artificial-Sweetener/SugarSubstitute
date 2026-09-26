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

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from .cube_section import CubeSectionView

class CubeSectionWidgetParts:
    widget: CubeSectionView
    grid_layout: Any
    header_label: Any
    reveal_button: Any
    reveal_menu: Any

class CubeSectionBuilder:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def build_cube_section(self, route_key: str) -> CubeSectionWidgetParts: ...
    def build_error_cube_widget(
        self,
        route_key: str,
        *,
        issue_lines: tuple[str, ...],
    ) -> CubeSectionView: ...

def cube_section_builder_for_panel(panel: QWidget) -> CubeSectionBuilder: ...
