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

"""Test aspect-ratio commands routed through dimension menus."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QVBoxLayout, QWidget

from tests.presentation.editor.panel.dimensions.context_menu.support import (
    DimensionPanel as _Panel,
    action as _action,
    add_dimension_row as _add_dimension_row,
    cleanup_widgets as _cleanup_widgets,
    ensure_worker_application as _ensure_app,
    install_recording_dimension_menu,
    spinbox as _spinbox,
    submenu as _submenu,
)


def test_width_side_ratio_action_preserves_width_and_updates_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aspect-ratio actions from the width widget should anchor width."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=100, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        width.customContextMenuRequested.emit(QPoint(1, 1))

        _action(
            _submenu(
                _submenu(menu_recording.root, "Set ratio by Width"),
                "Landscape",
            ),
            "16:9",
        ).trigger()
        assert width.value() == 1600
        assert height.value() == 900
    finally:
        _cleanup_widgets(app, content, panel)


def test_height_side_ratio_action_preserves_height_and_updates_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aspect-ratio actions from the height widget should anchor height."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=100, key="source_width")
        height = _spinbox(panel, value=1000, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        height.customContextMenuRequested.emit(QPoint(1, 1))

        _action(
            _submenu(
                _submenu(menu_recording.root, "Set ratio by Height"),
                "Portrait",
            ),
            "4:5",
        ).trigger()
        assert width.value() == 800
        assert height.value() == 1000
    finally:
        _cleanup_widgets(app, content, panel)
