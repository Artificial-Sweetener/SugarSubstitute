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

"""Expose prompt-editor main-thread dispatch through shared Qt execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject

from substitute.presentation.qt.execution import QtOwnerThreadDispatcher


class PromptEditorMainThreadDispatcher(Protocol):
    """Publish prompt-editor callbacks through an owner-thread boundary."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Queue one prompt-safe publication callback for Qt-thread delivery."""


class QtPromptEditorMainThreadDispatcher(QtOwnerThreadDispatcher):
    """Dispatch prompt-editor publications through shared Qt queued delivery."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Create a dispatcher bound to the optional Qt parent lifetime."""

        super().__init__(receiver=parent, parent=parent)


__all__ = [
    "PromptEditorMainThreadDispatcher",
    "QtPromptEditorMainThreadDispatcher",
]
