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

"""Apply LoRA-specific prompt mutations."""

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
    adjust_lora_weight,
    set_lora_weight,
)


class PromptLoraMutationService:
    """Own first-weight mutation policy for parsed LoRA syntax."""

    def __init__(
        self,
        document_projector: PromptDocumentProjector,
        mutation_projector: PromptMutationProjector,
    ) -> None:
        """Store document and result projectors used by LoRA operations."""

        self._document_projector = document_projector
        self._mutation_projector = mutation_projector

    def adjust_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        delta: float | Decimal,
    ) -> PromptMutation | None:
        """Adjust the first weight for the LoRA matching one outer range."""

        document = self._document_projector.parse_document(text)
        span = document.lora_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        result = adjust_lora_weight(
            document,
            span,
            delta=prompt_decimal(delta),
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
        """Set the first weight for the LoRA matching one outer range."""

        document = self._document_projector.parse_document(text)
        span = document.lora_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        result = set_lora_weight(
            document,
            span,
            weight=prompt_decimal(weight),
        )
        return self._mutation_projector.project_result(result)


__all__ = ["PromptLoraMutationService"]
