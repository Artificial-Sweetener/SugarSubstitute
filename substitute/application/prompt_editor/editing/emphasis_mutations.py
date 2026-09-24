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

"""Apply emphasis-specific prompt mutations."""

from __future__ import annotations

from decimal import Decimal

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.editing.mutation_result import (
    PromptMutation,
    PromptMutationProjector,
)
from substitute.application.prompt_editor.editing.mutation_values import prompt_decimal
from substitute.domain.prompt.document.ranges import SourceRange
from substitute.domain.prompt.emphasis.operations import (
    decrease_emphasis,
    increase_emphasis,
    set_emphasis_weight,
)


class PromptEmphasisMutationService:
    """Own emphasis wrapping, adjustment, and exact-weight mutation policy."""

    def __init__(
        self,
        document_projector: PromptDocumentProjector,
        mutation_projector: PromptMutationProjector,
    ) -> None:
        """Store document and result projectors used by emphasis operations."""

        self._document_projector = document_projector
        self._mutation_projector = mutation_projector

    def adjust(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        delta: float | Decimal,
    ) -> PromptMutation:
        """Increase or decrease emphasis around the selected text."""

        document = self._document_projector.parse_document(text)
        selection_range = SourceRange(selection_start, selection_end)
        step = prompt_decimal(delta)
        result = (
            increase_emphasis(document, selection_range, step=step)
            if step >= Decimal("0")
            else decrease_emphasis(document, selection_range, step=abs(step))
        )
        return self._mutation_projector.project_result(result)

    def set_weight(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        weight: float | Decimal,
    ) -> PromptMutation:
        """Set emphasis to one exact weight over a content range."""

        document = self._document_projector.parse_document(text)
        result = set_emphasis_weight(
            document,
            SourceRange(selection_start, selection_end),
            weight=prompt_decimal(weight),
        )
        return self._mutation_projector.project_result(result)

    def adjust_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        delta: float | Decimal,
    ) -> PromptMutation | None:
        """Adjust the emphasis span matching one exact outer source range."""

        document = self._document_projector.parse_document(text)
        span = document.emphasis_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        step = prompt_decimal(delta)
        result = (
            increase_emphasis(document, span.content_range, step=step)
            if step >= Decimal("0")
            else decrease_emphasis(document, span.content_range, step=abs(step))
        )
        return self._mutation_projector.project_result(result)

    def set_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        weight: float | Decimal,
    ) -> PromptMutation | None:
        """Set the weight of the emphasis span matching one outer range."""

        document = self._document_projector.parse_document(text)
        span = document.emphasis_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        result = set_emphasis_weight(
            document,
            span.content_range,
            weight=prompt_decimal(weight),
        )
        return self._mutation_projector.project_result(result)


__all__ = ["PromptEmphasisMutationService"]
