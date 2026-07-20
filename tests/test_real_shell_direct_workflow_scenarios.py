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

"""Prove cube/direct animated layout invariants in the production shell scaffold."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.editor.panel.content_gutter_controller import (
    DIRECT_WORKFLOW_LEFT_GUTTER,
)
from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
)
from substitute.application.direct_workflows import (
    DirectWorkflowGenerationPlanService,
)
from substitute.application.workspace_state import WorkspaceMaterializationService
from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPresentationMode,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)
from substitute.presentation.shell.restored_workflow_materializer import (
    RestoredWorkflowMaterializer,
)
from tests.headless_workspace_restore_harness import (
    HarnessNodeDefinitionGateway,
    HeadlessWorkspaceRestoreHarness,
)
from tests.real_shell_direct_workflow_harness import (
    RealShellDirectWorkflowHarness,
    RenderedSeedControlProbe,
)
from tests.prompt_detection_fixture_catalog import (
    PromptDetectionFixture,
    deterministic_prompt_detection_fixtures,
)
from tests.real_shell_prompt_editor_harness import RealShellPromptEditorHarness


def _deterministic_sdxl_fixture() -> PromptDetectionFixture:
    """Return the repository-owned SDXL projection fixture."""

    return deterministic_prompt_detection_fixtures(Path(__file__).parents[1])[0]


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


def test_real_shell_cube_direct_animation_and_artifacts(tmp_path: Path) -> None:
    """Rendered endpoints must preserve editor width and transfer stack width to canvas."""

    artifact_root = tmp_path
    harness = RealShellDirectWorkflowHarness()
    try:
        cube = harness.capture(artifact_root / "cube.png", "cube")
        harness.activate_direct(animated=True)
        harness.wait_for_intermediate_transition()
        mid = harness.capture(artifact_root / "mid.png", "mid")
        harness.wait_for_transition()
        direct = harness.capture(artifact_root / "direct.png", "direct")

        harness.activate_cube(animated=True)
        harness.wait_for_transition()
        restored = harness.capture(artifact_root / "restored.png", "restored")
        probes = [cube, mid, direct, restored]
        harness.write_report(artifact_root / "geometry.json", probes)

        assert cube.mode == CubeStackPresentationMode.EXPANDED.value
        assert (cube.editor_left_gutter, cube.editor_right_gutter) == (6, 14)
        assert mid.animating
        assert 0 < mid.container_width < CUBE_STACK_EXPANDED_WIDTH
        assert 6 <= mid.editor_left_gutter <= DIRECT_WORKFLOW_LEFT_GUTTER
        assert mid.editor_right_gutter == 14
        assert direct.mode == CubeStackPresentationMode.UNAVAILABLE.value
        assert direct.container_width == 0
        assert not direct.container_visible
        assert not direct.button_enabled
        assert (direct.editor_left_gutter, direct.editor_right_gutter) == (
            DIRECT_WORKFLOW_LEFT_GUTTER,
            14,
        )
        assert abs(direct.editor_width - cube.editor_width) <= 2
        assert (
            cube.editor_global_left - direct.editor_global_left
            == CUBE_STACK_EXPANDED_WIDTH
        )
        assert direct.canvas_width - cube.canvas_width == CUBE_STACK_EXPANDED_WIDTH
        assert restored.mode == CubeStackPresentationMode.EXPANDED.value
        assert (restored.editor_left_gutter, restored.editor_right_gutter) == (6, 14)
        assert abs(restored.editor_width - cube.editor_width) <= 2
        assert restored.splitter_sizes == cube.splitter_sizes
        assert restored.generation > direct.generation

        payload = json.loads((artifact_root / "geometry.json").read_text("utf-8"))
        assert [row["label"] for row in payload] == [
            "cube",
            "mid",
            "direct",
            "restored",
        ]
        assert all(
            (artifact_root / name).stat().st_size > 1000
            for name in (
                "cube.png",
                "mid.png",
                "direct.png",
                "restored.png",
            )
        )
    finally:
        harness.close()


def test_real_shell_materializes_persisted_direct_workflow_without_cube_stack(
    tmp_path: Path,
) -> None:
    """The real shell should restore direct cards through the unified materializer."""

    restore_harness = HeadlessWorkspaceRestoreHarness(tmp_path / "restore")
    assert restore_harness.force_save() is True
    plan = restore_harness.build_restore_plan()
    assert plan.workspace is not None
    hydrated = restore_harness.hydrate(plan.workspace)
    shell_harness = RealShellDirectWorkflowHarness()
    try:
        shell_harness.shell.node_definition_gateway.install_recorded_definitions(
            HarnessNodeDefinitionGateway.definitions
        )
        setattr(
            shell_harness.shell,
            "restored_workflow_materializer",
            RestoredWorkflowMaterializer(shell_harness.shell),
        )
        setattr(
            shell_harness.shell,
            "restore_projection_controller",
            RestoreProjectionController(shell_harness.shell),
        )
        setattr(
            shell_harness.shell,
            "workspace_controller",
            shell_harness.shell.workflow_workspace,
        )
        setattr(
            shell_harness.shell,
            "workspace_restore_image_adapter",
            SimpleNamespace(),
        )
        setattr(
            shell_harness.shell,
            "shell_layout_restore_controller",
            SimpleNamespace(apply_restored_shell_layout=lambda _snapshot: None),
        )
        WorkspaceMaterializationService().materialize(
            hydrated,
            ShellWorkspaceMaterializationPort(shell_harness.shell),
        )
        panel = shell_harness.shell.editor_panels["direct"]
        shell_harness.wait_for_rendered_node_names(
            frozenset({"10"}),
            workflow_id="direct",
        )

        restored = shell_harness.shell.workflow_session_service.get_workflow("direct")
        assert restored is not None
        assert restored.direct_workflow is not None
        assert restored.direct_workflow.buffer["nodes"]["10"]["mode"] == 4  # type: ignore[index]
        assert (
            shell_harness.shell.workflow_session_service.active_workflow_id == "direct"
        )
        assert "direct" in shell_harness.shell.editor_panels
        assert "direct" not in shell_harness.shell.cube_stacks
        rendered_cards = {
            (str(node_name), str(class_type))
            for widget in panel.findChildren(QWidget)
            if (node_name := widget.property("node_name"))
            and (class_type := widget.property("node_class_type"))
        }
        assert rendered_cards == {("10", "KSampler")}
    finally:
        shell_harness.close()


def test_real_shell_rapid_reversal_settings_reduced_motion_and_restore() -> None:
    """Retargeting and non-animated paths must retain mode and chrome ownership."""

    harness = RealShellDirectWorkflowHarness()
    app = harness.app
    previous_reduced_motion = app.property("substitute.reduce_motion")
    try:
        harness.activate_direct(animated=True)
        harness.wait_for_intermediate_transition()
        before_reverse = harness.probe("before-reverse")
        harness.activate_cube(animated=True)
        after_reverse = harness.probe("after-reverse")
        assert (
            before_reverse.container_width
            <= after_reverse.container_width
            < CUBE_STACK_EXPANDED_WIDTH
        )
        assert (
            6
            <= after_reverse.editor_left_gutter
            <= before_reverse.editor_left_gutter
            <= DIRECT_WORKFLOW_LEFT_GUTTER
        )
        harness.wait_for_transition()
        assert (
            harness.probe("reversed").mode == CubeStackPresentationMode.EXPANDED.value
        )

        harness.activate_direct(animated=True)
        harness.wait_for_transition()
        controller = harness.shell.cube_stack_presentation_controller
        controller.set_workflow_route_active(False)
        assert not harness.shell.cubeStackModeButton.isEnabled()
        controller.set_workflow_route_active(True)
        assert not harness.shell.cubeStackModeButton.isEnabled()

        app.setProperty("substitute.reduce_motion", True)
        harness.activate_cube(animated=True)
        assert not controller.is_animating
        controller.restore_preference(True)
        harness.activate_direct(animated=False)
        restored_direct = harness.probe("restored-direct")
        assert restored_direct.mode == CubeStackPresentationMode.UNAVAILABLE.value
        assert restored_direct.container_width == 0
        harness.activate_cube(animated=False)
        restored_compact = harness.probe("restored-compact")
        assert restored_compact.mode == CubeStackPresentationMode.COMPACT.value
        assert restored_compact.container_width == CUBE_STACK_COMPACT_WIDTH
        assert restored_compact.button_checked
    finally:
        app.setProperty("substitute.reduce_motion", previous_reduced_motion)
        harness.close()


def test_real_shell_sdxl_fixture_renders_regular_widgets() -> None:
    """The SDXL projection fixture should render through production widget owners."""

    harness = RealShellDirectWorkflowHarness()
    try:
        fixture = _deterministic_sdxl_fixture()
        harness.load_direct_workflow(
            fixture.path,
            node_definitions=fixture.node_definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )

        cards = harness.rendered_node_cards()
        classes = {class_type for _node_id, class_type in cards}
        primitive_ids = {
            node_id for node_id, class_type in cards if class_type == "PrimitiveNode"
        }

        assert primitive_ids == {"45", "47", "50", "51"}
        assert "CheckpointLoaderSimple" in classes
        assert "EmptyLatentImage" in classes
        assert "KSamplerAdvanced" in classes
        assert "SaveImage" not in classes
        assert "MarkdownNote" not in classes
    finally:
        harness.close()


def test_real_shell_sdxl_fixture_mounts_inferred_prompt_editors() -> None:
    """SDXL primitive prompts should use the production PromptEditor widget."""

    harness = RealShellDirectWorkflowHarness()
    try:
        fixture = _deterministic_sdxl_fixture()
        harness.load_direct_workflow(
            fixture.path,
            node_definitions=fixture.node_definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )

        assert harness.rendered_prompt_fields() == (("50", "text"), ("51", "text"))
        assert harness.rendered_node_card_order()[:2] == ("51", "50")
    finally:
        harness.close()


def test_real_shell_dynamic_combo_replaces_active_nested_fields(tmp_path: Path) -> None:
    """Changing a native dynamic selector should rebuild its card descendants."""

    workflow_path = tmp_path / "dynamic-combo.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "NativeDynamicNode",
                        "inputs": [],
                        "outputs": [],
                        "widgets_values": ["Quality", "a lighthouse", 7],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    definitions = {
        "NativeDynamicNode": {
            "input": {
                "required": {
                    "model": [
                        "COMFY_DYNAMICCOMBO_V3",
                        {
                            "options": [
                                {
                                    "key": "Quality",
                                    "inputs": {
                                        "required": {
                                            "prompt": [
                                                "STRING",
                                                {"default": "", "multiline": True},
                                            ]
                                        }
                                    },
                                },
                                {
                                    "key": "Speed",
                                    "inputs": {
                                        "required": {
                                            "steps": [
                                                "INT",
                                                {"default": 4, "min": 1, "max": 20},
                                            ]
                                        }
                                    },
                                },
                            ]
                        },
                    ],
                    "seed": ["INT", {"default": 0}],
                }
            }
        }
    }
    harness = RealShellDirectWorkflowHarness()
    try:
        harness.load_direct_workflow(
            workflow_path,
            node_definitions=definitions,
            expected_node_names=frozenset({"1"}),
        )
        panel = harness.shell.editor_panels[harness.direct_workflow_id]
        registered_fields = cast(
            dict[tuple[str, str, str], object],
            getattr(cast(Any, panel), "input_widgets_by_field_key"),
        )

        def node_fields() -> dict[str, object]:
            """Return current registered fields for the dynamic node."""

            return {
                field_key: widget
                for (_alias, node_name, field_key), widget in registered_fields.items()
                if node_name == "1"
            }

        initial_fields = node_fields()
        assert set(initial_fields) == {"model", "model.prompt", "seed"}
        binding = EditorFieldBinding.from_widget(initial_fields["model"])
        assert binding is not None
        assert binding.native_widget_type == "COMFY_DYNAMICCOMBO_V3"

        set_current_text = getattr(initial_fields["model"], "setCurrentText")
        set_current_text("Speed")
        harness.process_events()
        workflow = harness.shell.workflow_session_service.get_workflow(
            harness.direct_workflow_id
        )
        assert workflow is not None and workflow.direct_workflow is not None
        converted_nodes = workflow.direct_workflow.buffer["nodes"]
        assert isinstance(converted_nodes, dict)
        dynamic_node = converted_nodes["1"]
        assert isinstance(dynamic_node, dict)
        assert dynamic_node["inputs"]["model"] == "Speed"

        harness.wait_until(
            lambda: (
                set(node_fields()) == {"model", "model.steps", "seed"}
                and not panel.is_projection_active()
            ),
            description="dynamic nested field replacement",
        )
        assert "model.prompt" not in node_fields()
    finally:
        harness.close()


def test_real_shell_cube_mounts_graph_inferred_prompt_editor() -> None:
    """Cube-local topology should mount and edit through the production PromptEditor."""

    harness = RealShellPromptEditorHarness()
    try:
        field = harness.add_inferred_prompt_workflow(initial_text="initial")

        assert harness.rendered_node_card_order(field)[:2] == (
            "encoder",
            "ordinary",
        )

        harness.replace_text_with_keys(field, "updated prompt")

        nodes = field.workflow.cube_state.buffer["nodes"]
        assert isinstance(nodes, dict)
        encoder = nodes["encoder"]
        assert isinstance(encoder, dict)
        assert encoder["inputs"] == {"text": "updated prompt"}
    finally:
        harness.close()


def test_real_shell_sdxl_global_override_updates_direct_api_graph() -> None:
    """A toolbar commit should update direct state and the emitted Comfy API graph."""

    harness = RealShellDirectWorkflowHarness()
    try:
        fixture = _deterministic_sdxl_fixture()
        harness.load_direct_workflow(
            fixture.path,
            node_definitions=fixture.node_definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )

        assert {"sampler_name", "scheduler", "seed"} <= set(
            harness.active_override_keys()
        )

        harness.set_global_override_value("seed", 424242)
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


def test_real_cube_and_direct_comfy_seed_controls_share_one_render_contract() -> None:
    """Production cube seed and Comfy noise_seed surfaces should render identically."""

    harness = RealShellDirectWorkflowHarness()
    try:
        fixture = _deterministic_sdxl_fixture()
        definitions = dict(fixture.node_definitions)
        definitions["KSampler"] = {
            "input": {
                "required": {
                    "seed": ["INT", {"default": 0, "min": 0, "max": 999999}],
                }
            }
        }
        harness.install_cube_seed_control(node_definitions=definitions)
        cube_field = harness.seed_field_probe(harness.cube_workflow_id, "seed")
        cube_toolbar = harness.seed_toolbar_probe(harness.cube_workflow_id)

        harness.load_direct_workflow(
            fixture.path,
            node_definitions=definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )
        direct_field = harness.seed_field_probe(
            harness.direct_workflow_id,
            "noise_seed",
        )
        direct_toolbar = harness.seed_toolbar_probe(harness.direct_workflow_id)

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
