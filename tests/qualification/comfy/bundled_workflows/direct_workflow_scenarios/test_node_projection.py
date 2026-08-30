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

"""Qualify direct-workflow card and dynamic-field projection in the real shell."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
)
from substitute.presentation.editor.panel.node_card.accordion_motion import (
    AccordionContentClip,
    AccordionMotionController,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_scenarios.support import (
    deterministic_sdxl_fixture,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.rendering import (
    rendered_node_cards,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.workflows import (
    direct_section_view,
    load_direct_workflow,
)


def test_real_shell_sdxl_fixture_renders_regular_widgets(tmp_path: Path) -> None:
    """The SDXL projection fixture should render through production widget owners."""

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

        cards = rendered_node_cards(harness)
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


def test_real_shell_accordion_collapse_releases_section_height(tmp_path: Path) -> None:
    """Settled production card collapses must shrink their editor cube section."""

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
        section = direct_section_view(harness)
        controlled_bodies = [
            (body, controller)
            for body in section.findChildren(AccordionContentClip)
            if isinstance(
                controller := getattr(body, "_accordion_motion_controller", None),
                AccordionMotionController,
            )
        ][:2]
        assert len(controlled_bodies) == 2
        expanded_height = section.minimumHeight()

        for _body, controller in controlled_bodies:
            controller.toggle()
        harness.wait_until(
            lambda: all(body.isHidden() for body, _controller in controlled_bodies),
            description="production node-card accordion collapse",
        )

        assert section.minimumHeight() < expanded_height
        assert section.sizeHint().height() == section.minimumHeight()
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
    harness = DirectWorkflowShell(tmp_path)
    try:
        load_direct_workflow(
            harness,
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
