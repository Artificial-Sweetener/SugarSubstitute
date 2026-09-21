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

"""Define the layout and paint contract for prompt inline objects."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QPointF, QRectF, QSizeF
from PySide6.QtGui import QFont, QPainter, QPalette

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)


class PromptRichInlineObjectRenderer(Protocol):
    """Describe one renderer used by the projection layout for inline objects."""

    renderer_key: str

    def measure_inline_object(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
    ) -> QSizeF:
        """Return the inline size required to render one visible object run."""

    def paint_inline_object(
        self,
        painter: QPainter,
        rect: QRectF,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        *,
        base_font: QFont,
        palette: QPalette,
        selected: bool = False,
    ) -> None:
        """Paint one inline object run inside the supplied rect."""

    def anchor_rect(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        base_font: QFont,
    ) -> QRectF | None:
        """Return the rect used for non-clipping controls anchored to this object."""

    def hit_test_caret_state(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        position: QPointF,
        *,
        base_font: QFont,
    ) -> PromptProjectionCaretState:
        """Resolve one object-local point into the nearest logical caret state."""

    def selection_rects(
        self,
        run: PromptProjectionRun,
        token: PromptProjectionToken,
        rect: QRectF,
        *,
        selection_start: int,
        selection_end: int,
        base_font: QFont,
    ) -> tuple[QRectF, ...]:
        """Return the selection rects owned by one inline object run."""
