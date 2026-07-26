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

"""Define immutable results returned by prompt geometry queries."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretHit:
    """Describe one pointer-selected caret state and its document rect."""

    state: PromptProjectionCaretState
    document_rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionDragSelectionTarget:
    """Describe one wrapped-line drag-selection endpoint."""

    state: PromptProjectionCaretState
    line_index: int | None


@dataclass(frozen=True, slots=True)
class PromptProjectionVerticalCaretTarget:
    """Describe one vertical caret destination and its document rect."""

    state: PromptProjectionCaretState
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionHorizontalCaretTarget:
    """Describe one horizontal caret destination and its document rect."""

    state: PromptProjectionCaretState
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceLineRect:
    """Describe one viewport-local logical source line row."""

    line_index: int
    rect: QRectF


__all__ = [
    "PromptProjectionCaretHit",
    "PromptProjectionDragSelectionTarget",
    "PromptProjectionHorizontalCaretTarget",
    "PromptProjectionSourceLineRect",
    "PromptProjectionVerticalCaretTarget",
]
