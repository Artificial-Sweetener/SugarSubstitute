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

"""Define typed requests entering the prompt reorder use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)

PromptReorderKeyboardDirection = Literal["left", "right", "up", "down"]


@dataclass(frozen=True, slots=True)
class PromptReorderCommitIntent:
    """Request commit of the latest authoritative reorder snapshot."""

    reason: str
    snapshot: PromptReorderCommitSnapshot | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderCancelIntent:
    """Request cancellation of the active reorder session."""

    reason: str
    restore_selection: bool = True


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardMoveIntent:
    """Request one keyboard navigation step within reorder mode."""

    direction: PromptReorderKeyboardDirection


__all__ = [
    "PromptReorderCancelIntent",
    "PromptReorderCommitIntent",
    "PromptReorderKeyboardDirection",
    "PromptReorderKeyboardMoveIntent",
]
