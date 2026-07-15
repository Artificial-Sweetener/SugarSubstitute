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

"""Expose prompt-editor debouncing through shared Qt execution adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.presentation.qt.execution import QtDebouncer


class PromptEditorDebouncer(Protocol):
    """Coalesce prompt-editor request callbacks before they submit work."""

    @property
    def is_pending(self) -> bool:
        """Return whether a callback is waiting for timer delivery."""

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Schedule the latest callback for debounced delivery."""

    def flush(self, *, reason: str) -> bool:
        """Run the pending callback immediately when one exists."""

    def cancel(self, *, reason: str) -> bool:
        """Drop the pending callback when one exists."""


class QtPromptEditorDebouncer(QtDebouncer):
    """Coalesce prompt-editor requests through the shared Qt debouncer."""


__all__ = [
    "PromptEditorDebouncer",
    "QtPromptEditorDebouncer",
]
