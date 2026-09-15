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

"""Capture native numeric input state independently of the prompt's source caret."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.projection_engine_support import surface_for


@dataclass(frozen=True, slots=True)
class ExactWeightInputSnapshot:
    """Describe the actual Qt input owner while an inline weight edit is active."""

    text: str
    cursor_position: int
    selection_start: int
    selected_text: str
    visible: bool
    focused: bool
    token_id: str | None
    projected_text: str | None


def exact_weight_input_snapshot(
    editor: PromptEditor,
) -> ExactWeightInputSnapshot | None:
    """Read native selection directly rather than infer it from the source prompt."""

    owner = surface_for(editor).exact_weight_editor
    if not owner.active:
        return None
    token = owner.token()
    return ExactWeightInputSnapshot(
        text=owner.text(),
        cursor_position=owner.cursorPosition(),
        selection_start=owner.selectionStart(),
        selected_text=owner.selectedText(),
        visible=owner.isVisible(),
        focused=owner.hasFocus(),
        token_id=token.token_id if token is not None else None,
        projected_text=token.editing_value_text if token is not None else None,
    )


def exact_weight_input_violations(
    state: ExactWeightInputSnapshot | None,
) -> tuple[str, ...]:
    """Validate native Qt offsets and the derived projected value without IO."""

    if state is None:
        return ()
    violations: list[str] = []
    length = len(state.text.encode("utf-16-le")) // 2
    if not 0 <= state.cursor_position <= length:
        violations.append("exact_weight_caret_out_of_bounds")
    selection_length = len(state.selected_text.encode("utf-16-le")) // 2
    if selection_length:
        if not 0 <= state.selection_start <= length - selection_length:
            violations.append("exact_weight_selection_out_of_bounds")
    elif state.selection_start != -1:
        violations.append("exact_weight_empty_selection_has_start")
    if state.token_id is None or state.projected_text != state.text:
        violations.append("exact_weight_projection_does_not_match_input")
    if not state.visible:
        violations.append("exact_weight_active_input_is_hidden")
    return tuple(violations)
