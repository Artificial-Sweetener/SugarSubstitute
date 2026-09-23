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

"""Project session-owned exact-weight editing onto semantic tokens."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


@dataclass(frozen=True, slots=True)
class PromptExactWeightEditProjection:
    """Describe exact-edit presentation state matched to one token."""

    value_text: str
    slot_width: float
    caret_index: int
    select_all: bool


def exact_weight_edit_for_token(
    session: PromptProjectionSession,
    *,
    token_id: str,
    content_start: int,
    content_end: int,
) -> PromptExactWeightEditProjection | None:
    """Return active exact-edit state when it belongs to one token."""

    edit_state = session.exact_weight_edit
    if edit_state is None:
        return None
    if edit_state.token_id == token_id or (
        edit_state.synthetic
        and edit_state.content_start == content_start
        and edit_state.content_end == content_end
    ):
        return PromptExactWeightEditProjection(
            value_text=edit_state.buffer_text,
            slot_width=edit_state.slot_width,
            caret_index=edit_state.caret_index,
            select_all=edit_state.select_all,
        )
    return None


__all__ = ["PromptExactWeightEditProjection", "exact_weight_edit_for_token"]
