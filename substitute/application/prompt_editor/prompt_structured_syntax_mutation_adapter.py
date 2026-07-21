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

"""Apply prompt syntax actions within decoded structured values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.domain.prompt import SourceRange

from .prompt_document_semantics import PromptDocumentSemantics, PromptValueMapping
from .prompt_syntax_actions import (
    PromptAdjustEmphasisAction,
    PromptAdjustEmphasisContentAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
    PromptSyntaxAction,
)


@dataclass(frozen=True, slots=True)
class PromptLogicalSyntaxMutation:
    """Describe the logical mutation output needed for raw-source remapping."""

    text: str
    selection_start: int | None
    selection_end: int | None


@dataclass(frozen=True, slots=True)
class PromptStructuredSyntaxMutation:
    """Describe one structure-safe mutation in raw document coordinates."""

    text: str
    selection_start: int | None
    selection_end: int | None


class PromptStructuredSyntaxMutationAdapter:
    """Translate raw actions to decoded value actions and back."""

    def __init__(self, document_semantics: PromptDocumentSemantics) -> None:
        """Store the authoritative prompt-value mapping and replacement owner."""

        self._document_semantics = document_semantics

    def apply(
        self,
        source_text: str,
        action: PromptSyntaxAction,
        *,
        apply_logical_action: Callable[
            [str, PromptSyntaxAction],
            PromptLogicalSyntaxMutation | None,
        ],
    ) -> PromptStructuredSyntaxMutation | None:
        """Apply one raw action inside exactly one logical prompt value."""

        action_range = _action_source_range(action)
        if action_range is None:
            return None
        mapping = _value_mapping_for_range(
            self._document_semantics.value_mappings_for_text(source_text),
            action_range,
        )
        if mapping is None:
            return None
        try:
            logical_action = _logical_action(mapping, action)
        except ValueError:
            return None
        logical_mutation = apply_logical_action(mapping.logical_text, logical_action)
        if logical_mutation is None:
            return None
        updated_source = self._document_semantics.replace_value_text(
            source_text,
            mapping.value_id,
            logical_mutation.text,
        )
        updated_mapping = next(
            (
                candidate
                for candidate in self._document_semantics.value_mappings_for_text(
                    updated_source
                )
                if candidate.value_id == mapping.value_id
            ),
            None,
        )
        selection = _mapped_selection(updated_mapping, logical_mutation)
        return PromptStructuredSyntaxMutation(
            text=updated_source,
            selection_start=None if selection is None else selection.start,
            selection_end=None if selection is None else selection.end,
        )


def _action_source_range(action: PromptSyntaxAction) -> SourceRange | None:
    """Return the raw target range carried by one syntax mutation action."""

    if isinstance(
        action,
        (
            PromptAdjustEmphasisAction,
            PromptSetEmphasisWeightAction,
            PromptAdjustLoraWeightAction,
            PromptSetLoraWeightAction,
            PromptSetWildcardTagAction,
            PromptAdjustWildcardTagAction,
        ),
    ):
        return SourceRange(action.outer_start, action.outer_end)
    if isinstance(
        action,
        (
            PromptAdjustEmphasisContentAction,
            PromptSetEmphasisWeightContentAction,
        ),
    ):
        return SourceRange(action.content_start, action.content_end)
    return None


def _value_mapping_for_range(
    mappings: tuple[PromptValueMapping, ...],
    source_range: SourceRange,
) -> PromptValueMapping | None:
    """Return the unique value mapping containing one complete source range."""

    matches = tuple(
        mapping
        for mapping in mappings
        if mapping.source_range.start <= source_range.start
        and source_range.end <= mapping.source_range.end
    )
    return matches[0] if len(matches) == 1 else None


def _logical_action(
    mapping: PromptValueMapping,
    action: PromptSyntaxAction,
) -> PromptSyntaxAction:
    """Map one typed raw-source action into decoded value coordinates."""

    if isinstance(action, PromptAdjustEmphasisAction):
        target = _logical_range(mapping, action.outer_start, action.outer_end)
        return PromptAdjustEmphasisAction(target.start, target.end, action.delta)
    if isinstance(action, PromptAdjustEmphasisContentAction):
        target = _logical_range(mapping, action.content_start, action.content_end)
        return PromptAdjustEmphasisContentAction(
            target.start,
            target.end,
            action.delta,
        )
    if isinstance(action, PromptSetEmphasisWeightAction):
        target = _logical_range(mapping, action.outer_start, action.outer_end)
        return PromptSetEmphasisWeightAction(target.start, target.end, action.weight)
    if isinstance(action, PromptSetEmphasisWeightContentAction):
        target = _logical_range(mapping, action.content_start, action.content_end)
        return PromptSetEmphasisWeightContentAction(
            target.start,
            target.end,
            action.weight,
        )
    if isinstance(action, PromptAdjustLoraWeightAction):
        target = _logical_range(mapping, action.outer_start, action.outer_end)
        return PromptAdjustLoraWeightAction(target.start, target.end, action.delta)
    if isinstance(action, PromptSetLoraWeightAction):
        target = _logical_range(mapping, action.outer_start, action.outer_end)
        return PromptSetLoraWeightAction(target.start, target.end, action.weight)
    if isinstance(action, PromptSetWildcardTagAction):
        target = _logical_range(mapping, action.outer_start, action.outer_end)
        return PromptSetWildcardTagAction(target.start, target.end, action.tag)
    if isinstance(action, PromptAdjustWildcardTagAction):
        target = _logical_range(mapping, action.outer_start, action.outer_end)
        return PromptAdjustWildcardTagAction(
            target.start,
            target.end,
            action.current_display_tag,
            action.delta,
        )
    return action


def _logical_range(
    mapping: PromptValueMapping,
    start: int,
    end: int,
) -> SourceRange:
    """Map one raw action range into exact logical coordinates."""

    return mapping.logical_range_for_source_range(SourceRange(start, end))


def _mapped_selection(
    mapping: PromptValueMapping | None,
    mutation: PromptLogicalSyntaxMutation,
) -> SourceRange | None:
    """Map a logical mutation selection into updated raw coordinates."""

    if (
        mapping is None
        or mutation.selection_start is None
        or mutation.selection_end is None
    ):
        return None
    return mapping.source_range_for_logical_range(
        SourceRange(mutation.selection_start, mutation.selection_end)
    )


__all__ = [
    "PromptLogicalSyntaxMutation",
    "PromptStructuredSyntaxMutation",
    "PromptStructuredSyntaxMutationAdapter",
]
