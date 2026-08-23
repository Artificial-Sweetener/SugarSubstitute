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

"""Provide syntax-action service doubles."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import PromptMutation


class MutationServiceDouble:
    """Provide deterministic mutation responses for syntax-action tests."""

    def __init__(
        self,
        *,
        apply_syntax_action_result: PromptMutation | None = None,
    ) -> None:
        """Store the mutation value returned to the controller."""

        self.apply_syntax_action_result = apply_syntax_action_result
        self.adjust_calls: list[tuple[str, int, int, float]] = []
        self.apply_syntax_action_calls: list[tuple[str, object]] = []

    def adjust_emphasis(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        delta: float,
    ) -> PromptMutation:
        """Record unexpected legacy emphasis adjustment calls."""

        self.adjust_calls.append((text, selection_start, selection_end, delta))
        raise AssertionError("Syntax-action tests should use typed mutation actions.")

    def apply_syntax_action(self, text: str, action: object) -> PromptMutation | None:
        """Return the configured syntax-action result after recording the request."""

        self.apply_syntax_action_calls.append((text, action))
        return self.apply_syntax_action_result


class DocumentServiceDouble:
    """Provide a deterministic prompt-document service for syntax-action tests."""

    def __init__(self, document_service: PromptDocumentService, *, text: str) -> None:
        """Store the initial cached document view."""

        self.document_view = document_service.build_document_view(text)
        self.build_calls: list[str] = []

    def build_document_view(self, text: str) -> object:
        """Return the prebuilt document view for the expected starting text."""

        self.build_calls.append(text)
        assert text == self.document_view.source_text
        return self.document_view

    def emphasis_for_content_range(
        self,
        document_view: object,
        *,
        content_start: int,
        content_end: int,
    ) -> object | None:
        """Return the emphasis span matching one visible content range."""

        for span in getattr(document_view, "emphasis_spans"):
            if span.content_start == content_start and span.content_end == content_end:
                return cast(object, span)
        return None

    def emphasis_for_outer_range(
        self,
        document_view: object,
        *,
        outer_start: int,
        outer_end: int,
    ) -> object | None:
        """Return the emphasis span matching one exact outer shell range."""

        for span in getattr(document_view, "emphasis_spans"):
            if span.outer_start == outer_start and span.outer_end == outer_end:
                return cast(object, span)
        return None
