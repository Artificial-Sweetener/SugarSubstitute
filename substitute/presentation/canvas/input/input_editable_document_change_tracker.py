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

"""Track durable CuteCanvas changes for editable archive persistence."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol


class ChangeSignalPort(Protocol):
    """Describe one durable CuteCanvas change signal."""

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect one revision callback."""


class InputEditableDocumentChangeTracker:
    """Advance editable persistence state from authoritative change signals."""

    def __init__(
        self,
        *,
        changes: Iterable[ChangeSignalPort],
        mark_changed: Callable[[], None],
    ) -> None:
        """Connect each durable signal to the persistence lifecycle owner."""

        self._mark_changed = mark_changed
        for changed in changes:
            changed.connect(self._document_changed)

    def _document_changed(self, *_args: object) -> None:
        """Advance persistence state after one durable CuteCanvas mutation."""

        self._mark_changed()


__all__ = ["InputEditableDocumentChangeTracker"]
