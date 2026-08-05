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

"""Own interruptible show and hide motion for the Contextual Toolbar shell."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from substitute.presentation.motion.fluent_motion import (
    CONTEXTUAL_TOOLBAR_DURATION_MS,
    resolve_motion_duration,
)


class ContextualToolbarSurfaceMotion(QObject):
    """Retarget shell opacity without retaining nested graphics effects."""

    def __init__(self, surface: QWidget) -> None:
        """Initialize terminal visibility without installing a paint effect."""

        super().__init__(surface)
        self._surface = surface
        self._effect: QGraphicsOpacityEffect | None = None
        self._animation: QPropertyAnimation | None = None
        self._generation = 0
        self._target_visible = False
        self._completion: Callable[[], None] | None = None

    @property
    def target_visible(self) -> bool:
        """Return the latest requested terminal shell visibility."""

        return self._target_visible

    def set_visible(
        self,
        visible: bool,
        *,
        finished: Callable[[], None] | None = None,
    ) -> None:
        """Animate toward the requested visibility or settle immediately."""

        if visible == self._target_visible:
            if finished is not None:
                self._completion = finished
            animation = self._animation
            if (
                animation is not None
                and animation.state() is QAbstractAnimation.State.Running
            ):
                return
            self._settle_terminal(visible, self._generation)
            return

        current_opacity = self._current_opacity()
        self._target_visible = visible
        self._completion = finished
        self._generation += 1
        generation = self._generation
        self._stop_animation()
        duration = resolve_motion_duration(CONTEXTUAL_TOOLBAR_DURATION_MS)
        if visible:
            self._surface.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                False,
            )
            self._surface.show()
        else:
            self._surface.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
        if duration == 0:
            self._settle_terminal(visible, generation)
            return

        effect = self._install_effect(current_opacity)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setStartValue(current_opacity)
        animation.setEndValue(1.0 if visible else 0.0)
        animation.setDuration(duration)
        animation.setEasingCurve(
            QEasingCurve.Type.OutCubic if visible else QEasingCurve.Type.InCubic
        )
        animation.finished.connect(
            partial(self._finish, generation, visible, animation)
        )
        self._animation = animation
        animation.start(QAbstractAnimation.DeletionPolicy.KeepWhenStopped)

    def settle_visible(self) -> None:
        """Finish an entering shell before child page crossfade effects begin."""

        if not self._target_visible:
            return
        self._generation += 1
        generation = self._generation
        self._stop_animation()
        self._settle_terminal(True, generation)

    def _finish(
        self,
        generation: int,
        visible: bool,
        animation: QPropertyAnimation,
    ) -> None:
        """Apply terminal visibility only for the latest request generation."""

        if generation != self._generation:
            animation.deleteLater()
            return
        self._animation = None
        self._settle_terminal(visible, generation)
        animation.deleteLater()

    def _settle_terminal(self, visible: bool, generation: int) -> None:
        """Publish one terminal state and detach the completed paint effect."""

        effect = self._effect
        if effect is not None:
            effect.setOpacity(1.0 if visible else 0.0)
        self._surface.setVisible(visible)
        self._detach_effect()
        self._complete(generation)

    def _install_effect(self, opacity: float) -> QGraphicsOpacityEffect:
        """Install the sole temporary shell effect at live rendered opacity."""

        effect = self._effect
        if effect is None:
            effect = QGraphicsOpacityEffect(self._surface)
            self._surface.setGraphicsEffect(effect)
            self._effect = effect
        effect.setOpacity(opacity)
        return effect

    def _detach_effect(self) -> None:
        """Remove terminal shell effects so child effects cannot nest beneath them."""

        if self._effect is None:
            return
        self._surface.setGraphicsEffect(None)  # type: ignore[arg-type]
        self._effect = None

    def _current_opacity(self) -> float:
        """Return the live effect opacity or terminal QWidget visibility."""

        effect = self._effect
        if effect is not None:
            return float(effect.opacity())
        return 1.0 if self._surface.isVisible() else 0.0

    def _stop_animation(self) -> None:
        """Stop and release the current shell interpolation."""

        animation = self._animation
        self._animation = None
        if animation is not None:
            animation.stop()
            animation.deleteLater()

    def _complete(self, generation: int) -> None:
        """Run the latest terminal callback exactly once."""

        if generation != self._generation:
            return
        completion = self._completion
        self._completion = None
        if completion is not None:
            completion()


__all__ = ["ContextualToolbarSurfaceMotion"]
