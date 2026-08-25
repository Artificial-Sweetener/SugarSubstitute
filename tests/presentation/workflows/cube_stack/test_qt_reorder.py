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

"""Cube stack Qt reorder and presentation contracts."""

from __future__ import annotations

import importlib

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from tests.presentation.workflows.qt_support import _ensure_qapp


def test_cubestack_swap_item_reorders_real_qt_items_and_emits_signal() -> None:
    """Real CubeStack widget should reorder via _swapItem and emit its current signal payload."""
    _ensure_qapp()
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


def test_cubestack_drag_release_finalizes_before_post_drag_signal() -> None:
    """Drag release should finalize layout before publishing completion signals."""
    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    stack = mod.CubeStack(None)
    stack.addTab("a", "A")
    stack.setCurrentIndex(0)
    stack.setMovable(True)
    stack.isDraging = True
    events: list[str] = []
    stack._adjustLayout = lambda: events.append("layout")
    stack.cubeMoveFinished.connect(lambda: events.append("move-finished"))
    stack.tabMouseReleased.connect(lambda _index: events.append("released"))
    event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(4, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    stack.mouseReleaseEvent(event)

    assert stack.isDraging is False
    assert events == ["layout", "move-finished", "released"]
    stack.close()
    stack.deleteLater()


def test_cubestack_tab_presentation_updates_metadata_and_tooltip() -> None:
    """Real CubeStack items should store primary text, subtitle, and tooltip together."""
    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.addTab("a", "Loading")

    stack.setTabPresentation(
        0,
        primary_text="Text to Image",
        secondary_text="v1.1.1 � base-cubes",
        tooltip_text="Text to Image",
    )

    item = stack.tabItem(0)
    assert item.text() == "Text to Image"
    assert item.toolTip() == "Text to Image"
    assert item.secondaryText() == "v1.1.1 � base-cubes"
    assert item._tooltip_filter is not None
    assert item._tooltip_filter.show_delay_ms == 1000

    stack.close()
    stack.deleteLater()


def test_cubestack_tab_bypassed_updates_item_visual_state() -> None:
    """Real CubeStack items should store cube-level bypass presentation state."""

    _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    stack.addTab("a", "Text to Image")

    stack.setTabBypassed(0, True)

    item = stack.tabItem(0)
    assert item.isBypassed() is True
    assert item._visual_state().bypassed is True

    stack.close()
    stack.deleteLater()
