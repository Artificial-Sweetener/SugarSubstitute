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

"""Own the application result contract for prompt text mutations."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.domain.prompt.document.models import (
    PromptDocument,
    PromptMutationResult,
)
from substitute.domain.prompt.document.ranges import SourceRange


@dataclass(frozen=True, slots=True)
class PromptMutation:
    """Represent one prompt mutation ready for replacement and refresh."""

    text: str
    selection_start: int | None
    selection_end: int | None
    document_view: PromptDocumentView


class PromptMutationProjector:
    """Project domain mutation state into the shared application result."""

    def __init__(self, document_projector: PromptDocumentProjector) -> None:
        """Store the document projector that owns semantic view construction."""

        self._document_projector = document_projector

    def project_result(self, result: PromptMutationResult) -> PromptMutation:
        """Project one domain mutation result into editor-facing state."""

        return self.project_document(
            text=result.text,
            document=result.document,
            selection_range=result.selection_range,
        )

    def project_document(
        self,
        *,
        text: str,
        document: PromptDocument,
        selection_range: SourceRange | None,
    ) -> PromptMutation:
        """Project one parsed document and optional selection into editor state."""

        document_view = self._document_projector.build_document_view_from_document(
            document
        )
        return PromptMutation(
            text=text,
            selection_start=None if selection_range is None else selection_range.start,
            selection_end=None if selection_range is None else selection_range.end,
            document_view=document_view,
        )

    def project_text(
        self,
        *,
        text: str,
        selection_start: int | None,
        selection_end: int | None,
    ) -> PromptMutation:
        """Parse mutated text and publish its editor-facing semantic state."""

        return PromptMutation(
            text=text,
            selection_start=selection_start,
            selection_end=selection_end,
            document_view=self._document_projector.build_document_view(text),
        )


__all__ = ["PromptMutation", "PromptMutationProjector"]
