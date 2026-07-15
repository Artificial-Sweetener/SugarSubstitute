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

"""Coordinate prompt-domain mutations for the presentation layer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from substitute.domain.prompt import (
    PromptGapBlankLineDropTarget as DomainPromptGapBlankLineDropTarget,
    PromptLineDropTarget as DomainPromptLineDropTarget,
    PromptDocument,
    PromptMutationResult,
    SourceRange,
    adjust_lora_weight,
    decrease_emphasis,
    increase_emphasis,
    reorder_segments,
    set_emphasis_weight,
    set_lora_weight,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_views import PromptDocumentView
from .prompt_reorder_projection_service import PromptReorderProjectionService
from .prompt_reorder_serialization_service import PromptReorderSerializationService
from .prompt_reorder_views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderStateView,
)

_LOGGER = get_logger("application.prompt_editor.prompt_mutation_service")


@dataclass(frozen=True, slots=True)
class PromptSyntaxAction:
    """Describe one typed syntax-aware editor request emitted by a renderer."""


@dataclass(frozen=True, slots=True)
class PromptConsumeSyntaxAction(PromptSyntaxAction):
    """Consume one syntax-owned interaction without mutating the prompt text."""

    syntax_kind: str


@dataclass(frozen=True, slots=True)
class PromptAdjustEmphasisAction(PromptSyntaxAction):
    """Adjust one emphasis shell identified by its exact outer source range."""

    outer_start: int
    outer_end: int
    delta: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptAdjustEmphasisContentAction(PromptSyntaxAction):
    """Adjust emphasis over one visible content range, even when no shell exists."""

    content_start: int
    content_end: int
    delta: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptSetEmphasisWeightAction(PromptSyntaxAction):
    """Set one emphasis shell to an exact weight by its outer source range."""

    outer_start: int
    outer_end: int
    weight: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptSetEmphasisWeightContentAction(PromptSyntaxAction):
    """Set emphasis to one exact weight over a visible content range."""

    content_start: int
    content_end: int
    weight: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptAdjustLoraWeightAction(PromptSyntaxAction):
    """Adjust one LoRA schedule token identified by its exact outer source range."""

    outer_start: int
    outer_end: int
    delta: float | Decimal
    syntax_kind: str = "lora"


@dataclass(frozen=True, slots=True)
class PromptSetLoraWeightAction(PromptSyntaxAction):
    """Set one LoRA schedule token to an exact first-weight value."""

    outer_start: int
    outer_end: int
    weight: float | Decimal
    syntax_kind: str = "lora"


@dataclass(frozen=True, slots=True)
class PromptSetWildcardTagAction(PromptSyntaxAction):
    """Set one wildcard placeholder to an exact free-text group tag."""

    outer_start: int
    outer_end: int
    tag: str
    syntax_kind: str = "wildcard"


@dataclass(frozen=True, slots=True)
class PromptAdjustWildcardTagAction(PromptSyntaxAction):
    """Adjust one wildcard placeholder's numeric display group tag."""

    outer_start: int
    outer_end: int
    current_display_tag: str
    delta: int
    syntax_kind: str = "wildcard"


@dataclass(frozen=True, slots=True)
class PromptMutation:
    """Represent one prompt mutation ready for editor text replacement and refresh."""

    text: str
    selection_start: int | None
    selection_end: int | None
    document_view: PromptDocumentView


