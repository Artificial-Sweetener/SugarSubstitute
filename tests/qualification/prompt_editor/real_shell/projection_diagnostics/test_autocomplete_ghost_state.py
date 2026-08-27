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

"""Verify diagnostics for stale autocomplete ghost ownership."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_reports_stale_visible_ghost_owner_state(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Detect paint-visible ghost state after autocomplete owners are cleared."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="backpack")
    real_shell_scenario.input.move_cursor_to_end(field)
    editor = field.editor
    surface = cast(Any, getattr(editor, "_surface"))
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("backpack"),
            suffix_text=" basket",
        )
    )
    stale_preview_document = cast(Any, surface)._layout.frame.output.projection_document

    surface.set_autocomplete_preview_state(None)
    cast(Any, surface)._layout.set_projection(
        stale_preview_document,
        prompt_document_view=surface.prompt_document_view(),
    )
    snapshot = real_shell_scenario.snapshots.capture(
        field,
        label="forced-stale-visible-ghost-owner-state",
    )

    violations = snapshot_invariant_violations(snapshot)

    assert snapshot.autocomplete_preview_active is False
    assert snapshot.autocomplete_ghost_paint_visible_by_owner_state is True
    assert "backpack basket" in snapshot.layout_projection_text
    assert "autocomplete_ghost_paint_visible_without_preview_state" in violations
    assert "layout_projection_preview_leaked_without_preview_state" in violations
    assert "layout_not_restored_to_base_projection_document" in violations
