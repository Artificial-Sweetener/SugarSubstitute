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

"""Define immutable renderer-facing prompt syntax projections."""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from substitute.application.prompt_editor.document.views import (
    PromptEmphasisView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)


@dataclass(frozen=True, slots=True)
class PromptSyntaxRendererView:
    """Describe one renderer-facing syntax projection keyed by syntax kind."""

    kind: str
    syntax_spans: Sequence[PromptSyntaxSpanView]


@dataclass(frozen=True, slots=True)
class PromptEmphasisRendererView(PromptSyntaxRendererView):
    """Describe the renderer-ready emphasis projection for one prompt snapshot."""

    emphasis_spans: Sequence[PromptEmphasisView]


@dataclass(frozen=True, slots=True)
class PromptWildcardRendererSpanView:
    """Describe one renderer-ready wildcard placeholder with resolution state."""

    outer_start: int
    outer_end: int
    content_start: int
    content_end: int
    wildcard_form: str
    identifier: str
    csv_column: str | None
    tag: str | None
    exists: bool
    matched_csv_column: str | None
    available_csv_columns: tuple[str, ...]
    depth: int
    source_key: str
    display_text: str
    display_tag: str | None
    tag_is_explicit: bool
    tag_is_numeric: bool
    can_step_tag: bool
    source_occurrence_count: int
    resolution_pending: bool = False


@dataclass(frozen=True, slots=True)
class PromptWildcardRendererView(PromptSyntaxRendererView):
    """Describe the renderer-ready wildcard projection for one prompt snapshot."""

    wildcard_spans: Sequence[PromptWildcardRendererSpanView]


@dataclass(frozen=True, slots=True)
class PromptLoraRendererSpanView:
    """Describe one renderer-ready LoRA schedule with catalog metadata."""

    outer_start: int
    outer_end: int
    name_start: int
    name_end: int
    first_weight_start: int
    first_weight_end: int
    first_weight: Decimal
    first_weight_text: str
    second_weight_start: int | None
    second_weight_end: int | None
    second_weight: Decimal | None
    second_weight_text: str | None
    prompt_name: str
    backend_value: str | None
    display_name: str
    display_subtitle: str | None
    trained_words: tuple[str, ...]
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...]
    model_page_url: str | None
    folder: str
    base_model: str | None
    has_collision: bool
    lora_status: PromptLoraResolutionStatus
    match_source: str
    status_reason: str
    authority: bool
    ambiguity_candidate_count: int
    exists: bool
    depth: int


@dataclass(frozen=True, slots=True)
class PromptLoraRendererView(PromptSyntaxRendererView):
    """Describe the renderer-ready LoRA projection for one prompt snapshot."""

    lora_spans: Sequence[PromptLoraRendererSpanView]


@dataclass(frozen=True, slots=True)
class PromptSyntaxRenderPlan:
    """Group all renderer-facing syntax projections for one prompt snapshot."""

    syntax_spans: Sequence[PromptSyntaxSpanView]
    renderer_views: Sequence[PromptSyntaxRendererView]
    document_semantics_identity: Hashable = "ordinary-prompt-v1"

    def renderer_view_for_kind(self, kind: str) -> PromptSyntaxRendererView | None:
        """Return the renderer view registered for one syntax kind."""

        for renderer_view in self.renderer_views:
            if renderer_view.kind == kind:
                return renderer_view
        return None


__all__ = [
    "PromptEmphasisRendererView",
    "PromptLoraRendererSpanView",
    "PromptLoraRendererView",
    "PromptSyntaxRenderPlan",
    "PromptSyntaxRendererView",
    "PromptWildcardRendererSpanView",
    "PromptWildcardRendererView",
]
