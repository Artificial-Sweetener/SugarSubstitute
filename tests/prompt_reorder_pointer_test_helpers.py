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

"""Drive logical prompt reorder regions through their single Qt input surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from substitute.presentation.editor.prompt_editor.overlays import SegmentReorderOverlay


@dataclass(frozen=True, slots=True)
class PromptReorderPointerTarget:
    """Adapt one logical pointer region for concise interaction assertions."""

    overlay: SegmentReorderOverlay
    segment_index: int

    def rect(self) -> QRect:
        """Return overlay-local interaction bounds."""

        return self.overlay.pointer_region_rects()[self.segment_index]

    def geometry(self) -> QRect:
        """Return overlay-local interaction bounds."""

        return self.rect()

    def width(self) -> int:
        """Return the current interaction width."""

        return self.rect().width()

    def height(self) -> int:
        """Return the current interaction height."""

        return self.rect().height()

    def mapToGlobal(self, point: QPoint) -> QPoint:  # noqa: N802
        """Map an overlay-local point to global coordinates."""

        return self.overlay.mapToGlobal(point)

    def mapFromGlobal(self, point: QPoint) -> QPoint:  # noqa: N802
        """Map a global point to overlay-local coordinates."""

        return self.overlay.mapFromGlobal(point)

    def property(self, name: str) -> object:
        """Return diagnostic state exposed by the logical region owner."""

        region = self.overlay.pointer_region(self.segment_index)
        properties: dict[str, object] = {
            "segmentIndex": self.segment_index,
            "segmentText": region.drag_proxy_text(),
            "active": region.active,
            "dragging": region.dragging,
            "hovered": region.hovered,
        }
        return properties.get(name)

    def cursor(self) -> QCursor:
        """Return the logical cursor associated with this region."""

        return QCursor(self.overlay.pointer_region(self.segment_index).cursor_shape)

    def leading_global_point(self) -> QPoint:
        """Return a stable global drop point near the region's leading edge."""

        rect = self.rect()
        return self.overlay.mapToGlobal(QPoint(rect.left() + 4, rect.center().y()))

    def trailing_global_point(self) -> QPoint:
        """Return a stable global drop point near the region's trailing edge."""

        rect = self.rect()
        return self.overlay.mapToGlobal(QPoint(rect.right() - 3, rect.center().y()))


def prompt_reorder_pointer_targets(
    overlay: object,
) -> list[PromptReorderPointerTarget]:
    """Return visible logical regions sorted by their rendered position."""

    typed_overlay = cast(SegmentReorderOverlay, overlay)
    targets = [
        PromptReorderPointerTarget(typed_overlay, segment_index)
        for segment_index in typed_overlay.pointer_region_rects()
    ]
    return sorted(
        targets,
        key=lambda target: (target.rect().top(), target.rect().left()),
    )


def prompt_reorder_pointer_target(
    overlay: object,
    segment_index: int,
) -> PromptReorderPointerTarget:
    """Return one visible logical region by stable segment index."""

    typed_overlay = cast(SegmentReorderOverlay, overlay)
    if segment_index not in typed_overlay.pointer_region_rects():
        raise AssertionError(f"Missing chip for segment index {segment_index}.")
    return PromptReorderPointerTarget(typed_overlay, segment_index)


def drag_prompt_reorder_target_to_global(
    target: PromptReorderPointerTarget,
    *,
    global_target: QPoint,
) -> None:
    """Drag one logical region to a global target through the real overlay."""

    start = target.rect().center()
    destination = target.overlay.mapFromGlobal(global_target)
    QTest.mousePress(target.overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(target.overlay, destination, 10)
    QTest.mouseRelease(
        target.overlay,
        Qt.MouseButton.LeftButton,
        pos=destination,
        delay=10,
    )


__all__ = [
    "PromptReorderPointerTarget",
    "drag_prompt_reorder_target_to_global",
    "prompt_reorder_pointer_target",
    "prompt_reorder_pointer_targets",
]
