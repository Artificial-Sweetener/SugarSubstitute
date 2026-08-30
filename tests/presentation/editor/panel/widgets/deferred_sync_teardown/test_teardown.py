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

"""Verify deferred editor width synchronization tolerates Qt-owner teardown."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from shiboken6 import delete

import substitute.presentation.editor.panel.widgets.node_card as node_card_module
from substitute.presentation.editor.panel.widgets.cube_section import CubeSectionView
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    MasonryGridLayout,
)


class _ModelPickerWidthSyncSurface(Protocol):
    """Expose the deferred node-card synchronization under test."""

    def sync_model_picker_width_group(self) -> None:
        """Synchronize model-picker widths."""


def test_node_card_width_sync_returns_after_surface_deletion(
    qt_application_owner: QApplication,
) -> None:
    """Keep node-card synchronization inert after its C++ surface is deleted."""

    _ = qt_application_owner
    surface_type = cast(type[QWidget], getattr(node_card_module, "_NodeCardSurface"))
    surface = surface_type()
    delete(surface)

    cast(_ModelPickerWidthSyncSurface, surface).sync_model_picker_width_group()


def test_cube_section_width_sync_returns_after_section_deletion(
    qt_application_owner: QApplication,
) -> None:
    """Keep cube-section synchronization inert after its C++ owner is deleted."""

    _ = qt_application_owner
    section = CubeSectionView(
        header_bar=QWidget(),
        prompt_area=QVBoxLayout(),
        grid_layout=MasonryGridLayout(),
    )
    delete(section)

    section.sync_string_line_edit_width_group()
