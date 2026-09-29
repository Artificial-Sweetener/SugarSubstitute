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

"""Drive interruptible editor scroll motion without owning reveal policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QObject, QPropertyAnimation

from substitute.presentation.motion import (
    TRANSFORM_EASING_CURVE,
    restart_property_animation,
    stop_animation,
)


class RevealScrollBarProtocol(Protocol):
    """Describe the animated scrollbar boundary."""

    def value(self) -> int:
        """Return the current scrollbar value."""

    def setValue(self, value: int) -> None:  # noqa: N802
        """Set the current scrollbar value."""


class CubeRevealScrollDriver:
    """Own cube and input scrollbar animation lifetimes."""

    def __init__(self, parent: QObject, on_cube_settled: Callable[[], None]) -> None:
        """Store animation ownership and the cube-settlement callback."""

        self._parent = parent
        self._on_cube_settled = on_cube_settled
        self._cube_animation: QPropertyAnimation | None = None
        self._input_animation: QPropertyAnimation | None = None
        self._suppresses_visible_sync = False

    @property
    def suppresses_visible_sync(self) -> bool:
        """Return whether cube motion is temporarily suppressing scroll sync."""

        return self._suppresses_visible_sync

    def move_cube_scrollbar(
        self,
        scrollbar: RevealScrollBarProtocol,
        target_value: int,
        *,
        animated: bool,
        duration_ms: int,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Move the cube scrollbar while suppressing incidental visible-cube sync."""

        self._move(
            scrollbar,
            target_value,
            animated=animated,
            duration_ms=duration_ms,
            cube_navigation=True,
            on_finished=on_finished,
        )

    def move_input_scrollbar(
        self,
        scrollbar: RevealScrollBarProtocol,
        target_value: int,
        *,
        animated: bool,
        duration_ms: int,
    ) -> None:
        """Move the scrollbar to an input without suppressing visible-cube sync."""

        self._move(
            scrollbar,
            target_value,
            animated=animated,
            duration_ms=duration_ms,
            cube_navigation=False,
        )

    def cancel_cube_navigation(self) -> None:
        """Stop active cube navigation and publish its settled scroll state."""

        animation = self._cube_animation
        self._cube_animation = None
        self._suppresses_visible_sync = False
        stop_animation(animation)
        if animation is not None:
            self._on_cube_settled()

    def _move(
        self,
        scrollbar: RevealScrollBarProtocol,
        target_value: int,
        *,
        animated: bool,
        duration_ms: int,
        cube_navigation: bool,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Replace one owned animation or apply its final value immediately."""

        animation_attr = "_cube_animation" if cube_navigation else "_input_animation"
        existing = cast(QPropertyAnimation | None, getattr(self, animation_attr))
        stop_animation(existing)
        setattr(self, animation_attr, None)

        if not animated:
            if cube_navigation:
                self._suppresses_visible_sync = True
            scrollbar.setValue(target_value)
            if cube_navigation:
                self._suppresses_visible_sync = False
                self._on_cube_settled()
            if on_finished is not None:
                on_finished()
            return

        animation = QPropertyAnimation(
            cast(QObject, scrollbar),
            b"value",
            self._parent,
        )
        setattr(self, animation_attr, animation)
        if cube_navigation:
            self._suppresses_visible_sync = True

        def finish_animation() -> None:
            """Publish settlement only for the animation that still owns the slot."""

            if getattr(self, animation_attr) is not animation:
                return
            setattr(self, animation_attr, None)
            if cube_navigation:
                self._suppresses_visible_sync = False
                self._on_cube_settled()
            if on_finished is not None:
                on_finished()

        animation.finished.connect(finish_animation)
        restart_property_animation(
            animation,
            start_value=scrollbar.value(),
            end_value=target_value,
            duration_ms=duration_ms,
            easing_curve=TRANSFORM_EASING_CURVE,
        )


__all__ = ["CubeRevealScrollDriver", "RevealScrollBarProtocol"]
