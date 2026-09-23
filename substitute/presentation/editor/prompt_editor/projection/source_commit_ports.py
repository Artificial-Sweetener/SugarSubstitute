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

"""Define focused presentation ports used while publishing source commits."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import SignalInstance
from PySide6.QtGui import QFont


class PromptSourceReplacementPointerSink(Protocol):
    """Clear pointer state made invalid by a committed source replacement."""

    def clear_pointer_state_for_source_replacement(self) -> None:
        """Clear pointer state after a committed source replacement."""


class PromptSourceCommitPresentationSink(Protocol):
    """Expose source-commit presentation effects outside core state."""

    textChanged: SignalInstance
    cursorPositionChanged: SignalInstance
    _caret_visibility_prompt_state_revision: int | None

    def font(self) -> QFont:
        """Return the current surface font."""

    def notify_implicit_parenthesis_authored(self, nesting_depth: int) -> None:
        """Publish authored nested implicit emphasis education."""


__all__ = [
    "PromptSourceCommitPresentationSink",
    "PromptSourceReplacementPointerSink",
]
