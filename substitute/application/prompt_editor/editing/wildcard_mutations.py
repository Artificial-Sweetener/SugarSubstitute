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

"""Apply wildcard-tag prompt mutations."""

from __future__ import annotations

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.editing.mutation_result import (
    PromptMutation,
    PromptMutationProjector,
)
from substitute.domain.prompt.document.ranges import SourceRange


class PromptWildcardMutationService:
    """Own explicit and stepped wildcard tag mutation policy."""

    def __init__(
        self,
        document_projector: PromptDocumentProjector,
        mutation_projector: PromptMutationProjector,
    ) -> None:
        """Store document and result projectors used by wildcard operations."""

        self._document_projector = document_projector
        self._mutation_projector = mutation_projector

    def set_tag_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        tag: str,
    ) -> PromptMutation | None:
        """Set or replace the tag for one exact wildcard placeholder range."""

        if not _is_valid_tag(tag):
            return None
        document = self._document_projector.parse_document(text)
        span = document.wildcard_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        new_text, selection_position = _replace_tag(
            text,
            content_range=span.content_range,
            tag=tag,
        )
        return self._mutation_projector.project_document(
            text=new_text,
            document=self._document_projector.parse_document(new_text),
            selection_range=SourceRange(selection_position, selection_position),
        )

    def adjust_numeric_tag_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        current_display_tag: str,
        delta: int,
    ) -> PromptMutation | None:
        """Persist a stepped numeric group tag for one wildcard range."""

        if not _is_positive_integer_text(current_display_tag):
            return None
        document = self._document_projector.parse_document(text)
        span = document.wildcard_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        if span.tag is not None and not _is_positive_integer_text(span.tag):
            return None
        adjusted_tag = str(max(1, int(current_display_tag) + delta))
        return self.set_tag_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            tag=adjusted_tag,
        )


def _replace_tag(
    text: str,
    *,
    content_range: SourceRange,
    tag: str,
) -> tuple[str, int]:
    """Return text with one wildcard content range rewritten to carry a tag."""

    content = text[content_range.start : content_range.end]
    base_content, _, _ = content.partition("|")
    replacement = f"{base_content}|{tag}"
    selection_position = content_range.start + len(replacement)
    return (
        text[: content_range.start] + replacement + text[content_range.end :],
        selection_position,
    )


def _is_valid_tag(tag: str) -> bool:
    """Return whether one string can be parsed as a wildcard tag suffix."""

    return bool(tag) and tag.strip() == tag


def _is_positive_integer_text(value: str) -> bool:
    """Return whether one string is a strict positive integer."""

    return (
        value.isdecimal()
        and int(value) > 0
        and not (len(value) > 1 and value.startswith("0"))
    )


__all__ = ["PromptWildcardMutationService"]
