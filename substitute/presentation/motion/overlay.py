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

"""Paint a mouse-transparent snapshot overlay for structural motion."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from time import perf_counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QPaintEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from .models import MotionFrameTarget


class MotionOverlay(QWidget):
    """Paint one frozen pre-commit surface and its animated target snapshots."""

    def __init__(
        self,
        parent: QWidget,
        *,
        background: QPixmap,
        paint_observer: Callable[[float], None] | None = None,
    ) -> None:
        """Mount a non-interactive overlay above the supplied viewport."""

        super().__init__(parent)
        self._background = background
        self._targets: tuple[MotionFrameTarget, ...] = ()
        self._paint_observer = paint_observer
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(parent.rect())
        self.raise_()
        self.show()

    def set_frame(self, targets: Sequence[MotionFrameTarget]) -> None:
        """Publish one immutable frame and schedule its paint."""

        self._targets = tuple(targets)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the frozen old surface and interpolated target snapshots."""

        started_at = perf_counter()
        painter = QPainter(self)
        painter.setClipRegion(event.region())
        painter.drawPixmap(self.rect(), self._background)
        for target in self._targets:
            painter.save()
            painter.setOpacity(target.opacity)
            painter.drawPixmap(target.rect, target.snapshot, target.snapshot.rect())
            painter.restore()
        painter.end()
        if self._paint_observer is not None:
            self._paint_observer((perf_counter() - started_at) * 1000.0)


__all__ = ["MotionOverlay"]
