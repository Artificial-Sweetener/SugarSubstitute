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

"""Verify immutable effective projection values prepared before painting."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionInlineObjectFragment,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintState,
)
from tests.support.prompt_editor.projection_layout_support import projection_layout_for


def test_paint_input_reuses_prepared_effective_projection_values() -> None:
    """Do not allocate replacement runs or tokens during repeated paint lookup."""

    layout, projection = projection_layout_for("(cat:1.05), suffix")
    token = projection.tokens[0]
    run = next(run for run in projection.runs if run.token_id == token.token_id)
    layout.frame.set_paint_state(
        PromptProjectionPaintState(
            active_token_ids=frozenset((token.token_id,)),
            active_run_ids=frozenset((run.run_id,)),
        )
    )
    paint_input = layout.frame.paint_input

    first_token = paint_input.effective_token(token.token_id)
    first_run = paint_input.effective_run(run.run_id)

    assert first_token is paint_input.effective_token(token.token_id)
    assert first_run is paint_input.effective_run(run.run_id)
    assert first_token is not None and first_token.active
    assert first_run is not None and first_run.active
    first_style = paint_input.text_style(run.run_id)
    assert first_style is paint_input.text_style(run.run_id)
    fragment = next(
        fragment
        for line in paint_input.layout_snapshot.lines
        for fragment in line.fragments
        if isinstance(fragment, PromptProjectionInlineObjectFragment)
        and fragment.token_id == token.token_id
        and fragment.run_id == run.run_id
    )
    first_binding = paint_input.inline_binding(fragment)
    assert first_binding is paint_input.inline_binding(fragment)
    assert first_binding is not None
    assert first_binding.run.active
    assert first_binding.token.active
