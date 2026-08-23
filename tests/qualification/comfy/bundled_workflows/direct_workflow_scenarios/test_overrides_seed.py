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

"""Qualify direct-workflow global overrides and seed-control rendering."""

from __future__ import annotations

from pathlib import Path

from substitute.application.direct_workflows import (
    DirectWorkflowGenerationPlanService,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_scenarios.support import (
    deterministic_sdxl_fixture,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.overrides import (
    RenderedSeedControlProbe,
    active_override_keys,
    install_cube_seed_control,
    seed_field_probe,
    seed_toolbar_probe,
    set_global_override_value,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.workflows import (
    load_direct_workflow,
)


def _seed_widget_geometry(probe: RenderedSeedControlProbe) -> tuple[object, ...]:
    """Return SeedBox-owned geometry independent of its external surface label."""

    return (
        probe.widget_type,
        probe.size,
        probe.size_hint,
        probe.minimum_size_hint,
        probe.size_policy,
        probe.line_edit_geometry,
        probe.split_button_geometry,
    )


def test_real_shell_sdxl_global_override_updates_direct_api_graph(
    tmp_path: Path,
) -> None:
    """A toolbar commit should update direct state and the emitted Comfy API graph."""

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

        assert {"sampler_name", "scheduler", "seed"} <= set(
            active_override_keys(harness)
        )

        set_global_override_value(harness, "seed", 424242)
        workflow = harness.shell.workflow_session_service.get_workflow(
            harness.direct_workflow_id
        )
        assert workflow is not None
        assert workflow.direct_workflow is not None
        assert workflow.global_overrides["seed"]["value"] == 424242

        generation_plan = DirectWorkflowGenerationPlanService().build(
            workflow.direct_workflow
        )
        sampler_inputs: list[dict[object, object]] = []
        for node in generation_plan.authored_api_graph.values():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") != "KSamplerAdvanced":
                continue
            inputs = node.get("inputs")
            assert isinstance(inputs, dict)
            sampler_inputs.append(inputs)
        assert sampler_inputs
        assert all(inputs["noise_seed"] == 424242 for inputs in sampler_inputs)
    finally:
        harness.close()


def test_real_cube_and_direct_comfy_seed_controls_share_one_render_contract(
    tmp_path: Path,
) -> None:
    """Production cube seed and Comfy noise_seed surfaces should render identically."""

    harness = DirectWorkflowShell(tmp_path)
    try:
        fixture = deterministic_sdxl_fixture()
        definitions = dict(fixture.node_definitions)
        definitions["KSampler"] = {
            "input": {
                "required": {
                    "seed": ["INT", {"default": 0, "min": 0, "max": 999999}],
                }
            }
        }
        install_cube_seed_control(harness, node_definitions=definitions)
        cube_field = seed_field_probe(harness, harness.cube_workflow_id, "seed")
        cube_toolbar = seed_toolbar_probe(harness, harness.cube_workflow_id)

        load_direct_workflow(
            harness,
            fixture.path,
            node_definitions=definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )
        direct_field = seed_field_probe(
            harness,
            harness.direct_workflow_id,
            "noise_seed",
        )
        direct_toolbar = seed_toolbar_probe(harness, harness.direct_workflow_id)

        assert cube_field.label_text == "Seed"
        assert direct_field.label_text == "Noise Seed"
        assert not cube_field.label_explicitly_hidden
        assert not direct_field.label_explicitly_hidden
        assert _seed_widget_geometry(direct_field) == _seed_widget_geometry(cube_field)

        assert cube_toolbar.label_text == "Seed"
        assert direct_toolbar.label_text == "Seed"
        assert cube_toolbar.label_visible == direct_toolbar.label_visible
        assert not cube_toolbar.label_explicitly_hidden
        assert not direct_toolbar.label_explicitly_hidden
        assert _seed_widget_geometry(direct_toolbar) == _seed_widget_geometry(
            cube_toolbar
        )
    finally:
        harness.close()
