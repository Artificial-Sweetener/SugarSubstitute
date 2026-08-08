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

"""Coordinate regional-mask row selection motion as one transition."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QEasingCurve, QObject, QVariantAnimation, Signal

_SELECTION_DURATION_MS = 220


@dataclass(frozen=True, slots=True)
class RegionalMaskSelectionAnimationTarget:
    """Apply and settle one participant in a shared selection transition."""

    apply_progress: Callable[[float], None]
    finish: Callable[[], None]


class RegionalMaskSelectionAnimator(QObject):
    """Drive outgoing contraction and incoming expansion from one clock."""

    finished = Signal()

    def __init__(self, parent: QObject) -> None:
        """Create one reusable, interruptible selection animation."""

        super().__init__(parent)
        self._targets: tuple[RegionalMaskSelectionAnimationTarget, ...] = ()
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(_SELECTION_DURATION_MS)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._apply_value)
        self._animation.finished.connect(self._finish_targets)

    @property
    def is_running(self) -> bool:
        """Return whether a coordinated row transition is active."""

        return self._animation.state() is QVariantAnimation.State.Running

    def start(
        self,
        targets: Sequence[RegionalMaskSelectionAnimationTarget],
    ) -> None:
        """Start all supplied row transitions on the same animation clock."""

        self.complete()
        self._targets = tuple(targets)
        if not self._targets:
            self.finished.emit()
            return
        for target in self._targets:
            target.apply_progress(0.0)
        self._animation.start()

    def complete(self) -> None:
        """Settle an interrupted transition before its rows are reused or removed."""

        if not self._targets:
            return
        self._animation.stop()
        self._finish_targets()

    def _apply_value(self, value: object) -> None:
        """Forward one normalized Qt animation sample to every participant."""

        progress = cast(float, value)
        for target in self._targets:
            target.apply_progress(progress)

    def _finish_targets(self) -> None:
        """Settle every participant exactly once and publish completion."""

        targets = self._targets
        if not targets:
            return
        self._targets = ()
        for target in targets:
            target.finish()
        self.finished.emit()


__all__ = [
    "RegionalMaskSelectionAnimationTarget",
    "RegionalMaskSelectionAnimator",
]
