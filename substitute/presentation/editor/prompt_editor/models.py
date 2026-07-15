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

"""Define typed presentation-local state for prompt editor interactions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor import (
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
    PromptReorderLayoutView,
    PromptReorderStateView,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)


class PromptEditorInteractionMode(Enum):
    """Describe the prompt editor's current presentation interaction mode."""

    TEXT_EDITING = auto()
    SEGMENT_REORDER = auto()


@dataclass(slots=True)
class AutocompleteSession:
    """Store the active autocomplete selection and replacement bounds."""

    mode: str = "none"
    suggestions: tuple[PromptAutocompleteSuggestion, ...] = ()
    selected_index: int = -1
    word_start: int | None = None
    word_end: int | None = None
    active_tag_end: int | None = None
    prefix: str = ""
    lora_candidates: tuple[PromptLoraAutocompleteCandidate, ...] = ()
    lora_query: PromptLoraAutocompleteQuery | None = None
    scene_query: PromptSceneAutocompleteQuery | None = None
    wildcard_query: PromptWildcardAutocompleteQuery | None = None


@dataclass(slots=True)
class SegmentReorderSession:
    """Store controller-owned commit session state for Alt-held reorder mode.

    Writer:
        `PromptReorderSessionController` writes this state when reorder starts,
        when pointer/keyboard reorder prepares a commit snapshot, and when
        cancel or close clears the session.
    Readers:
        The controller commit path and focused interaction tests read it.
    State kind:
        Commit state. Projection preview and animation state must not overwrite
        this state except through explicit controller snapshot capture.
    """

    is_active: bool = False
    original_ordered_indices: tuple[int, ...] = ()
    current_ordered_indices: tuple[int, ...] = ()
    original_reorder_state: PromptReorderStateView | None = None
    current_reorder_state: PromptReorderStateView | None = None
    active_segment_index: int | None = None
    dragged_segment_index: int | None = None
    selection_start: int | None = None
    selection_end: int | None = None
    selection_start_offset_within_active_chip: int | None = None
    selection_end_offset_within_active_chip: int | None = None
    has_reordered: bool = False


PromptReorderKeyboardDirection = Literal["left", "right", "up", "down"]


@dataclass(frozen=True, slots=True)
class PromptReorderCommitSnapshot:
    """Describe authoritative reorder state available for command commit.

    Writer:
        `PromptReorderSessionController` stores the authoritative snapshot
        consumed by the reorder controller on Alt release. The overlay may
        prepare a typed snapshot, but it does not mutate source directly.
    Readers:
        The controller commit path and tests read this state before routing
        source mutation through the reorder command boundary.
    State kind:
        Commit state. It is independent from preview and animation state.
    """

    reorder_state: PromptReorderStateView | None
    layout_view: PromptReorderLayoutView | None
    ordered_chip_indices: tuple[int, ...]
    active_segment_index: int | None
    dragged_segment_index: int | None
    has_reordered: bool


@dataclass(frozen=True, slots=True)
class PromptReorderCommitIntent:
    """Request that the current prepared reorder preview be committed."""

    reason: str
    snapshot: PromptReorderCommitSnapshot | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderCancelIntent:
    """Request that the current reorder interaction be canceled."""

    reason: str
    restore_selection: bool = True


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardMoveIntent:
    """Request one keyboard navigation step within reorder mode."""

    direction: PromptReorderKeyboardDirection
