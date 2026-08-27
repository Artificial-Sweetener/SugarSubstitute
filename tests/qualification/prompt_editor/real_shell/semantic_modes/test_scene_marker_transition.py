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

"""Verify scene-state transitions when prompt semantics change in place."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.prompt_editor.diagnostics.models import PromptDiagnosticKind
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_same_source_semantics_switch_rebuilds_scene_state(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Remove scenes and publish marker diagnostics after a semantics switch."""

    source = "**portrait\n{missing}"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    editor = cast(Any, field.editor)
    real_shell_scenario.wait_until(
        lambda: any(
            token.kind.value == "scene"
            for token in editor._surface.projection_document().tokens
        )
    )

    editor.replaceBaselineSourceDocument(source, WildcardTextDocumentSemantics())
    editor._diagnostics_feature_controller.refresh_now()
    real_shell_scenario.wait_until(
        lambda: all(
            token.kind.value != "scene"
            for token in editor._surface.projection_document().tokens
        )
    )
    real_shell_scenario.wait_until(
        lambda: any(
            diagnostic.kind is PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER
            for diagnostic in editor._diagnostics_feature_controller.presentation.snapshot.diagnostics
        )
    )

    assert editor.toPlainText() == source
    prepared_scene = editor._scene_position_preparation.prepare_position_context(
        0,
        reason="unsupported_scene_marker_assertion",
    )
    assert prepared_scene.context is not None
    assert prepared_scene.context.scene_key is None
    assert (
        editor._document_service.scene_autocomplete_query_at_cursor(
            text=source,
            cursor_position=2,
            has_selection=False,
        )
        is None
    )
