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

"""Verify production prompt-field wiring to the cube buffer."""

from __future__ import annotations

from typing import Any, cast

from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_edits_update_cube_buffer_through_field_wiring(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Persist typed prompt edits through the editor-panel field wiring."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="old prompt")

    real_shell_scenario.input.replace_text_with_keys(field, "updated prompt")
    real_shell_scenario.wait_until(
        lambda: field.editor.toPlainText() == "updated prompt"
    )

    nodes = cast(dict[str, dict[str, Any]], field.workflow.cube_state.buffer["nodes"])
    node = nodes[field.node_name]
    assert node["inputs"][field.field_key] == "updated prompt"
    assert field.workflow.cube_state.dirty is True
