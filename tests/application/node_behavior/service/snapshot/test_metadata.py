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

"""Behavior snapshot field-metadata contracts."""

from __future__ import annotations


import pytest

from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)


def test_build_snapshot_exposes_all_editor_behavior_buckets() -> None:
    """Service snapshots should include resolved nodes, card decisions, hidden keys, and reveal entries."""

    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": 7,
                        "sampler_name": "euler",
                        "scheduler": "karras",
                    },
                }
            },
            definitions={
                "KSampler": {
                    "input": {
                        "required": {
                            "seed": ["INT", {"min": 0, "max": 999999, "step": 1}],
                            "sampler_name": [["euler", "heun"], {}],
                            "scheduler": [["karras", "normal"], {}],
                        }
                    },
                }
            },
        ),
        "B": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "model-b"},
                }
            }
        ),
    }

    snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT", {"min": 0, "max": 999999, "step": 1}],
                        "sampler_name": [["euler", "heun"], {}],
                        "scheduler": [["karras", "normal"], {}],
                    }
                },
            }
        },
        workflow_overrides={"seed": {"value": 1}},
    )

    assert "A" in snapshot.resolved_nodes_by_alias
    assert "A" in snapshot.field_specs_by_alias
    assert "A" in snapshot.card_decisions_by_alias
    assert "A" in snapshot.hidden_field_keys_by_alias
    assert "B" in snapshot.reveal_entries_by_alias
    assert "ksampler" in snapshot.resolved_nodes_by_alias["A"]
    assert snapshot.field_specs_by_alias["A"]["ksampler"]["seed"].field_type == "INT"
    assert ("A", "ksampler", "seed") in snapshot.hidden_field_keys_by_alias["A"]


def test_build_snapshot_exposes_comfy_tooltip_metadata() -> None:
    """Comfy node descriptions and field tooltips should enter render contracts."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"steps": 20},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "description": "Samples an image from latent noise.",
                "input": {
                    "required": {
                        "steps": [
                            "INT",
                            {"tooltip": "Number of denoise steps."},
                        ]
                    }
                },
            }
        },
    )

    resolved = snapshot.resolved_nodes_by_alias["A"]["sampler"]
    field_spec = snapshot.field_specs_by_alias["A"]["sampler"]["steps"]
    assert resolved.card.tooltip == "Samples an image from latent noise."
    assert field_spec.meta_info["tooltip"] == "Number of denoise steps."


def test_build_snapshot_preserves_live_advanced_metadata() -> None:
    """Live Comfy advanced metadata should survive the behavior boundary unchanged."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"control_after_generate": "randomize"},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "optional": {
                        "control_after_generate": [
                            ["fixed", "increment", "decrement", "randomize"],
                            {"advanced": True},
                        ]
                    }
                }
            }
        },
    )

    field_spec = snapshot.field_specs_by_alias["A"]["sampler"]["control_after_generate"]
    assert field_spec.meta_info["advanced"] is True
    assert field_spec.is_advanced is True


@pytest.mark.parametrize("description", ["", "   ", {"text": "not renderable"}])
def test_build_snapshot_ignores_blank_or_invalid_comfy_node_tooltips(
    description: object,
) -> None:
    """Blank and non-string node descriptions should not become card tooltips."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"steps": 20},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "description": description,
                "input": {"required": {"steps": ["INT", {}]}},
            }
        },
    )

    assert snapshot.resolved_nodes_by_alias["A"]["sampler"].card.tooltip is None


def test_build_snapshot_ignores_cube_authored_tooltips_when_live_missing() -> None:
    """Cube-authored node and field tooltips should not render without live metadata."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"steps": 20},
            }
        },
        definitions={
            "KSampler": {
                "description": "Cube-authored node tooltip.",
                "input": {
                    "required": {
                        "steps": ["INT", {"tooltip": "Cube-authored field tooltip."}]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    resolved = snapshot.resolved_nodes_by_alias["A"]["sampler"]
    field_spec = snapshot.field_specs_by_alias["A"]["sampler"]["steps"]
    assert resolved.card.tooltip is None
    assert "tooltip" not in field_spec.meta_info


def test_build_snapshot_orders_fields_from_definition_before_persisted_extras() -> None:
    """Sorted persisted inputs should not override cube definition field order."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "OrderedSampler",
                "inputs": {
                    "height": 768,
                    "prompt": "quality",
                    "seed": 123,
                    "unknown_extra": "kept",
                    "width": 512,
                },
            }
        },
        definitions={
            "OrderedSampler": {
                "input": {
                    "required": {
                        "prompt": ["STRING", {}],
                        "width": ["INT", {}],
                        "height": ["INT", {}],
                    },
                    "optional": {
                        "seed": ["INT", {}],
                    },
                }
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "OrderedSampler": {
                "input": {
                    "required": {
                        "prompt": ["STRING", {}],
                        "width": ["INT", {}],
                        "height": ["INT", {}],
                    },
                    "optional": {
                        "seed": ["INT", {}],
                    },
                }
            }
        },
    )

    assert list(snapshot.field_specs_by_alias["A"]["sampler"]) == [
        "prompt",
        "width",
        "height",
        "seed",
        "unknown_extra",
    ]
