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

from PySide6.QtGui import QTextCursor

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
    surface = cast(Any, editor._runtime.projection.surface)
    surface.autocomplete_preview.set_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("backpack"),
            suffix_text=" basket",
        )
    )
    stale_preview_document = cast(Any, surface)._layout.frame.output.projection_document

    surface.autocomplete_preview.set_preview_state(None)
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


def test_selection_replacement_autocomplete_preview_owns_immediate_layout(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Autocomplete preview after replacement typing must own mounted geometry."""

    decorated_unit = (
        "masterpiece, (detailed face:1.20), {lighting/day}, "
        "<lora:detail_booster:0.80>, cinematic background, "
    )
    source = decorated_unit * 90
    start = len(source) // 2
    end = start + len("masterpiece, (detailed face:1.20)")
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    editor = field.editor
    cursor = editor.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    runtime = cast(Any, editor)._runtime
    surface = runtime.projection.surface
    semantic_refresh = runtime.core.syntax.interaction_controller._semantic_refresh

    def owners_are_current(expected_source: str) -> bool:
        """Return whether source, semantics, and projection finished publication."""

        return bool(
            editor.toPlainText() == expected_source
            and surface.projection_document().source_text == expected_source
            and surface.editor_state.semantic.document.source_text == expected_source
            and not surface._projection_freshness_controller.has_pending_update()
            and not surface.has_stale_projection_geometry()
            and semantic_refresh._pending_request is None
            and semantic_refresh._active_task_identity is None
        )

    expected_source = source[:start] + "r" + source[end:]
    real_shell_scenario.input.type_text(field, "r")
    real_shell_scenario.wait_until(lambda: owners_are_current(expected_source))

    expected_source = source[:start] + "re" + source[end:]
    real_shell_scenario.input.type_text(field, "e")
    real_shell_scenario.wait_until(lambda: owners_are_current(expected_source))
    immediate = real_shell_scenario.snapshots.capture(
        field,
        label="selection-replacement-autocomplete-preview-published",
        settle=False,
    )

    assert immediate.autocomplete_preview_active
    assert immediate.active_projection_layout_required
    assert immediate.layout_uses_active_projection_document
