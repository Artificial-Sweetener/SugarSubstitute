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

"""Interpolate one Contextual Toolbar content-morph stage."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QSize,
    QVariantAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect

from substitute.presentation.motion.fluent_motion import TRANSFORM_EASING_CURVE


class ContextualToolbarContentStage(QObject):
    """Publish synchronized size and opacity samples for one morph phase."""

    def __init__(self, parent: QObject) -> None:
        """Create an idle stage with no retained animation group."""

        super().__init__(parent)
        self._group: QParallelAnimationGroup | None = None

    def start(
        self,
        *,
        current_size: QSize,
        apply_size: Callable[[QSize], None],
        effect: QGraphicsOpacityEffect,
        target_size: QSize,
        target_opacity: float,
        duration: int,
        finished: Callable[[], None],
    ) -> None:
        """Animate one phase from the currently rendered size and opacity."""

        self.stop()
        group = QParallelAnimationGroup(self)
        size_animation = QVariantAnimation(group)
        size_animation.setStartValue(QSize(current_size))
        size_animation.setEndValue(QSize(target_size))
        size_animation.setDuration(duration)
        size_animation.setEasingCurve(TRANSFORM_EASING_CURVE)
        size_animation.valueChanged.connect(
            lambda value: _publish_size(value, apply_size)
        )
        group.addAnimation(size_animation)

        opacity_animation = QVariantAnimation(group)
        opacity_animation.setStartValue(float(effect.opacity()))
        opacity_animation.setEndValue(float(target_opacity))
        opacity_animation.setDuration(duration)
        opacity_animation.setEasingCurve(
            QEasingCurve.Type.InCubic
            if target_opacity == 0.0
            else QEasingCurve.Type.OutCubic
        )
        opacity_animation.valueChanged.connect(effect.setOpacity)
        group.addAnimation(opacity_animation)
        group.finished.connect(finished)
        self._group = group
        group.start(QAbstractAnimation.DeletionPolicy.KeepWhenStopped)

    def stop(self) -> None:
        """Stop and release the current interpolation group."""

        group = self._group
        self._group = None
        if group is not None:
            group.stop()
            group.deleteLater()


def _publish_size(value: object, apply_size: Callable[[QSize], None]) -> None:
    """Forward only QSize samples emitted by QVariantAnimation."""

    if isinstance(value, QSize):
        apply_size(value)


__all__ = ["ContextualToolbarContentStage"]
