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

"""Cube stack compact-transition contracts."""

from __future__ import annotations

import importlib

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from tests.presentation.workflows.qt_support import _ensure_qapp


def test_cubestack_compact_mode_updates_existing_and_future_items() -> None:
    """Compact mode should propagate to current items and new tabs."""
    _ensure_qapp()
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