class PromptMutationService:
    """Apply prompt mutations and return typed editor updates."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
        reorder_projection_service: PromptReorderProjectionService | None = None,
        reorder_serialization_service: PromptReorderSerializationService | None = None,
    ) -> None:
        """Store focused prompt document collaborators for mutation projection."""

        self._document_projector = document_projector or PromptDocumentProjector()
        self._reorder_projection_service = (
            reorder_projection_service
            or PromptReorderProjectionService(
                document_projector=self._document_projector
            )
        )
        self._reorder_serialization_service = (
            reorder_serialization_service
            or PromptReorderSerializationService(
                document_projector=self._document_projector
            )
        )

    def apply_syntax_action(
        self,
        text: str,
        action: PromptSyntaxAction,
    ) -> PromptMutation | None:
        """Apply one typed syntax action produced by a syntax-aware renderer."""

        if isinstance(action, PromptAdjustEmphasisAction):
            mutation = self.adjust_emphasis_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                delta=action.delta,
            )
            if mutation is None:
                log_debug(
                    _LOGGER,
                    "Prompt syntax action target is stale.",
                    action_type=type(action).__name__,
                    syntax_kind=action.syntax_kind,
                    outer_start=action.outer_start,
                    outer_end=action.outer_end,
                    prompt_length=len(text),
                )
            return mutation

        if isinstance(action, PromptAdjustEmphasisContentAction):
            return self.adjust_emphasis(
                text,
                selection_start=action.content_start,
                selection_end=action.content_end,
                delta=action.delta,
            )

        if isinstance(action, PromptSetEmphasisWeightAction):
            mutation = self.set_emphasis_weight_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                weight=action.weight,
            )
            if mutation is None:
                log_debug(
                    _LOGGER,
                    "Prompt syntax action target is stale.",
                    action_type=type(action).__name__,
                    syntax_kind=action.syntax_kind,
                    outer_start=action.outer_start,
                    outer_end=action.outer_end,
                    prompt_length=len(text),
                )
            return mutation

        if isinstance(action, PromptSetEmphasisWeightContentAction):
            return self.set_emphasis_weight(
                text,
                selection_start=action.content_start,
                selection_end=action.content_end,
                weight=action.weight,
            )

        if isinstance(action, PromptAdjustLoraWeightAction):
            mutation = self.adjust_lora_weight_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                delta=action.delta,
            )
            if mutation is None:
                log_debug(
                    _LOGGER,
                    "Prompt syntax action target is stale.",
                    action_type=type(action).__name__,
                    syntax_kind=action.syntax_kind,
                    outer_start=action.outer_start,
                    outer_end=action.outer_end,
                    prompt_length=len(text),
                )
            return mutation

        if isinstance(action, PromptSetLoraWeightAction):
            mutation = self.set_lora_weight_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                weight=action.weight,
            )
            if mutation is None:
                log_debug(
                    _LOGGER,
                    "Prompt syntax action target is stale.",
                    action_type=type(action).__name__,
                    syntax_kind=action.syntax_kind,
                    outer_start=action.outer_start,
                    outer_end=action.outer_end,
                    prompt_length=len(text),
                )
            return mutation

        if isinstance(action, PromptSetWildcardTagAction):
            mutation = self.set_wildcard_tag_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                tag=action.tag,
            )
            if mutation is None:
                log_debug(
                    _LOGGER,
                    "Prompt syntax action target is stale or invalid.",
                    action_type=type(action).__name__,
                    syntax_kind=action.syntax_kind,
                    outer_start=action.outer_start,
                    outer_end=action.outer_end,
                    prompt_length=len(text),
                )
            return mutation

        if isinstance(action, PromptAdjustWildcardTagAction):
            mutation = self.adjust_wildcard_numeric_tag_for_outer_range(
                text,
                outer_start=action.outer_start,
                outer_end=action.outer_end,
                current_display_tag=action.current_display_tag,
                delta=action.delta,
            )
            if mutation is None:
                log_debug(
                    _LOGGER,
                    "Prompt syntax action target is stale or not numeric.",
                    action_type=type(action).__name__,
                    syntax_kind=action.syntax_kind,
                    outer_start=action.outer_start,
                    outer_end=action.outer_end,
                    prompt_length=len(text),
                )
            return mutation

        if isinstance(action, PromptConsumeSyntaxAction):
            return None

        log_warning(
            _LOGGER,
            "Unsupported prompt syntax action.",
            action_type=type(action).__name__,
            syntax_kind=_syntax_kind_for_action(action),
            prompt_length=len(text),
        )
        return None

    def adjust_emphasis(
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
        step = _to_decimal(delta)
        result = (
            increase_emphasis(document, selection_range, step=step)
            if step >= Decimal("0")
            else decrease_emphasis(document, selection_range, step=abs(step))
        )
        return self._mutation_from_result(result)

    def set_emphasis_weight(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        weight: float | Decimal,
    ) -> PromptMutation:
        """Set emphasis to one exact weight over the supplied content range."""

        document = self._document_projector.parse_document(text)
        selection_range = SourceRange(selection_start, selection_end)
        result = set_emphasis_weight(
            document,
            selection_range,
            weight=_to_decimal(weight),
        )
        return self._mutation_from_result(result)

    def adjust_emphasis_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        delta: float | Decimal,
    ) -> PromptMutation | None:
        """Adjust the emphasis span identified by one exact outer source range."""

        document = self._document_projector.parse_document(text)
        target_range = SourceRange(outer_start, outer_end)
        span = document.emphasis_with_outer_range(target_range)
        if span is None:
            return None

        step = _to_decimal(delta)
        result = (
            increase_emphasis(document, span.content_range, step=step)
            if step >= Decimal("0")
            else decrease_emphasis(document, span.content_range, step=abs(step))
        )
        return self._mutation_from_result(result)

    def set_emphasis_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        weight: float | Decimal,
    ) -> PromptMutation | None:
        """Set one exact weight on the emphasis shell matching the supplied outer range."""

        document = self._document_projector.parse_document(text)
        target_range = SourceRange(outer_start, outer_end)
        span = document.emphasis_with_outer_range(target_range)
        if span is None:
            return None
        result = set_emphasis_weight(
            document,
            span.content_range,
            weight=_to_decimal(weight),
        )
        return self._mutation_from_result(result)

    def adjust_lora_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        delta: float | Decimal,
    ) -> PromptMutation | None:
        """Adjust the first weight for the LoRA span matching one outer range."""

        document = self._document_projector.parse_document(text)
        target_range = SourceRange(outer_start, outer_end)
        span = document.lora_with_outer_range(target_range)
        if span is None:
            return None
        result = adjust_lora_weight(
            document,
            span,
            delta=_to_decimal(delta),
        )
        return self._mutation_from_result(result)

    def set_lora_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        weight: float | Decimal,
    ) -> PromptMutation | None:
        """Set the first weight for the LoRA span matching one outer range."""

        document = self._document_projector.parse_document(text)
        target_range = SourceRange(outer_start, outer_end)
        span = document.lora_with_outer_range(target_range)
        if span is None:
            return None
        result = set_lora_weight(
            document,
            span,
            weight=_to_decimal(weight),
        )
        return self._mutation_from_result(result)

    def set_wildcard_tag_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        tag: str,
    ) -> PromptMutation | None:
        """Set or replace the wildcard tag for one exact placeholder range."""

        if not _is_valid_wildcard_tag(tag):
            return None
        document = self._document_projector.parse_document(text)
        span = document.wildcard_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        new_text, selection_position = _replace_wildcard_tag(
            text,
            content_range=span.content_range,
            tag=tag,
        )
        return self._mutation_from_document(
            text=new_text,
            document=self._document_projector.parse_document(new_text),
            selection_range=SourceRange(selection_position, selection_position),
        )

    def adjust_wildcard_numeric_tag_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        current_display_tag: str,
        delta: int,
    ) -> PromptMutation | None:
        """Persist a stepped numeric wildcard group tag for one placeholder range."""

        if not _is_positive_integer_text(current_display_tag):
            return None
        document = self._document_projector.parse_document(text)
        span = document.wildcard_with_outer_range(SourceRange(outer_start, outer_end))
        if span is None:
            return None
        if span.tag is not None and not _is_positive_integer_text(span.tag):
            return None
        adjusted_tag = str(max(1, int(current_display_tag) + delta))
        return self.set_wildcard_tag_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            tag=adjusted_tag,
        )

    def reorder_chips(
        self,
        text: str,
        *,
        dragged_chip_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptMutation:
        """Reorder prompt chips by applying one typed row/gap drop target."""

        document = self._document_projector.parse_document(text)
        result = reorder_segments(
            document,
            dragged_segment_index=dragged_chip_index,
            drop_target=_domain_drop_target_from_application(drop_target),
        )
        return self._mutation_from_result(result)

    def reorder_layout(
        self,
        text: str,
        *,
        layout_view: PromptReorderLayoutView,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Commit one in-session reorder layout back into prompt text."""

        current_document_view = self._document_projector.build_document_view(text)
        preview_snapshot = (
            self._reorder_serialization_service.build_reorder_preview_snapshot(
                current_document_view,
                layout_view,
                include_edge_gaps=False,
            )
        )
        selection_range = None
        if selected_chip_index is not None:
            selected_range = preview_snapshot.chip_ranges_by_index.get(
                selected_chip_index
            )
            if selected_range is not None:
                selection_range = SourceRange(*selected_range)
        mutation_text = _preserve_source_trailing_comma_spacing(
            preview_snapshot.text,
            source_text=text,
        )
        return self._mutation_from_document(
            text=mutation_text,
            document=self._document_projector.parse_document(mutation_text),
            selection_range=selection_range,
        )

    def reorder_state(
        self,
        text: str,
        *,
        reorder_state: PromptReorderStateView,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Commit authoritative reorder source state back into prompt text."""

        current_document_view = self._document_projector.build_document_view(text)
        layout_view = (
            self._reorder_projection_service.build_reorder_layout_view_from_state(
                reorder_state
            )
        )
        preview_snapshot = self._reorder_serialization_service.build_reorder_preview_snapshot_from_state(
            current_document_view,
            reorder_state,
            layout_view=layout_view,
            include_edge_gaps=False,
        )
        selection_range = None
        if selected_chip_index is not None:
            selected_range = preview_snapshot.chip_ranges_by_index.get(
                selected_chip_index
            )
            if selected_range is not None:
                selection_range = SourceRange(*selected_range)
        mutation_text = _preserve_source_trailing_comma_spacing(
            preview_snapshot.text,
            source_text=text,
        )
        return self._mutation_from_document(
            text=mutation_text,
            document=self._document_projector.parse_document(mutation_text),
            selection_range=selection_range,
        )

    def _mutation_from_result(self, result: PromptMutationResult) -> PromptMutation:
        """Convert one domain mutation result into the application mutation view."""

        return self._mutation_from_document(
            text=result.text,
            document=result.document,
            selection_range=result.selection_range,
        )

    def _mutation_from_document(
        self,
        *,
        text: str,
        document: PromptDocument,
        selection_range: SourceRange | None,
    ) -> PromptMutation:
        """Build one prompt mutation from a domain document and optional selection."""

        document_view = self._document_projector.build_document_view_from_document(
            document
        )
        return PromptMutation(
            text=text,
            selection_start=None if selection_range is None else selection_range.start,
            selection_end=None if selection_range is None else selection_range.end,
            document_view=document_view,
        )


def _to_decimal(value: float | Decimal) -> Decimal:
    """Convert one numeric prompt-editor delta into Decimal form."""

    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _preserve_source_trailing_comma_spacing(text: str, *, source_text: str) -> str:
    """Avoid inventing final horizontal whitespace for bare trailing-comma prompts."""

    if not text.endswith(", "):
        return text
    if source_text.endswith(","):
        return text[:-1]
    return text


def _replace_wildcard_tag(
    text: str,
    *,
    content_range: SourceRange,
    tag: str,
) -> tuple[str, int]:
    """Return text with one wildcard content range rewritten to carry the tag."""

    content = text[content_range.start : content_range.end]
    base_content, _, _ = content.partition("|")
    replacement = f"{base_content}|{tag}"
    selection_position = content_range.start + len(replacement)
    return (
        text[: content_range.start] + replacement + text[content_range.end :],
        selection_position,
    )


def _is_valid_wildcard_tag(tag: str) -> bool:
    """Return whether one tag string can be parsed as a wildcard tag suffix."""

    return bool(tag) and tag.strip() == tag


def _is_positive_integer_text(value: str) -> bool:
    """Return whether one string is a strict positive integer."""

    return (
        value.isdecimal()
        and int(value) > 0
        and not (len(value) > 1 and value.startswith("0"))
    )


def _syntax_kind_for_action(action: PromptSyntaxAction) -> str:
    """Return the syntax-kind label exposed by one typed syntax action."""

    return getattr(action, "syntax_kind", "unknown")


def _domain_drop_target_from_application(
    drop_target: PromptReorderDropTarget,
) -> DomainPromptLineDropTarget | DomainPromptGapBlankLineDropTarget:
    """Convert one application drop target into the domain reorder target type."""

    if isinstance(drop_target, PromptLineDropTarget):
        return DomainPromptLineDropTarget(
            row_index=drop_target.row_index,
            insertion_index=drop_target.insertion_index,
        )
    return DomainPromptGapBlankLineDropTarget(
        gap_index=drop_target.gap_index,
        blank_line_index=drop_target.blank_line_index,
    )


__all__ = [
    "PromptAdjustWildcardTagAction",
    "PromptAdjustLoraWeightAction",
    "PromptAdjustEmphasisAction",
    "PromptAdjustEmphasisContentAction",
    "PromptConsumeSyntaxAction",
    "PromptMutation",
    "PromptMutationService",
    "PromptSetEmphasisWeightAction",
    "PromptSetEmphasisWeightContentAction",
    "PromptSetLoraWeightAction",
    "PromptSetWildcardTagAction",
    "PromptSyntaxAction",
]
