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

"""Regression tests for partial behavior snapshots with missing definitions."""

from __future__ import annotations

from tests.support.node_behavior import build_behavior_snapshot, cube_state


def test_missing_definition_degrades_only_its_saved_node() -> None:
    """A healthy sibling should retain controls when one definition is absent."""

    cube = cube_state(
        nodes={
            "missing": {
                "class_type": "MissingCustomNode",
                "inputs": {"saved_value": 42},
                "_meta": {"title": "Saved Missing Node"},
            },
            "healthy": {
                "class_type": "HealthyNode",
                "inputs": {"value": 3},
                "_meta": {"title": "Healthy Node"},
            },
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "HealthyNode": {"input": {"required": {"value": ["INT", {"default": 1}]}}}
        },
    )

    degraded = snapshot.degraded_nodes_by_alias["A"]["missing"]
    assert degraded.title == "Saved Missing Node"
    assert degraded.class_type == "MissingCustomNode"
    assert degraded.missing_definition_classes == ("MissingCustomNode",)
    assert snapshot.field_specs_by_alias["A"]["missing"] == {}
    assert tuple(snapshot.field_specs_by_alias["A"]["healthy"]) == ("value",)
    assert set(snapshot.resolved_nodes_by_alias["A"]) == {"missing", "healthy"}
    decision = snapshot.card_decisions_by_alias["A"]["missing"]
    assert decision.visible is True
    assert decision.reason == "missing-live-definition"


def test_persisted_widget_schema_never_impersonates_a_missing_live_definition() -> None:
    """Persisted controls should remain facts but render as one degraded node card."""

    cube = cube_state(
        nodes={
            "missing": {
                "class_type": "MissingCustomNode",
                "inputs": {"amount": 0.75},
                "_meta": {"title": "Saved custom node"},
                "_workflow": {
                    "execution_role": "executable",
                    "editor_definition": {
                        "input": {
                            "required": {
                                "amount": ["FLOAT", {"default": 0.75}],
                            }
                        }
                    },
                },
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={},
    )

    degraded = snapshot.degraded_nodes_by_alias["A"]["missing"]
    assert degraded.title == "Saved custom node"
    assert degraded.missing_definition_classes == ("MissingCustomNode",)
    assert snapshot.field_specs_by_alias["A"]["missing"] == {}


def test_node_search_can_filter_a_degraded_card() -> None:
    """An explicit editor search should still control degraded-card visibility."""

    cube = cube_state(
        nodes={
            "missing": {
                "class_type": "MissingCustomNode",
                "inputs": {},
                "_meta": {"title": "Saved custom node"},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={},
        node_search_text="unrelated",
    )

    decision = snapshot.card_decisions_by_alias["A"]["missing"]
    assert decision.visible is False
    assert decision.reason == "search:node-filter"


def test_wrapper_degrades_when_an_unexposed_body_node_definition_is_missing() -> None:
    """A wrapper must report missing execution dependencies beyond public fields."""

    wrapper_id = "2b1c2ac1-feb6-4240-9e39-5b191ab39f62"
    cube = cube_state(
        nodes={"wrapper": {"class_type": wrapper_id, "inputs": {}}},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Saved wrapper",
                "inputs": [],
                "outputs": [],
                "links": [],
                "nodes": [
                    {
                        "id": 42,
                        "type": "HiddenMissingNode",
                        "inputs": [],
                    }
                ],
            }
        ],
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={},
    )

    degraded = snapshot.degraded_nodes_by_alias["A"]["wrapper"]
    assert degraded.title == "Saved wrapper"
    assert degraded.missing_definition_classes == ("HiddenMissingNode",)
    assert snapshot.field_specs_by_alias["A"]["wrapper"] == {}
