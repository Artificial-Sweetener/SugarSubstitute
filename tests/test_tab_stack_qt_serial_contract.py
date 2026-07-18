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

"""Qt-backed serial characterization tests for tab/cube reorder behavior."""

from __future__ import annotations

import importlib
import os
import sys
from typing import cast

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPalette, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "qt serial tab/stack tests require non-xdist execution",
        allow_module_level=True,
    )


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _clear_gui_stubs() -> None:
    """Remove lightweight stubs so real Qt widgets can import."""
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "QCoreApplication"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    qfw = sys.modules.get("qfluentwidgets")
    if qfw is not None and not hasattr(qfw, "MenuAnimationType"):
        for name in list(sys.modules):
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
                sys.modules.pop(name, None)
    qframe = sys.modules.get("qframelesswindow")
    if qframe is not None and not hasattr(qframe, "WindowEffect"):
        for name in list(sys.modules):
            if name == "qframelesswindow" or name.startswith("qframelesswindow."):
                sys.modules.pop(name, None)
    sys.modules.pop("substitute.presentation.widgets.cursor_tooltip_filter", None)


def _wheel_event(widget: QWidget, *, angle_delta_y: int) -> QWheelEvent:
    """Build one wheel event at the center of a widget."""

    local_point = widget.rect().center()
    return QWheelEvent(
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


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
        tabbar.deleteLater()
        stack.deleteLater()
        _ensure_qapp().processEvents()


def test_cubestack_swap_item_reorders_real_qt_items_and_emits_signal() -> None:
    """Real CubeStack widget should reorder via _swapItem and emit its current signal payload."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.addTab("a", "A")
    stack.addTab("b", "B")
    stack.addTab("c", "C")
    stack.setCurrentIndex(2)
    moved_calls: list[tuple[int, int]] = []
    stack.cubeMoved.connect(
        lambda from_idx, to_idx: moved_calls.append((from_idx, to_idx))
    )

    stack._swapItem(1)

    assert [item.routeKey() for item in stack.items] == ["a", "c", "b"]
    assert stack.currentIndex() == 1
    assert moved_calls == [(1, 1)]


def test_cubestack_mouse_release_emits_tab_mouse_released_when_not_dragging() -> None:
    """Real CubeStack release path should emit current index even without drag."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.addTab("a", "A")
    stack.setCurrentIndex(0)
    stack.setMovable(True)
    stack.isDraging = False
    released_calls: list[int] = []
    stack.tabMouseReleased.connect(lambda index: released_calls.append(index))

    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(4, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    stack.mouseReleaseEvent(event)

    assert released_calls == [0]


def test_cubestack_tab_presentation_updates_metadata_and_tooltip() -> None:
    """Real CubeStack items should store primary text, subtitle, and tooltip together."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.addTab("a", "Loading")

    stack.setTabPresentation(
        0,
        primary_text="Text to Image",
        secondary_text="v1.1.1 · base-cubes",
        tooltip_text="Text to Image",
    )

    item = stack.tabItem(0)
    assert item.text() == "Text to Image"
    assert item.toolTip() == "Text to Image"
    assert item.secondaryText() == "v1.1.1 · base-cubes"
    assert item._tooltip_filter is not None
    assert item._tooltip_filter._show_delay_ms == 1000

    stack.close()
    stack.deleteLater()


def test_cubestack_tab_bypassed_updates_item_visual_state() -> None:
    """Real CubeStack items should store cube-level bypass presentation state."""

    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.addTab("a", "Text to Image")

    stack.setTabBypassed(0, True)

    item = stack.tabItem(0)
    assert item.isBypassed() is True
    assert item._visual_state().bypassed is True

    stack.close()
    stack.deleteLater()


def test_cube_item_rename_uses_alias_editor_and_keeps_display_text() -> None:
    """Cube rename should use the cube alias editor without mutating display text."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    stack.show()
    app.processEvents()

    first._startRename()
    app.processEvents()

    assert first.alias_editor.isVisible()
    assert first.rename_editor.isHidden()
    assert first.text() == "SDXL/Text to Image"
    assert first.alias_editor.text() == "SDXL/Text to Image"
    assert first._visual_state().editing_primary_text is True

    stack.close()
    stack.deleteLater()


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
    tabbar.deleteLater()


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
    tabbar.deleteLater()


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
    tabbar.deleteLater()


def test_cube_item_alias_editor_geometry_matches_primary_text_row() -> None:
    """Alias editor geometry should match the painted primary cube text row."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    item_mod = importlib.import_module("substitute.presentation.workflows.cube_item")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    stack.show()
    app.processEvents()

    first.setCloseButtonDisplayMode(mod.CubeCloseButtonDisplayMode.ALWAYS)
    first._sync_close_button_visibility()
    assert not first.closeButton.isHidden()
    app.processEvents()

    first._startRename()
    app.processEvents()

    expected_primary_rect, _secondary_rect = item_mod.CubeCardVisual.text_row_rects(
        first._textRect()
    )
    assert first.closeButton.isHidden()
    assert first.alias_editor.geometry() == expected_primary_rect.toAlignedRect()

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_accept_emits_existing_stack_signal() -> None:
    """Committing the alias editor should use the existing cube rename signal flow."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    rename_calls: list[tuple[str, str]] = []
    stack.cubeRenameRequested.connect(
        lambda old_key, new_name: rename_calls.append((old_key, new_name))
    )
    stack.show()
    app.processEvents()

    first._startRename()
    first.alias_editor.setText("Flux/Image to Image")
    QTest.keyClick(first.alias_editor, Qt.Key.Key_Return)

    assert rename_calls == [("a", "Flux/Image to Image")]
    assert first.alias_editor.isHidden()
    assert first.rename_editor.isHidden()

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_commits_when_card_background_is_clicked() -> None:
    """Clicking outside the primary text editor should commit the cube alias."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    rename_calls: list[tuple[str, str]] = []
    stack.cubeRenameRequested.connect(
        lambda old_key, new_name: rename_calls.append((old_key, new_name))
    )
    stack.show()
    app.processEvents()

    first._startRename()
    first.alias_editor.setText("Flux/Image to Image")
    QTest.mouseClick(
        first,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(4, first.height() // 2),
    )
    app.processEvents()

    assert rename_calls == [("a", "Flux/Image to Image")]
    assert first.alias_editor.isHidden()
    assert first.alias_editor.isEditing() is False

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_escape_leaves_alias_unchanged() -> None:
    """Cancelling cube alias editing should leave the item and stack signal untouched."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    rename_calls: list[tuple[str, str]] = []
    stack.cubeRenameRequested.connect(
        lambda old_key, new_name: rename_calls.append((old_key, new_name))
    )
    stack.show()
    app.processEvents()

    first._startRename()
    first.alias_editor.setText("Flux/Image to Image")
    QTest.keyClick(first.alias_editor, Qt.Key.Key_Escape)

    assert first.text() == "SDXL/Text to Image"
    assert first.alias_editor.text() == "SDXL/Text to Image"
    assert first.alias_editor.isHidden()
    assert rename_calls == []

    stack.close()
    stack.deleteLater()


def test_cube_stack_begin_alias_editing_requires_expanded_item() -> None:
    """Route-key editing should start only after compact mode is cleared."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    stack.show()
    app.processEvents()

    stack.setCompact(True)
    app.processEvents()

    assert stack.begin_alias_editing("a") is False
    assert first.alias_editor.isHidden()

    stack.finishCompactTransition(False)
    app.processEvents()

    assert stack.begin_alias_editing("a") is True
    assert first.alias_editor.isVisible()

    stack.close()
    stack.deleteLater()


def test_cube_alias_editing_finished_emits_original_route_key() -> None:
    """Alias edit completion should preserve the route key captured at edit start."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    finished: list[str] = []
    stack.aliasEditingFinished.connect(finished.append)
    stack.show()
    app.processEvents()

    assert stack.begin_alias_editing("a") is True
    first.setRouteKey("resolved-after-commit")
    first.alias_editor.cancel()
    app.processEvents()

    assert finished == ["a"]

    stack.close()
    stack.deleteLater()


def test_cubestack_compact_mode_updates_existing_and_future_items() -> None:
    """Compact mode should propagate to current items and new tabs."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "A")

    stack.setCompact(True)
    second = stack.addTab("b", "B")

    assert stack.isCompact() is True
    assert stack.width() == mod.CUBE_STACK_COMPACT_WIDTH
    assert first.isCompact() is True
    assert second.isCompact() is True
    assert first.width() == mod.CUBE_ITEM_COMPACT_WIDTH
    assert second.width() == mod.CUBE_ITEM_COMPACT_WIDTH
    assert first.closeButton.isHidden()
    assert second.closeButton.isHidden()
    assert first.closeButton.isEnabled() is False

    first.setCloseButtonDisplayMode(mod.CubeCloseButtonDisplayMode.ALWAYS)
    first.enterEvent(QEvent(QEvent.Type.Enter))
    first.setSelected(True)

    assert first.closeButton.isHidden()
    assert first.closeButton.isEnabled() is False

    stack.setCompact(False)

    assert stack.isCompact() is False
    assert stack.width() == mod.CUBE_STACK_EXPANDED_WIDTH
    assert first.isCompact() is False
    assert second.isCompact() is False
    assert first.width() == mod.CUBE_ITEM_EXPANDED_WIDTH
    assert second.width() == mod.CUBE_ITEM_EXPANDED_WIDTH
    assert first.closeButton.isEnabled() is True
    assert first.closeButton.isHidden() is False

    stack.close()
    stack.deleteLater()


def test_cubestack_transition_api_matches_final_compact_states() -> None:
    """Transition finish should leave the same final state as immediate compact mode."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "A")
    second = stack.addTab("b", "B")

    first._startRename()
    assert not first.alias_editor.isHidden()
    first.rename_editor.setVisible(True)
    stack.beginCompactTransition(True)
    stack.applyCompactTransition(
        stack_width=mod.CUBE_STACK_COMPACT_WIDTH,
        item_width=mod.CUBE_ITEM_COMPACT_WIDTH,
        compact_progress=1.0,
    )
    stack.finishCompactTransition(True)

    assert stack.isCompact() is True
    assert first.isCompact() is True
    assert second.isCompact() is True
    assert first.width() == mod.CUBE_ITEM_COMPACT_WIDTH
    assert second.width() == mod.CUBE_ITEM_COMPACT_WIDTH
    assert first.compact_progress() == 1.0
    assert second.compact_progress() == 1.0
    assert first.alias_editor.isHidden()
    assert first.rename_editor.isHidden()
    assert first.closeButton.isHidden()
    assert first.closeButton.isEnabled() is False

    stack.beginCompactTransition(False)
    stack.applyCompactTransition(
        stack_width=mod.CUBE_STACK_EXPANDED_WIDTH,
        item_width=mod.CUBE_ITEM_EXPANDED_WIDTH,
        compact_progress=0.0,
    )
    stack.finishCompactTransition(False)

    assert stack.isCompact() is False
    assert first.isCompact() is False
    assert second.isCompact() is False
    assert first.width() == mod.CUBE_ITEM_EXPANDED_WIDTH
    assert second.width() == mod.CUBE_ITEM_EXPANDED_WIDTH
    assert first.compact_progress() == 0.0
    assert second.compact_progress() == 0.0
    assert first.closeButton.isEnabled() is True

    stack.close()
    stack.deleteLater()


def test_rendered_expanded_progress_owns_cube_close_visibility() -> None:
    """Rendered geometry should expose close even before compact lifecycle commits."""

    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    stack = mod.CubeStack(None)
    item = stack.addTab("a", "A")
    item.setCloseButtonDisplayMode(mod.CubeCloseButtonDisplayMode.ON_HOVER)
    item.setSelected(True)

    item.setCompact(True)
    item.beginCompactTransition(False)
    item.setFixedWidth(mod.CUBE_ITEM_EXPANDED_WIDTH)
    item.setCompactProgress(0.0)

    assert item.isCompact() is True
    assert item._compact_transition_active is True
    assert item.compact_progress() == 0.0
    assert item.closeButton.isEnabled() is True
    assert item.closeButton.isHidden() is False

    stack.close()
    stack.deleteLater()


def test_cubestack_transition_keeps_items_and_add_placeholder_aligned() -> None:
    """Transition frames should keep cube items and the add placeholder aligned."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    item = stack.addTab("a", "A")
    stack.show()
    app.processEvents()

    stack.beginCompactTransition(True)
    for stack_width, item_width, progress in (
        (mod.CUBE_STACK_EXPANDED_WIDTH, mod.CUBE_ITEM_EXPANDED_WIDTH, 0.0),
        (
            round((mod.CUBE_STACK_EXPANDED_WIDTH + mod.CUBE_STACK_COMPACT_WIDTH) / 2),
            round((mod.CUBE_ITEM_EXPANDED_WIDTH + mod.CUBE_ITEM_COMPACT_WIDTH) / 2),
            0.5,
        ),
        (mod.CUBE_STACK_COMPACT_WIDTH, mod.CUBE_ITEM_COMPACT_WIDTH, 1.0),
    ):
        stack.applyCompactTransition(
            stack_width=stack_width,
            item_width=item_width,
            compact_progress=progress,
        )
        stack.itemLayout.activate()
        stack.widgetLayout.activate()
        stack.hBoxLayout.activate()
        app.processEvents()

        assert item.x() == mod.CUBE_STACK_EDGE_INSET
        assert (
            item.mapToGlobal(QPoint(0, 0)).x() - stack.mapToGlobal(QPoint(0, 0)).x()
            == mod.CUBE_STACK_EDGE_INSET
        )
        assert stack.addPlaceholder.x() == mod.CUBE_STACK_EDGE_INSET
        assert stack.addPlaceholder.width() == item_width
        assert stack.addPlaceholder.height() == mod.CUBE_ITEM_HEIGHT
        assert (
            stack.addPlaceholder.mapToGlobal(QPoint(0, 0)).x()
            - stack.mapToGlobal(QPoint(0, 0)).x()
            == mod.CUBE_STACK_EDGE_INSET
        )

    stack.close()
    stack.deleteLater()


def test_cubestack_empty_transition_keeps_add_placeholder_aligned() -> None:
    """Empty stacks should align the add placeholder without item layout width."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.show()
    app.processEvents()

    stack.beginCompactTransition(True)
    for stack_width, item_width, progress in (
        (mod.CUBE_STACK_EXPANDED_WIDTH, mod.CUBE_ITEM_EXPANDED_WIDTH, 0.0),
        (
            round((mod.CUBE_STACK_EXPANDED_WIDTH + mod.CUBE_STACK_COMPACT_WIDTH) / 2),
            round((mod.CUBE_ITEM_EXPANDED_WIDTH + mod.CUBE_ITEM_COMPACT_WIDTH) / 2),
            0.5,
        ),
        (mod.CUBE_STACK_COMPACT_WIDTH, mod.CUBE_ITEM_COMPACT_WIDTH, 1.0),
    ):
        stack.applyCompactTransition(
            stack_width=stack_width,
            item_width=item_width,
            compact_progress=progress,
        )
        stack.widgetLayout.activate()
        stack.hBoxLayout.activate()
        app.processEvents()

        assert stack.addPlaceholder.x() == mod.CUBE_STACK_EDGE_INSET
        assert stack.addPlaceholder.width() == item_width
        assert stack.addPlaceholder.height() == mod.CUBE_ITEM_HEIGHT
        assert (
            stack.addPlaceholder.mapToGlobal(QPoint(0, 0)).x()
            - stack.mapToGlobal(QPoint(0, 0)).x()
            == mod.CUBE_STACK_EDGE_INSET
        )

    stack.close()
    stack.deleteLater()


def test_cubestack_add_placeholder_click_emits_add_request() -> None:
    """Clicking the final placeholder card should request the cube picker."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    calls: list[bool] = []
    stack.cubeAddRequested.connect(lambda: calls.append(True))
    stack.show()
    app.processEvents()

    QTest.mouseClick(
        stack.addPlaceholder,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        stack.addPlaceholder.rect().center(),
    )

    assert calls == [True]
    assert stack.addPlaceholder.objectName() == "cubeStackAddPlaceholder"
    assert stack.addPlaceholder.isPlusVisible() is True

    stack.close()
    stack.deleteLater()


def test_cubeitem_compact_progress_clamps_and_drives_geometry_helpers() -> None:
    """Cube item transition progress should expose deterministic paint geometry."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    item_mod = importlib.import_module("substitute.presentation.workflows.cube_item")

    item = item_mod.CubeItem("A", None, item_mod.FluentIcon.ADD)

    item.setCompactProgress(-1.0)
    assert item.compact_progress() == 0.0
    assert item._icon_x() == mod.CUBE_ITEM_ICON_X
    assert (
        mod.CUBE_ITEM_COMPACT_WIDTH - mod.CUBE_ITEM_ICON_SIZE_COMPACT
        == mod.CUBE_ITEM_ICON_X * 2
    )
    assert item._text_opacity(0.0) == 1.0

    item.setFixedWidth(mod.CUBE_ITEM_COMPACT_WIDTH)
    item.setCompactProgress(2.0)
    assert item.compact_progress() == 1.0
    assert item._icon_x() == mod.CUBE_ITEM_ICON_X
    assert item._text_opacity(1.0) == 0.0

    for width in (
        mod.CUBE_ITEM_EXPANDED_WIDTH,
        round((mod.CUBE_ITEM_EXPANDED_WIDTH + mod.CUBE_ITEM_COMPACT_WIDTH) / 2),
        mod.CUBE_ITEM_COMPACT_WIDTH,
    ):
        item.setFixedWidth(width)
        for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
            item.setCompactProgress(progress)
            assert item._icon_x() == mod.CUBE_ITEM_ICON_X

    mid_rect = item._textRectForWidth(mod.CUBE_ITEM_EXPANDED_WIDTH, 0.5)
    assert mid_rect.width() > 0

    item.close()
    item.deleteLater()


def test_cube_item_context_menu_exposes_duplicate_and_remove_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube item context menu should expose duplicate and X-independent removal."""
    _ensure_qapp()
    _clear_gui_stubs()
    item_mod = importlib.import_module("substitute.presentation.workflows.cube_item")

    class FakeAction:
        """Capture one rendered cube item context-menu action."""

        def __init__(self, item: MenuItem) -> None:
            """Store item state for assertions and trigger dispatch."""

            self._item = item

        def text(self) -> str:
            """Return the rendered action label."""

            return self._item.label

        def trigger(self) -> None:
            """Invoke the rendered action callback."""

            if self._item.callback is not None:
                self._item.callback()

    class FakeRoundMenu:
        """Capture actions added to a cube item context menu."""

        instances: list["FakeRoundMenu"] = []

        def __init__(self, *, parent: object) -> None:
            self.parent = parent
            self.actions: list[FakeAction] = []
            self.exec_calls: list[object] = []
            FakeRoundMenu.instances.append(self)

        def addAction(self, action: FakeAction) -> None:
            """Record one menu action."""

            self.actions.append(action)

        def exec(self, global_pos: object, **kwargs: object) -> None:
            """Record menu execution without showing a popup."""

            self.exec_calls.append((global_pos, kwargs))

    class FakeRenderer:
        """Render shared menu models into fake cube context menus."""

        def __init__(self, *, parent: object) -> None:
            """Store the menu parent for fake menu construction."""

            self._parent = parent

        def render(self, model: MenuModel) -> FakeRoundMenu:
            """Return a fake menu populated from shared menu items."""

            menu = FakeRoundMenu(parent=self._parent)
            for entry in model.entries:
                if isinstance(entry, MenuItem):
                    menu.addAction(FakeAction(entry))
            return menu

    monkeypatch.setattr(item_mod, "QFluentMenuRenderer", FakeRenderer)

    item = item_mod.CubeItem("A", None, None)
    closed_calls: list[bool] = []
    duplicate_calls: list[bool] = []
    item.closed.connect(lambda: closed_calls.append(True))
    item.duplicateRequested.connect(lambda _item: duplicate_calls.append(True))

    item._showContextMenu(QPoint(0, 0))

    menu = FakeRoundMenu.instances[0]
    assert [action.text() for action in menu.actions] == [
        "Rename",
        "Duplicate",
        "Bypass",
        "Remove",
    ]

    menu.actions[1].trigger()
    menu.actions[3].trigger()

    assert duplicate_calls == [True]
    assert closed_calls == [True]

    item.close()
    item.deleteLater()


def test_cube_item_close_button_uses_square_hover_target() -> None:
    """Cube X button hover chrome should be a tight square around the icon."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    item = mod.CubeItem("A", None, None)

    assert item.closeButton.width() == mod.CUBE_ITEM_CLOSE_BUTTON_SIZE
    assert item.closeButton.height() == mod.CUBE_ITEM_CLOSE_BUTTON_SIZE

    item.close()
    item.deleteLater()


def test_cubestack_wheel_reroutes_when_stack_has_no_scroll_range() -> None:
    """CubeStack should yield wheel input when its content does not need scrolling."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.resize(200, 220)
    stack.addTab("a", "A")
    stack.show()
    app.processEvents()
    rerouted: list[QWheelEvent] = []
    stack.cubeStackWheelRerouteRequested.connect(rerouted.append)

    event = _wheel_event(stack.viewport(), angle_delta_y=-120)
    stack.wheelEvent(event)

    assert stack.verticalScrollBar().maximum() == 0
    assert rerouted == [event]
    assert event.isAccepted()

    stack.close()
    stack.deleteLater()


def test_cubestack_indicator_realign_timer_is_destroyed_with_stack() -> None:
    """Deferred indicator work must not outlive a replaced cube-stack surface."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    import shiboken6

    stack = mod.CubeStack(None)
    stack.addTab("a", "A")
    timer = stack._indicator_realign_timer

    assert timer.parent() is stack
    assert timer.isSingleShot()
    assert timer.isActive()

    stack.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    assert not shiboken6.isValid(timer)


def test_cubestack_indicator_realign_ignores_deleted_content_view() -> None:
    """A stale layout tick must stop when its owned content view was deleted."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    import shiboken6

    stack = mod.CubeStack(None)
    stack._indicator_realign_timer.stop()
    detached_view = stack.takeWidget()
    assert detached_view is stack.view
    detached_view.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert not shiboken6.isValid(detached_view)

    stack._complete_indicator_realign()

    stack.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_cubestack_wheel_stays_owned_when_stack_can_scroll_at_boundary() -> None:
    """Scrollable CubeStack should not reroute, even when currently at a boundary."""
    app = _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.resize(200, 80)
    for index in range(20):
        stack.addTab(str(index), f"Cube {index}")
    stack.show()
    app.processEvents()
    rerouted: list[QWheelEvent] = []
    stack.cubeStackWheelRerouteRequested.connect(rerouted.append)
    stack.verticalScrollBar().setValue(stack.verticalScrollBar().maximum())

    event = _wheel_event(stack.viewport(), angle_delta_y=-120)
    stack.wheelEvent(event)

    assert stack.verticalScrollBar().maximum() > 0
    assert rerouted == []
    assert event.isAccepted()

    stack.close()
    stack.deleteLater()
