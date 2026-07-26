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

"""Resolve visible horizontal caret targets across structural region separators."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretMap,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)


def skip_region_separator_caret_states(
    caret_map: PromptProjectionCaretMap,
    candidate: PromptProjectionCaretState,
    *,
    direction: int,
) -> PromptProjectionCaretState:
    """Skip hidden separator edge states until a visible source caret is reached."""

    if direction == 0:
        raise ValueError("Region caret navigation direction must not be zero.")
    state = candidate
    while _is_region_separator_state(caret_map, state):
        next_state = (
            caret_map.next_state(state)
            if direction > 0
            else caret_map.previous_state(state)
        )
        if next_state == state:
            return state
        state = next_state
    return state


def resolve_region_separator_line_caret_state(
    caret_map: PromptProjectionCaretMap,
    candidate: PromptProjectionCaretState,
    *,
    line_source_start: int,
    line_source_end: int,
) -> PromptProjectionCaretState:
    """Resolve a shared separator edge to the visible line that was clicked."""

    token = caret_map.token_by_id(candidate.token_id)
    if token is None or token.kind is not PromptProjectionTokenKind.REGION_SEPARATOR:
        return candidate
    if line_source_start >= token.source_end:
        return skip_region_separator_caret_states(
            caret_map,
            candidate,
            direction=1,
        )
    if line_source_end <= token.source_start:
        return skip_region_separator_caret_states(
            caret_map,
            candidate,
            direction=-1,
        )
    return candidate


def _is_region_separator_state(
    caret_map: PromptProjectionCaretMap,
    state: PromptProjectionCaretState,
) -> bool:
    """Return whether one caret state belongs to hidden separator source."""

    token = caret_map.token_by_id(state.token_id)
    return (
        token is not None and token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )


__all__ = [
    "resolve_region_separator_line_caret_state",
    "skip_region_separator_caret_states",
]
