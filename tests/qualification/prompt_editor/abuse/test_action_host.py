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

"""Test prompt-editor abuse action-host contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSizeF
import pytest

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from tools.prompt_editor_abuse import reorder_action_host
from tools.prompt_editor_abuse.reorder_action_host import (
    PromptReorderAbuseActionHost,
)


def test_reorder_host_resolves_destination_after_drag_start_settles_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Back-to-back drags should target geometry established at drag start."""

    class _Overlay:
        """Expose identity coordinate mapping for the harness action host."""

        def __init__(self) -> None:
            """Initialize the typed drag-base query returned to the host."""

            self.base_drag_layout: object | None = None

        def base_drag_layout_view(self) -> object | None:
            """Return the drag-base layout through the production query shape."""

            return self.base_drag_layout

        @staticmethod
        def mapToGlobal(point: QPoint) -> QPoint:
            """Return an identity-mapped global point."""

            return QPoint(point)

        @staticmethod
        def mapFromGlobal(point: QPoint) -> QPoint:
            """Return an identity-mapped overlay point."""

            return QPoint(point)

    overlay: Any = _Overlay()
    destination = PromptLineDropTarget(row_index=7, insertion_index=0)
    placement = SimpleNamespace(
        target=destination,
        hit_rect=QRectF(400.0, 50.0, 20.0, 20.0),
    )

    def placement_for_target(target: object) -> SimpleNamespace | None:
        """Return the one semantic placement owned by the fake snapshot."""

        return placement if target == destination else None

    overlay.base_drag_layout = SimpleNamespace(
        rows=(SimpleNamespace(row_index=7, chip_indices=(0,)),)
    )
    overlay.preview_build_facts = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(base_drag_layout_view=overlay.base_drag_layout)
    )
    overlay._geometry = SimpleNamespace(
        state=SimpleNamespace(
            placement_snapshot=SimpleNamespace(
                placement_for_target=placement_for_target
            )
        )
    )
    overlay._gesture = SimpleNamespace(
        state=SimpleNamespace(
            drag_intent_size=QSizeF(40.0, 20.0),
            drag_grab_offset=QPointF(20.0, 10.0),
        )
    )
    pressed = False
    drag_started = False

    def chip_target(_overlay: object, segment_index: int) -> SimpleNamespace:
        """Return destination geometry that moves when press settles animation."""

        if segment_index == 1:
            rect = QRect(10, 10, 40, 20)
        else:
            left = 300 if drag_started else 200 if pressed else 100
            rect = QRect(left, 50, 40, 20)
        return SimpleNamespace(overlay=_overlay, segment_index=segment_index, rect=rect)

    def press(*_args: object, **_kwargs: object) -> None:
        """Model production settling the previous animation on pointer press."""

        nonlocal pressed
        pressed = True

    def move(*_args: object, **_kwargs: object) -> None:
        """Model threshold crossing establishing stable base drag geometry."""

        nonlocal drag_started
        drag_started = True

    monkeypatch.setattr(reorder_action_host, "overlay_chip", chip_target)
    monkeypatch.setattr(
        reorder_action_host,
        "QTest",
        SimpleNamespace(mousePress=press, mouseMove=move),
    )
    monkeypatch.setattr(
        reorder_action_host,
        "QApplication",
        SimpleNamespace(startDragDistance=lambda: 10),
    )
    host = PromptReorderAbuseActionHost()

    host.reorder_drag_press(SimpleNamespace(_segment_overlay=overlay), "1:0")
    host.reorder_drag_threshold(SimpleNamespace(_segment_overlay=overlay))

    assert host._target == QPoint(410, 60)
