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

"""Define immutable inputs and outcomes shared by prompt layout engines."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QFont

from substitute.application.prompt_editor.document.views import PromptDocumentView

from ..core.state.editor_state import PromptLayoutWidthKey
from ..projection.metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry
from .models import PromptProjectionLayoutSnapshot


class PromptLayoutStatus(Enum):
    """Describe whether one engine attempt published layout work."""

    APPLIED = "applied"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class PromptLayoutReason(Enum):
    """Identify the bounded reason for one layout outcome."""

    CANONICAL_BUILD = "canonical_build"
    CANONICAL_REFLOW = "canonical_reflow"
    MISSING_PREVIOUS_LAYOUT = "missing_previous_layout"
    MISSING_EDIT = "missing_edit"
    MISSING_DOCUMENT_VIEW = "missing_document_view"
    CONFIGURATION_MISMATCH = "configuration_mismatch"
    SAME_LINE_EDIT = "same_line_edit"
    HARD_LINE_EDIT = "hard_line_edit"
    TRAILING_PLAIN_INSERT = "trailing_plain_insert"
    TRAILING_PLAIN_DELETE = "trailing_plain_delete"
    TRAILING_NEWLINE_INSERT = "trailing_newline_insert"
    TRAILING_NEWLINE_DELETE = "trailing_newline_delete"
    UNSUPPORTED_EDIT_DELTA = "unsupported_edit_delta"
    NEWLINE_EDIT = "newline_edit"
    DIRTY_LINE_NOT_FOUND = "dirty_line_not_found"
    DIRTY_LINE_HAS_INLINE_OBJECT = "dirty_line_has_inline_object"
    AFFECTED_FRAGMENT_NOT_FOUND = "affected_fragment_not_found"
    UPDATED_RUN_NOT_FOUND = "updated_run_not_found"
    FRAGMENT_EDIT_NOT_SUPPORTED = "fragment_edit_not_supported"
    EMPTY_LINE_INSERT_NOT_SUPPORTED = "empty_line_insert_not_supported"
    WORD_WRAP_BOUNDARY = "word_wrap_boundary"
    EDIT_WOULD_WRAP = "edit_would_wrap"
    TAG_KEEP_GROUP = "tag_keep_group"
    NOT_HARD_LINE_BREAK_EDIT = "not_hard_line_break_edit"
    LINE_SPLIT_NOT_SUPPORTED = "line_split_not_supported"
    LINE_JOIN_NOT_SUPPORTED = "line_join_not_supported"
    TRAILING_EDIT_NOT_SUPPORTED = "trailing_edit_not_supported"


@dataclass(frozen=True, slots=True)
class PromptLayoutConfiguration:
    """Capture every stable input that can affect prompt layout geometry."""

    base_font: QFont
    document_margin: float
    text_width: float
    content_left_inset: float
    metrics: PromptProjectionMetrics
    inline_object_renderers: PromptProjectionInlineObjectRendererRegistry

    def __post_init__(self) -> None:
        """Detach the retained font from caller-owned mutable Qt state."""

        object.__setattr__(self, "base_font", QFont(self.base_font))


@dataclass(frozen=True, slots=True)
class PromptLayoutEdit:
    """Describe one source/projection edit offered to a layout engine."""

    start: int
    end: int
    replacement_text: str
    first_dirty_projection_position: int
    editable_token_id: str | None = None
    projection_edit_start: int | None = None
    projection_edit_end: int | None = None
    projection_replacement_text: str | None = None


@dataclass(frozen=True, slots=True)
class PromptLayoutOutput:
    """Publish the exact immutable state produced by one layout engine."""

    projection_document: PromptProjectionDocument
    prompt_document_view: PromptDocumentView | None
    snapshot: PromptProjectionLayoutSnapshot
    configuration: PromptLayoutConfiguration

    @property
    def width_key(self) -> PromptLayoutWidthKey:
        """Return the compact geometry identity published to frame state."""

        return PromptLayoutWidthKey(
            text_width=self.configuration.text_width,
            content_left_inset=self.configuration.content_left_inset,
            document_margin=self.configuration.document_margin,
            font_key=self.configuration.base_font.toString(),
        )


@dataclass(frozen=True, slots=True)
class PromptLayoutRequest:
    """Provide one common immutable request to canonical or incremental layout."""

    previous: PromptLayoutOutput | None
    projection_document: PromptProjectionDocument
    prompt_document_view: PromptDocumentView | None
    configuration: PromptLayoutConfiguration
    edit: PromptLayoutEdit | None = None


@dataclass(frozen=True, slots=True)
class PromptLayoutDamage:
    """Bound the changed visual-line and content-height region."""

    content_height_changed: bool
    content_height_delta: float
    first_reflowed_line_index: int
    reflowed_line_count: int
    upstream_line_count: int


@dataclass(frozen=True, slots=True)
class PromptLayoutOutcome:
    """Return one typed engine decision without triggering fallback."""

    status: PromptLayoutStatus
    reason: PromptLayoutReason
    output: PromptLayoutOutput | None = None
    damage: PromptLayoutDamage | None = None

    def __post_init__(self) -> None:
        """Enforce complete applied results and inert non-applied results."""

        has_published_result = self.output is not None and self.damage is not None
        if self.status is PromptLayoutStatus.APPLIED and not has_published_result:
            raise ValueError("applied layout outcomes require output and damage")
        if self.status is not PromptLayoutStatus.APPLIED and (
            self.output is not None or self.damage is not None
        ):
            raise ValueError("non-applied layout outcomes cannot publish layout state")

    @classmethod
    def applied(
        cls,
        *,
        reason: PromptLayoutReason,
        output: PromptLayoutOutput,
        damage: PromptLayoutDamage,
    ) -> PromptLayoutOutcome:
        """Return a complete applied engine result."""

        return cls(
            status=PromptLayoutStatus.APPLIED,
            reason=reason,
            output=output,
            damage=damage,
        )

    @classmethod
    def rejected(cls, reason: PromptLayoutReason) -> PromptLayoutOutcome:
        """Return an inert rejected engine result."""

        return cls(status=PromptLayoutStatus.REJECTED, reason=reason)

    @classmethod
    def deferred(cls, reason: PromptLayoutReason) -> PromptLayoutOutcome:
        """Return an inert result whose caller may schedule canonical recovery."""

        return cls(status=PromptLayoutStatus.DEFERRED, reason=reason)


__all__ = [
    "PromptLayoutConfiguration",
    "PromptLayoutDamage",
    "PromptLayoutEdit",
    "PromptLayoutOutcome",
    "PromptLayoutOutput",
    "PromptLayoutReason",
    "PromptLayoutRequest",
    "PromptLayoutStatus",
]
