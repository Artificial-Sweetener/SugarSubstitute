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

"""Verify linked-field and prompt visibility decisions."""

from __future__ import annotations

from substitute.domain.links import NodeLinkEndpoint, NodeLinkEndpointIndex
from substitute.domain.node_behavior import (
    CardBehavior,
    CardDecision,
    EnabledSwitchPolicy,
    EditorBehaviorContext,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    PackageBehaviorPatch,
    PromptFieldBehavior,
    PromptRole,
    ResolvedNodeBehavior,
    RevealMode,
    VisibilityRule,
    compute_editor_behavior,
)
from tests.domain.node_behavior.engine.support import cube


def test_compute_editor_behavior_merges_hidden_fields_and_reveal_entries() -> None:
    """Engine should compute card decisions, hidden keys, and reveal entries together."""

    ctx = EditorBehaviorContext(
        stack_order=("A", "B"),
        cubes={
            "A": cube(
                {
                    "vae_primary": {
                        "class_type": "VAELoader",
                        "inputs": {},
                        "enabled": False,
                        "mode": 4,
                    },
                    "prompt": {
                        "class_type": "PromptNode",
                        "inputs": {},
                        "node_link": {"from_cube": "B", "from_node": "prompt"},
                    },
                }
            ),
            "B": cube(
                {
                    "vae": {
                        "class_type": "VAELoader",
                        "inputs": {},
                        "enabled": False,
                        "mode": 4,
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "vae_primary": ResolvedNodeBehavior(
                    node_name="vae_primary",
                    class_type="VAELoader",
                    card=CardBehavior(
                        visibility_rule=VisibilityRule.ONLY_FIRST_OF_CLASS,
                        reveal_mode=RevealMode.MENU,
                    ),
                    fields={},
                ),
                "prompt": ResolvedNodeBehavior(
                    node_name="prompt",
                    class_type="PromptNode",
                    card=CardBehavior(),
                    fields={
                        "prompt_template": FieldBehavior(
                            "prompt_template",
                            prompt=PromptFieldBehavior(role=PromptRole.POSITIVE),
                        ),
                        "seed": FieldBehavior(
                            "seed",
                            override_behavior=OverrideBehavior(
                                override_key="seed",
                                pin_policy=OverridePinPolicy.OPTIONAL,
                            ),
                        ),
                    },
                ),
            },
            "B": {
                "vae": ResolvedNodeBehavior(
                    node_name="vae",
                    class_type="VAELoader",
                    card=CardBehavior(
                        visibility_rule=VisibilityRule.ONLY_FIRST_OF_CLASS,
                        reveal_mode=RevealMode.MENU,
                    ),
                    fields={},
                )
            },
        },
        workflow_overrides={"seed": {"value": 1}},
        search_hidden_keys=frozenset({"cfg"}),
        node_link_endpoint_index=NodeLinkEndpointIndex.from_endpoints(
            (
                NodeLinkEndpoint(
                    cube_alias="A",
                    node_name="prompt",
                    class_type="PromptNode",
                    family="prompt:positive",
                    editable_value_keys=("prompt_template",),
                ),
            )
        ),
        node_search_text=None,
    )

    card_decisions, hidden_keys, reveal_entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch(), "B": PackageBehaviorPatch()},
    )

    assert isinstance(card_decisions["B"]["vae"], CardDecision)
    assert ("A", "prompt", "seed") in hidden_keys["A"]
    assert "cfg" in hidden_keys["B"]
    assert ("A", "prompt", "prompt_template") in hidden_keys["A"]
    assert reveal_entries["B"][0].node_name == "vae"


