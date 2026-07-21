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

"""Apply bounded prompt source edit transactions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Protocol, TypeVar

from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    PromptGeneratedEmphasis,
    PromptParenthesisTransition,
    PromptParenthesisTransitionKind,
)
from substitute.domain.prompt import parse_prompt_document

from .cursor_state import PromptCursorState
from .edit_transaction import PromptUndoAvailabilityChange, PromptUndoSnapshot
from .source_buffer import PromptSourceBuffer, PromptSourceSnapshot
from .parenthesis_intent import PromptParenthesisIntent, segment_bounds_at
from .undo_stack import PromptUndoStack

TPayload = TypeVar("TPayload")


class PromptSourceNormalizationResult(Protocol):
    """Expose normalized source text and original boundary remapping."""

    @property
    def text(self) -> str:
        """Return normalized source text."""

    @property
    def boundary_positions(self) -> tuple[int, ...]:
        """Return normalized positions for each original source boundary."""

    @property
    def transitions(self) -> tuple[PromptParenthesisTransition, ...]:
        """Return semantic parenthesis transitions from this normalization."""


class PromptSourceNormalizer(Protocol):
    """Normalize source text at editor ingestion boundaries."""

    def normalize_for_storage(self, text: str) -> PromptSourceNormalizationResult:
        """Normalize full prompt source for storage."""

    def normalize_for_paste_range(
        self,
        text: str,
        *,
        start: int,
        end: int,
    ) -> PromptSourceNormalizationResult:
        """Normalize pasted source inside one full prompt string."""

    def normalize_for_typed_edit_range(
        self,
        text: str,
        *,
        start: int,
        end: int,
        replacement_text: str,
        generated_emphases: tuple[PromptGeneratedEmphasis, ...] = (),
    ) -> PromptSourceNormalizationResult:
        """Normalize one typed edit inside one full prompt string."""


class PromptSourceEditOrigin(str, Enum):
    """Identify the explicit producer of one source edit."""

    TYPED = "typed"
    PASTE = "paste"
    AUTOCOMPLETE = "autocomplete"
    PROGRAMMATIC = "programmatic"


@dataclass(frozen=True, slots=True)
class PromptSourceTextEdit:
    """Describe one contiguous source-text edit between prompt snapshots."""

    start: int
    end: int
    replacement_text: str


@dataclass(frozen=True, slots=True)
class PromptSourceEditResult(Generic[TPayload]):
    """Report a source edit transaction and its undo availability change."""

    previous_snapshot: PromptSourceSnapshot
    next_snapshot: PromptSourceSnapshot
    cursor_state: PromptCursorState
    requested_start: int
    requested_end: int
    requested_replacement_text: str
    source_edit: PromptSourceTextEdit | None
    transitions: tuple[PromptParenthesisTransition, ...] = ()
    undo_availability_change: PromptUndoAvailabilityChange | None = None

    @property
    def source_changed(self) -> bool:
        """Return whether the transaction changed source text."""

        return self.previous_snapshot.source_text != self.next_snapshot.source_text


class PromptSourceEditSession(Generic[TPayload]):
    """Own source text mutation, normalization, and source revision updates."""

    def __init__(
        self,
        *,
        source_buffer: PromptSourceBuffer,
        undo_stack: PromptUndoStack[TPayload],
    ) -> None:
        """Create a source edit session around existing source and undo owners."""

        self._source_buffer = source_buffer
        self._undo_stack = undo_stack

    @property
    def source_text(self) -> str:
        """Return the current source text."""

        return self._source_buffer.source_text

    @property
    def source_revision(self) -> int:
        """Return the current source revision."""

        return self._source_buffer.source_revision

    def snapshot(self) -> PromptSourceSnapshot:
        """Return a snapshot of the current source state."""

        return self._source_buffer.snapshot()

    def replace_full_source(
        self,
        text: str,
        *,
        cursor_position: int,
        anchor_position: int,
        normalizer: PromptSourceNormalizer,
        exact_source: bool,
        record_undo: bool,
        clear_history: bool,
        undo_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptSourceEditResult[TPayload]:
        """Replace the full source text with the requested undo policy."""

        normalization = (
            _identity_source_normalization(text)
            if exact_source
            else normalizer.normalize_for_storage(text)
        )
        next_intents = (
            self._source_buffer.parenthesis_intents
            if text == self._source_buffer.source_text
            else ()
        )
        next_generated_emphases = _generated_emphases_after_normalization(
            existing=(
                self._source_buffer.generated_emphases
                if text == self._source_buffer.source_text
                else ()
            ),
            normalization=normalization,
        )
        return self._apply_replacement(
            normalization.text,
            cursor_position=_mapped_boundary_position(
                normalization.boundary_positions,
                cursor_position,
            ),
            anchor_position=_mapped_boundary_position(
                normalization.boundary_positions,
                anchor_position,
            ),
            requested_start=0,
            requested_end=self._source_buffer.source_length,
            requested_replacement_text=text,
            record_undo=record_undo,
            clear_history=clear_history,
            undo_snapshot=undo_snapshot,
            next_parenthesis_intents=next_intents,
            next_generated_emphases=next_generated_emphases,
            transitions=normalization.transitions,
        )

    def replace_source_range(
        self,
        start: int,
        end: int,
        replacement_text: str,
        *,
        normalizer: PromptSourceNormalizer,
        origin: PromptSourceEditOrigin,
        exact_source: bool,
        record_undo: bool,
        undo_snapshot: PromptUndoSnapshot[TPayload],
    ) -> PromptSourceEditResult[TPayload]:
        """Replace one source range and return normalized cursor/result data."""

        text = self._source_buffer.source_text
        _validate_source_range(text, start=start, end=end)
        updated_text = text[:start] + replacement_text + text[end:]
        requested_cursor_position = start + len(replacement_text)
        edited_generated_emphases = _remap_generated_emphases_for_edit(
            previous_text=text,
            start=start,
            end=end,
            replacement_text=replacement_text,
            existing=self._source_buffer.generated_emphases,
        )
        normalization = _normalize_range_edit(
            previous_text=text,
            updated_text=updated_text,
            start=start,
            replacement_end=requested_cursor_position,
            original_end=end,
            replacement_text=replacement_text,
            normalizer=normalizer,
            origin=origin,
            exact_source=exact_source,
            protected_intents=self._source_buffer.parenthesis_intents,
            generated_emphases=edited_generated_emphases,
        )
        next_intents = _updated_parenthesis_intents(
            previous_text=text,
            next_text=normalization.text,
            start=start,
            end=end,
            replacement_text=replacement_text,
            existing=self._source_buffer.parenthesis_intents,
        )
        next_generated_emphases = _generated_emphases_after_normalization(
            existing=edited_generated_emphases,
            normalization=normalization,
        )
        return self._apply_replacement(
            normalization.text,
            cursor_position=_mapped_boundary_position(
                normalization.boundary_positions,
                requested_cursor_position,
            ),
            anchor_position=_mapped_boundary_position(
                normalization.boundary_positions,
                requested_cursor_position,
            ),
            requested_start=start,
            requested_end=end,
            requested_replacement_text=replacement_text,
            record_undo=record_undo,
            clear_history=False,
            undo_snapshot=undo_snapshot,
            next_parenthesis_intents=next_intents,
            next_generated_emphases=next_generated_emphases,
            transitions=normalization.transitions,
        )

    def synchronize_source_text(
        self,
        text: str,
        *,
        parenthesis_intents: tuple[PromptParenthesisIntent, ...] = (),
        generated_emphases: tuple[PromptGeneratedEmphasis, ...] = (),
    ) -> PromptSourceSnapshot:
        """Synchronize external source application into this session."""

        if text != self._source_buffer.source_text:
            self._source_buffer.source_text = text
            self._source_buffer.source_revision += 1
        self._source_buffer.parenthesis_intents = parenthesis_intents
        self._source_buffer.generated_emphases = generated_emphases
        return self._source_buffer.snapshot()

    def _apply_replacement(
        self,
        next_text: str,
        *,
        cursor_position: int,
        anchor_position: int,
        requested_start: int,
        requested_end: int,
        requested_replacement_text: str,
        record_undo: bool,
        clear_history: bool,
        undo_snapshot: PromptUndoSnapshot[TPayload],
        next_parenthesis_intents: tuple[PromptParenthesisIntent, ...],
        next_generated_emphases: tuple[PromptGeneratedEmphasis, ...],
        transitions: tuple[PromptParenthesisTransition, ...],
    ) -> PromptSourceEditResult[TPayload]:
        """Apply one already-normalized source replacement."""

        previous_snapshot = self._source_buffer.snapshot()
        availability_change = self._undo_stack.clear() if clear_history else None
        if next_text == previous_snapshot.source_text:
            return PromptSourceEditResult(
                previous_snapshot=previous_snapshot,
                next_snapshot=previous_snapshot,
                cursor_state=PromptCursorState(
                    cursor_position=cursor_position,
                    anchor_position=anchor_position,
                ).clamped(previous_snapshot.source_length),
                requested_start=requested_start,
                requested_end=requested_end,
                requested_replacement_text=requested_replacement_text,
                source_edit=None,
                transitions=transitions,
                undo_availability_change=availability_change,
            )

        if record_undo:
            availability_change = self._undo_stack.record_snapshot(undo_snapshot)
        self._source_buffer.source_text = next_text
        self._source_buffer.parenthesis_intents = next_parenthesis_intents
        self._source_buffer.generated_emphases = next_generated_emphases
        self._source_buffer.source_revision += 1
        next_snapshot = self._source_buffer.snapshot()
        return PromptSourceEditResult(
            previous_snapshot=previous_snapshot,
            next_snapshot=next_snapshot,
            cursor_state=PromptCursorState(
                cursor_position=cursor_position,
                anchor_position=anchor_position,
            ).clamped(next_snapshot.source_length),
            requested_start=requested_start,
            requested_end=requested_end,
            requested_replacement_text=requested_replacement_text,
            source_edit=source_text_edit_between(
                previous_snapshot.source_text,
                next_snapshot.source_text,
            ),
            transitions=transitions,
            undo_availability_change=availability_change,
        )


def source_text_edit_between(
    previous_text: str,
    next_text: str,
) -> PromptSourceTextEdit | None:
    """Return the minimal contiguous edit between two source snapshots."""

    if previous_text == next_text:
        return None
    shared_prefix_length = 0
    max_prefix_length = min(len(previous_text), len(next_text))
    while (
        shared_prefix_length < max_prefix_length
        and previous_text[shared_prefix_length] == next_text[shared_prefix_length]
    ):
        shared_prefix_length += 1

    previous_suffix_index = len(previous_text)
    next_suffix_index = len(next_text)
    while (
        previous_suffix_index > shared_prefix_length
        and next_suffix_index > shared_prefix_length
        and previous_text[previous_suffix_index - 1] == next_text[next_suffix_index - 1]
    ):
        previous_suffix_index -= 1
        next_suffix_index -= 1

    return PromptSourceTextEdit(
        start=shared_prefix_length,
        end=previous_suffix_index,
        replacement_text=next_text[shared_prefix_length:next_suffix_index],
    )


def _normalize_range_edit(
    previous_text: str,
    updated_text: str,
    *,
    start: int,
    replacement_end: int,
    original_end: int,
    replacement_text: str,
    normalizer: PromptSourceNormalizer,
    origin: PromptSourceEditOrigin,
    exact_source: bool,
    protected_intents: tuple[PromptParenthesisIntent, ...],
    generated_emphases: tuple[PromptGeneratedEmphasis, ...],
) -> PromptSourceNormalizationResult:
    """Return normalization for one source range replacement."""

    if exact_source or _is_manual_parenthesis_escape_edit(
        previous_text,
        start=start,
        end=original_end,
        replacement_text=replacement_text,
    ):
        return _identity_source_normalization(updated_text)
    if origin in {PromptSourceEditOrigin.PASTE, PromptSourceEditOrigin.AUTOCOMPLETE}:
        return normalizer.normalize_for_paste_range(
            updated_text,
            start=start,
            end=replacement_end,
        )
    if origin is PromptSourceEditOrigin.TYPED:
        if original_end != start:
            return _identity_source_normalization(updated_text)
        if any(
            intent.contains_edit(start, original_end) for intent in protected_intents
        ):
            return _identity_source_normalization(updated_text)
        return normalizer.normalize_for_typed_edit_range(
            updated_text,
            start=start,
            end=replacement_end,
            replacement_text=replacement_text,
            generated_emphases=generated_emphases,
        )
    return _identity_source_normalization(updated_text)


def _is_manual_parenthesis_escape_edit(
    previous_text: str,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> bool:
    """Return whether the user directly added or removed a paren escape."""

    if replacement_text == "\\" and start < len(previous_text):
        return previous_text[start] in "()"
    removed = previous_text[start:end]
    if removed != "\\":
        return False
    return end < len(previous_text) and previous_text[end] in "()"


def _updated_parenthesis_intents(
    *,
    previous_text: str,
    next_text: str,
    start: int,
    end: int,
    replacement_text: str,
    existing: tuple[PromptParenthesisIntent, ...],
) -> tuple[PromptParenthesisIntent, ...]:
    """Remap durable overrides and release them on complete segment replacement."""

    delta = len(next_text) - len(previous_text)
    updated: list[PromptParenthesisIntent] = []
    for intent in existing:
        if start <= intent.segment_start and intent.segment_end <= end:
            continue
        if "," in replacement_text or "," in previous_text[start:end]:
            if start <= intent.segment_end and intent.segment_start <= end:
                continue
        if end <= intent.segment_start:
            updated.append(
                PromptParenthesisIntent(
                    segment_start=intent.segment_start + delta,
                    segment_end=intent.segment_end + delta,
                )
            )
        elif intent.contains_edit(start, end):
            updated.append(
                PromptParenthesisIntent(
                    segment_start=intent.segment_start,
                    segment_end=intent.segment_end + delta,
                )
            )
        else:
            updated.append(intent)
    if _is_manual_parenthesis_escape_edit(
        previous_text,
        start=start,
        end=end,
        replacement_text=replacement_text,
    ):
        segment_start, segment_end = segment_bounds_at(next_text, start)
        updated = [
            intent
            for intent in updated
            if not (
                intent.segment_start == segment_start
                and intent.segment_end == segment_end
            )
        ]
        updated.append(PromptParenthesisIntent(segment_start, segment_end))
    return tuple(sorted(updated, key=lambda intent: intent.segment_start))


def _remap_generated_emphases_for_edit(
    *,
    previous_text: str,
    start: int,
    end: int,
    replacement_text: str,
    existing: tuple[PromptGeneratedEmphasis, ...],
) -> tuple[PromptGeneratedEmphasis, ...]:
    """Remap generated-weight provenance while treating weight edits as authored."""

    if not existing:
        return ()
    delta = len(replacement_text) - (end - start)
    content_ranges = {
        (span.outer_range.start, span.outer_range.end): span.content_range
        for span in parse_prompt_document(previous_text).emphasis_spans
    }
    remapped: list[PromptGeneratedEmphasis] = []
    for generated in existing:
        if end <= generated.source_start:
            remapped.append(
                PromptGeneratedEmphasis(
                    source_start=generated.source_start + delta,
                    source_end=generated.source_end + delta,
                    nesting_depth=generated.nesting_depth,
                )
            )
            continue
        if generated.source_end <= start:
            remapped.append(generated)
            continue
        content_range = content_ranges.get(
            (generated.source_start, generated.source_end)
        )
        if (
            content_range is not None
            and content_range.start <= start
            and end <= content_range.end
        ):
            remapped.append(
                PromptGeneratedEmphasis(
                    source_start=generated.source_start,
                    source_end=generated.source_end + delta,
                    nesting_depth=generated.nesting_depth,
                )
            )
    return tuple(remapped)


def _generated_emphases_after_normalization(
    *,
    existing: tuple[PromptGeneratedEmphasis, ...],
    normalization: PromptSourceNormalizationResult,
) -> tuple[PromptGeneratedEmphasis, ...]:
    """Reconcile generated-weight provenance with semantic normalization output."""

    replaced_ranges = tuple(
        (transition.source_start, transition.source_end)
        for transition in normalization.transitions
    )
    generated_by_range: dict[tuple[int, int], PromptGeneratedEmphasis] = {}
    for generated in existing:
        if any(
            transition_start <= generated.source_start
            and generated.source_end <= transition_end
            for transition_start, transition_end in replaced_ranges
        ):
            continue
        mapped = PromptGeneratedEmphasis(
            source_start=normalization.boundary_positions[generated.source_start],
            source_end=normalization.boundary_positions[generated.source_end],
            nesting_depth=generated.nesting_depth,
        )
        generated_by_range[(mapped.source_start, mapped.source_end)] = mapped
    for transition in normalization.transitions:
        if transition.kind is not PromptParenthesisTransitionKind.IMPLICIT_EMPHASIS:
            continue
        generated = PromptGeneratedEmphasis(
            source_start=normalization.boundary_positions[transition.source_start],
            source_end=normalization.boundary_positions[transition.source_end],
            nesting_depth=transition.nesting_depth,
        )
        generated_by_range[(generated.source_start, generated.source_end)] = generated
    return tuple(
        generated_by_range[key]
        for key in sorted(generated_by_range, key=lambda bounds: bounds[0])
    )


def _identity_source_normalization(text: str) -> PromptSourceNormalizationResult:
    """Return source text unchanged with one-to-one boundary mapping."""

    return _PromptIdentitySourceNormalization(
        text=text,
        boundary_positions=tuple(range(len(text) + 1)),
    )


@dataclass(frozen=True, slots=True)
class _PromptIdentitySourceNormalization:
    """Represent exact source text as a normalization result."""

    text: str
    boundary_positions: tuple[int, ...]
    transitions: tuple[PromptParenthesisTransition, ...] = ()


def _mapped_boundary_position(
    boundary_positions: tuple[int, ...], position: int
) -> int:
    """Return the normalized boundary position for an original source position."""

    if not 0 <= position < len(boundary_positions):
        raise ValueError("Source boundary position is outside the normalized text.")
    return boundary_positions[position]


def _validate_source_range(text: str, *, start: int, end: int) -> None:
    """Reject invalid source edit ranges before mutation."""

    if start < 0 or end < start or end > len(text):
        raise ValueError("Source edit range is outside the source text.")


__all__ = [
    "PromptSourceEditResult",
    "PromptSourceEditOrigin",
    "PromptSourceEditSession",
    "PromptSourceNormalizer",
    "PromptSourceNormalizationResult",
    "PromptSourceTextEdit",
    "source_text_edit_between",
]
