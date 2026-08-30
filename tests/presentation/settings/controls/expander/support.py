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

"""Synchronize Settings expander tests with owned Qt animations."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from substitute.presentation.settings.settings_expander import SettingsExpander


def application() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def motion_animations(
    expander: SettingsExpander,
) -> tuple[QPropertyAnimation, QPropertyAnimation]:
    """Return the motion owners used only to synchronize animation proof."""

    content = cast(Any, expander)._content_offset_animation
    chevron = cast(Any, expander)._chevron_animation
    assert isinstance(content, QPropertyAnimation)
    assert isinstance(chevron, QPropertyAnimation)
    return content, chevron


def wait_for_motion(expander: SettingsExpander) -> None:
    """Wait for the owning animation signal with a bounded failure timeout."""

    animations = motion_animations(expander)
    finished = tuple(QSignalSpy(animation.finished) for animation in animations)
    for animation, spy in zip(animations, finished, strict=True):
        if animation.state() is QAbstractAnimation.State.Running and spy.count() == 0:
            assert spy.wait(2_000), "Settings expander motion did not finish"
