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

"""Qualify graph-inferred PromptEditor mounting across workflow owners."""

from __future__ import annotations

from pathlib import Path

from tests.qualification.comfy.bundled_workflows.direct_workflow_scenarios.support import (
    deterministic_sdxl_fixture,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.rendering import (
    rendered_node_card_order,
    rendered_prompt_fields,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.workflows import (
    load_direct_workflow,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_sdxl_fixture_mounts_inferred_prompt_editors(tmp_path: Path) -> None:
    """SDXL primitive prompts should use the production PromptEditor widget."""

    harness = DirectWorkflowShell(tmp_path)
    try:
        fixture = deterministic_sdxl_fixture()
        load_direct_workflow(
            harness,
            fixture.path,
            node_definitions=fixture.node_definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )

        assert rendered_prompt_fields(harness) == (("50", "text"), ("51", "text"))
        assert rendered_node_card_order(harness)[:2] == ("51", "50")
    finally:
        harness.close()


def test_real_shell_cube_mounts_graph_inferred_prompt_editor(tmp_path: Path) -> None:
    """Cube-local topology should mount and edit through the production PromptEditor."""

    harness = PromptEditorRealShellScenario(artifact_root=tmp_path)
    try:
        field = harness.workflows.add_inferred_prompt_workflow(initial_text="initial")

        assert harness.workflows.probes.rendered_node_card_order(field)[:2] == (
            "encoder",
            "ordinary",
        )

        harness.input.replace_text_with_keys(field, "updated prompt")

        nodes = field.workflow.cube_state.buffer["nodes"]
        assert isinstance(nodes, dict)
        encoder = nodes["encoder"]
        assert isinstance(encoder, dict)
        assert encoder["inputs"] == {"text": "updated prompt"}
    finally:
        harness.close()
