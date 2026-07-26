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

"""Capture the immutable references consumed by prompt geometry queries."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont

from ..projection.metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry
from ..layout.models import PromptProjectionLayoutSnapshot


@dataclass(frozen=True, slots=True)
class PromptProjectionGeometryInput:
    """Capture every immutable reference consumed by geometry queries."""

    projection_document: PromptProjectionDocument
    layout_snapshot: PromptProjectionLayoutSnapshot
    base_font: QFont
    document_margin: float
    metrics: PromptProjectionMetrics
    text_width: float
    inline_object_renderers: PromptProjectionInlineObjectRendererRegistry
    layout_identity: int


__all__ = ["PromptProjectionGeometryInput"]
