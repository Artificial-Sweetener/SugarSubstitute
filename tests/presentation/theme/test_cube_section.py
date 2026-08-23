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

"""Verify cube-section titles remain QFluent theme primitives."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QWidget
from qfluentwidgets import SubtitleLabel, Theme  # type: ignore[import-untyped]

from substitute.presentation.editor.panel.widgets.cube_section import (
    cube_section_builder_for_panel,
)
from tests.presentation.theme.support import ThemeWidgetOwner, is_qfluent_managed


class CubeSectionPanel(QWidget):
    """Provide editor-panel attributes needed to build a cube section."""

    def __init__(self) -> None:
        """Initialize the minimal cube-section composition state."""

        super().__init__()
        self.cube_headers: dict[str, QWidget] = {}
        self._cube_visibility_btns: dict[str, QWidget] = {}
        self._cube_visibility_menus: dict[str, object] = {}
        self._last_behavior_snapshot = SimpleNamespace(
            field_specs_by_alias={},
            reveal_entries_by_alias={},
        )
        setattr(
            self,
            "scroll",
            SimpleNamespace(schedule_metrics_refresh=lambda: None),
        )

    def _build_behavior_snapshot(self) -> object:
        """Return the already configured behavior snapshot."""

        return self._last_behavior_snapshot


def test_title_uses_qfluent_label_primitive(
    theme_owner: ThemeWidgetOwner,
) -> None:
    """Cube section titles are labels managed by QFluent styling."""

    with theme_owner.using_theme(Theme.DARK):
        panel = theme_owner.own(CubeSectionPanel())
        cube_section_builder_for_panel(panel).build_cube_section("SDXL/Text to Image")

        title = panel.cube_headers["SDXL/Text to Image"]
        assert isinstance(title, SubtitleLabel)
        assert is_qfluent_managed(title)
