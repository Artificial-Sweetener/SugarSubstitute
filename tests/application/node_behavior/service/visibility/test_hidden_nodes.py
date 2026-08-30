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

"""Hidden-node behavior contracts."""

from __future__ import annotations

from pathlib import Path


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    ActivationDefault,
    CardMode,
    CollapseMode,
    FieldPresentation,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from tests.support.node_behavior import (
    DummyNodeDefinitionGateway,
    build_behavior_snapshot,
    cube_state,
)


def test_simple_syrup_schedule_node_is_hidden_infrastructure() -> None:
    """SimpleSyrup schedule nodes should not expose editor card UI."""

    node_class = "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
    cube = cube_state(
        nodes={
            "schedule": {
                "class_type": node_class,
                "inputs": {
                    "positive_prompt": "quality",
                    "negative_prompt": "blurry",
                    "encode_style": "standard",
                },
            },
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            node_class: {
                "input": {
                    "required": {
                        "positive_prompt": ["STRING", {"multiline": True}],
                        "negative_prompt": ["STRING", {"multiline": True}],
                        "encode_style": ["STRING", {}],
                    }
                }
            }
        },
    )

    fields = snapshot.field_specs_by_alias["A"]["schedule"]
    positive_behavior = fields["positive_prompt"].field_behavior
    negative_behavior = fields["negative_prompt"].field_behavior
    style_behavior = fields["encode_style"].field_behavior

    card = snapshot.resolved_nodes_by_alias["A"]["schedule"].card
    decision = snapshot.card_decisions_by_alias["A"]["schedule"]
    assert card.card_mode is CardMode.STANDARD
    assert card.collapse_mode is CollapseMode.AUTO
    assert card.activation_default is ActivationDefault.ENABLED
    assert card.hidden is True
    assert card.icon_name is None
    assert decision.visible is False
    assert decision.enabled is True
    assert decision.revealable is False
    assert decision.show_enabled_switch is False
    assert positive_behavior.presentation is FieldPresentation.STANDARD
    assert positive_behavior.prompt is None
    assert negative_behavior.presentation is FieldPresentation.STANDARD
    assert negative_behavior.prompt is None
    assert style_behavior.presentation is FieldPresentation.STANDARD


def test_workflow_local_definition_does_not_override_existing_hidden_policy() -> None:
    """Renderable direct-workflow widgets must not force hidden nodes visible."""

    node_class = "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
    document = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "schedule": {
                    "class_type": node_class,
                    "inputs": {"positive_prompt": "quality"},
                    "_workflow": {
                        "execution_role": "executable",
                        "editor_definition": {
                            "input": {
                                "required": {
                                    "positive_prompt": [
                                        "STRING",
                                        {"multiline": True},
                                    ]
                                }
                            }
                        },
                    },
                }
            }
        },
    )
    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())

    snapshot = service.build_snapshot(
        cube_states={"direct": document},
        stack_order=["direct"],
    )

    behavior = snapshot.resolved_nodes_by_alias["direct"]["schedule"]
    decision = snapshot.card_decisions_by_alias["direct"]["schedule"]
    assert "positive_prompt" in snapshot.field_specs_by_alias["direct"]["schedule"]
    assert behavior.card.hidden is True
    assert decision.visible is False
    assert decision.revealable is False


def test_direct_workflow_terminal_image_output_is_hard_hidden() -> None:
    """Direct image sinks should disappear without becoming reveal-menu entries."""

    document = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "source": {
                    "class_type": "ImageSource",
                    "inputs": {},
                },
                "sink": {
                    "class_type": "UnfamiliarImageSink",
                    "inputs": {"pictures": ["source", 0]},
                },
            }
        },
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "ImageSource": {"input": {"required": {}}, "output": ["IMAGE"]},
                "UnfamiliarImageSink": {
                    "input": {"required": {"pictures": ["IMAGE", {}]}},
                    "output_node": True,
                },
            }
        )
    )

    snapshot = service.build_snapshot(
        cube_states={"direct": document},
        stack_order=["direct"],
    )

    behavior = snapshot.resolved_nodes_by_alias["direct"]["sink"]
    decision = snapshot.card_decisions_by_alias["direct"]["sink"]
    assert behavior.card.hidden is True
    assert decision.visible is False
    assert decision.revealable is False
    assert decision.show_enabled_switch is False
    assert not any(
        entry.node_name == "sink"
        for entry in snapshot.reveal_entries_by_alias["direct"]
    )


def test_cube_terminal_image_output_keeps_existing_behavior() -> None:
    """Output takeover visibility must remain scoped to direct workflows."""

    cube = cube_state(
        nodes={
            "source": {"class_type": "ImageSource", "inputs": {}},
            "sink": {
                "class_type": "UnfamiliarImageSink",
                "inputs": {"pictures": ["source", 0]},
            },
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "ImageSource": {"input": {"required": {}}, "output": ["IMAGE"]},
            "UnfamiliarImageSink": {
                "input": {"required": {"pictures": ["IMAGE", {}]}},
                "output_node": True,
            },
        },
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["sink"]
    decision = snapshot.card_decisions_by_alias["A"]["sink"]
    assert behavior.card.hidden is False
    assert decision.visible is True