def test_compute_editor_behavior_only_hides_role_endpoint_prompt_links() -> None:
    """Incidental node_link metadata should not hide non-endpoint fields."""

    ctx = EditorBehaviorContext(
        stack_order=("A",),
        cubes={
            "A": cube(
                {
                    "prompt": {
                        "class_type": "PromptNode",
                        "inputs": {"text": "hello"},
                        "node_link": {"from_cube": "B", "from_node": "prompt"},
                    },
                    "other": {
                        "class_type": "OtherNode",
                        "inputs": {"prompt_template": "visible"},
                        "node_link": {"from_cube": "B", "from_node": "other"},
                    },
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "prompt": ResolvedNodeBehavior(
                    node_name="prompt",
                    class_type="PromptNode",
                    card=CardBehavior(),
                    fields={
                        "text": FieldBehavior(
                            "text",
                            prompt=PromptFieldBehavior(role=PromptRole.POSITIVE),
                        ),
                    },
                ),
                "other": ResolvedNodeBehavior(
                    node_name="other",
                    class_type="OtherNode",
                    card=CardBehavior(),
                    fields={"prompt_template": FieldBehavior("prompt_template")},
                ),
            },
        },
        workflow_overrides={},
        search_hidden_keys=frozenset(),
        node_link_endpoint_index=NodeLinkEndpointIndex.from_endpoints(
            (
                NodeLinkEndpoint(
                    cube_alias="A",
                    node_name="prompt",
                    class_type="PromptNode",
                    family="prompt:positive",
                    editable_value_keys=("text",),
                ),
            )
        ),
    )

    _decisions, hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch()},
    )

    assert ("A", "prompt", "text") in hidden_keys["A"]
    assert ("A", "other", "prompt_template") not in hidden_keys["A"]


def test_compute_editor_behavior_hides_linked_vectorscope_value_fields() -> None:
    """Active VectorscopeCC node links should hide inherited local value controls."""

    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (
            NodeLinkEndpoint(
                cube_alias="A",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
                editable_value_keys=("brightness", "contrast"),
            ),
            NodeLinkEndpoint(
                cube_alias="B",
                node_name="vectorscopecc",
                class_type="VectorscopeCC",
                family="vectorscopecc",
                editable_value_keys=("brightness", "contrast"),
            ),
        )
    )
    ctx = EditorBehaviorContext(
        stack_order=("A", "B"),
        cubes={
            "A": cube(
                {
                    "vectorscopecc": {
                        "class_type": "VectorscopeCC",
                        "inputs": {"brightness": 0.25, "contrast": 0.0},
                        "enabled": False,
                    }
                }
            ),
            "B": cube(
                {
                    "vectorscopecc": {
                        "class_type": "VectorscopeCC",
                        "inputs": {"brightness": 0.75, "contrast": 0.5},
                        "enabled": True,
                        "node_link": {
                            "from_cube": "A",
                            "from_node": "vectorscopecc",
                        },
                    }
                }
            ),
        },
        behaviors_by_alias={
            "A": {
                "vectorscopecc": ResolvedNodeBehavior(
                    node_name="vectorscopecc",
                    class_type="VectorscopeCC",
                    card=CardBehavior(enabled_switch_policy=EnabledSwitchPolicy.ALWAYS),
                    fields={
                        "brightness": FieldBehavior("brightness"),
                        "contrast": FieldBehavior("contrast"),
                    },
                )
            },
            "B": {
                "vectorscopecc": ResolvedNodeBehavior(
                    node_name="vectorscopecc",
                    class_type="VectorscopeCC",
                    card=CardBehavior(enabled_switch_policy=EnabledSwitchPolicy.ALWAYS),
                    fields={
                        "brightness": FieldBehavior("brightness"),
                        "contrast": FieldBehavior("contrast"),
                    },
                )
            },
        },
        workflow_overrides={},
        search_hidden_keys=frozenset(),
        node_link_endpoint_index=endpoint_index,
    )

    decisions, hidden_keys, _entries = compute_editor_behavior(
        ctx,
        declarative_by_alias={"A": PackageBehaviorPatch(), "B": PackageBehaviorPatch()},
    )

    assert decisions["B"]["vectorscopecc"].enabled is False
    assert decisions["B"]["vectorscopecc"].show_enabled_switch is True
    assert decisions["B"]["vectorscopecc"].node_link_active is True
    assert ("B", "vectorscopecc", "brightness") in hidden_keys["B"]
    assert ("B", "vectorscopecc", "contrast") in hidden_keys["B"]
    assert ("A", "vectorscopecc", "brightness") not in hidden_keys["A"]
