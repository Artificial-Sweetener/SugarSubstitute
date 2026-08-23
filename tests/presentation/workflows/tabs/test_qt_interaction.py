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

"""Workflow tab Qt interaction contracts."""

from __future__ import annotations

import importlib

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPalette
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)
from tests.presentation.workflows.qt_support import (
    _clear_gui_stubs,
    _ensure_qapp,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_tabbar_swap_item_reorders_real_qt_items() -> None:
    """Real TabBar widget should reorder item list and current index via _swapItem."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )

    tabbar = mod.TabBar(None)
    tabbar.addTab("a", "A")
    tabbar.addTab("b", "B")
    tabbar.addTab("c", "C")
    tabbar.setCurrentIndex(1)

    tabbar._swapItem(0)

    assert [item.routeKey() for item in tabbar.items] == ["b", "a", "c"]
    assert tabbar.currentIndex() == 0
    assert tabbar.currentTab().routeKey() == "b"


def test_workflow_tabbar_mouse_move_delegates_to_gesture_owner() -> None:
    """Workflow tab movement should delegate selection policy to its gesture owner."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )
    tabbar = mod.TabBar(None)
    delegated: list[tuple[QMouseEvent, bool]] = []
    tabbar._handle_tab_mouse_event = lambda event, *, select_on_press: delegated.append(
        (event, select_on_press)
    )
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(4, 4),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    tabbar.mouseMoveEvent(event)

    assert delegated == [(event, False)]
    tabbar.close()
    destroy_qt_object(tabbar)


def test_reorderable_tab_surfaces_disable_qfluent_smooth_scrolling() -> None:
    """Workflow and cube tab surfaces should scroll immediately when overfull."""
    _ensure_qapp()
    _clear_gui_stubs()
    workflow_mod = importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )
    cube_mod = importlib.import_module(
        "substitute.presentation.workflows.cube_stack_view"
    )

    tabbar = workflow_mod.TabBar(None)
    stack = cube_mod.CubeStack(None)

    try:
        for surface in (tabbar, stack):
            assert surface.smoothScroll.smoothMode is SmoothMode.NO_SMOOTH
            assert surface.vScrollBar.duration == 0
            assert surface.hScrollBar.duration == 0
    finally:
        tabbar.close()
        stack.close()
        destroy_qt_object(tabbar)
        destroy_qt_object(stack)


def test_workflow_tab_rename_editor_tracks_theme_text_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow rename editor should use the same light/dark text as tab painting."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    base_mod = importlib.import_module(
        "substitute.presentation.workflows.reorderable_tabs_base"
    )
    mod = importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )

    monkeypatch.setattr(base_mod, "isDarkTheme", lambda: True)
    tabbar = mod.TabBar(None)
    first = tabbar.addTab("a", "Recipe")
    tabbar.show()
    app.processEvents()

    first._startRename()
    app.processEvents()

    assert first.rename_editor.palette().color(QPalette.ColorRole.Text) == QColor(
        Qt.GlobalColor.white
    )

    monkeypatch.setattr(base_mod, "isDarkTheme", lambda: False)
    first._apply_theme_styles()

    assert first.rename_editor.palette().color(QPalette.ColorRole.Text) == QColor(
        Qt.GlobalColor.black
    )
    assert "color: rgba(0, 0, 0, 1.000)" in first.rename_editor.styleSheet()

    tabbar.close()
    destroy_qt_object(tabbar)


def test_workflow_tab_rename_editor_uses_explicit_tab_text_color() -> None:
    """Workflow rename editor should honor explicit tab text color overrides."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )

    tabbar = mod.TabBar(None)
    first = tabbar.addTab("a", "Recipe")
    expected = QColor("#123456")
    tabbar.show()
    app.processEvents()

    first.setTextColor(expected)
    first._startRename()
    app.processEvents()

    assert first.rename_editor.palette().color(QPalette.ColorRole.Text) == expected
    assert "color: rgba(18, 52, 86, 1.000)" in first.rename_editor.styleSheet()

    tabbar.close()
    destroy_qt_object(tabbar)


def test_workflow_tab_rename_editor_geometry_matches_tab_text_rect() -> None:
    """Workflow rename editor should not add padding beyond the painted text rect."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )

    tabbar = mod.TabBar(None)
    first = tabbar.addTab("a", "Recipe")
    tabbar.show()
    app.processEvents()

    first._startRename()
    app.processEvents()

    assert first.rename_editor.geometry() == first._textRect().toRect()
    assert first.rename_editor.contentsMargins().isNull()
    assert first.rename_editor.textMargins().isNull()
    assert first.rename_editor.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    assert "padding: 0px" in first.rename_editor.styleSheet()
    assert "margin: 0px" in first.rename_editor.styleSheet()

    tabbar.close()
    destroy_qt_object(tabbar)
