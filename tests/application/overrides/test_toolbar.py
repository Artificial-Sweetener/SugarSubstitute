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

"""Verify deterministic behavior-driven toolbar snapshots."""

from __future__ import annotations


from substitute.application.node_behavior import OverridePinPolicy
from substitute.application.overrides import PinnedOverrideService
from tests.application.overrides.support import _field_spec, _snapshot
from tests.support.node_behavior import build_behavior_snapshot, cube_state


def test_build_toolbar_snapshot_orders_candidates_deterministically() -> None:
    """Candidates should group by override key and sort by toolbar order then label."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=20,
                    ),
                    "scheduler": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="scheduler",
                        value="karras",
                        override_key="scheduler",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=30,
                    ),
                }
            },
            "B": {
                "seed_node": {
                    "seed": _field_spec(
                        cube_alias="B",
                        node_name="seed_node",
                        class_type="SeedNode",
                        field_key="seed",
                        value=123,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    ),
                    "cfg": _field_spec(
                        cube_alias="B",
                        node_name="seed_node",
                        class_type="SeedNode",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=40,
                        toolbar_label="Guidance",
                    ),
                }
            },
        }
    )
    service = PinnedOverrideService()

    toolbar_snapshot = service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A", "B"],
        overrides={"sampler_name": {"value": "euler", "mode": "global"}},
    )

    assert [candidate.override_key for candidate in toolbar_snapshot.candidates] == [
        "seed",
        "sampler_name",
        "scheduler",
        "cfg",
    ]
    assert [candidate.label for candidate in toolbar_snapshot.candidates] == [
        "seed",
        "sampler_name",
        "scheduler",
        "Guidance",
    ]
    assert [control.override_key for control in toolbar_snapshot.active_controls] == [
        "sampler_name"
    ]


def test_build_toolbar_snapshot_skips_choice_candidates_without_options() -> None:
    """Toolbar choices should not treat unresolved fallback values as inventories."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                        field_type="LIST",
                        field_info=["LIST", {"dynamic": True}],
                    ),
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=123,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=20,
                    ),
                }
            }
        }
    )

    toolbar_snapshot = PinnedOverrideService().build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides={},
    )

    assert [candidate.override_key for candidate in toolbar_snapshot.candidates] == [
        "seed"
    ]


def test_toolbar_snapshot_uses_node_behavior_defaults_for_basic_ksampler() -> None:
    """KSampler behavior should expose optional candidates without default pinning them."""

    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": 123,
                        "sampler_name": "euler",
                        "scheduler": "karras",
                        "steps": 20,
                        "cfg": 7.0,
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
                            "steps": ["INT", {"min": 1, "max": 100, "step": 1}],
                            "cfg": ["FLOAT", {"min": 0.0, "max": 30.0, "step": 0.1}],
                        }
                    }
                }
            },
        )
    }
    behavior_snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=behavior_snapshot,
        stack_order=["A"],
    )
    toolbar_snapshot = service.build_toolbar_snapshot(
        behavior_snapshot=behavior_snapshot,
        stack_order=["A"],
        overrides=overrides,
    )

    assert changed is True
    assert overrides == {
        "seed": {"value": 123, "mode": "global"},
        "sampler_name": {"value": "euler", "mode": "global"},
        "scheduler": {"value": "karras", "mode": "global"},
    }
    assert [candidate.override_key for candidate in toolbar_snapshot.candidates] == [
        "sampler_name",
        "scheduler",
        "steps",
        "cfg",
        "seed",
    ]
    assert [candidate.label for candidate in toolbar_snapshot.candidates] == [
        "Sampler",
        "scheduler",
        "steps",
        "CFG",
        "seed",
    ]
    assert {
        candidate.override_key: candidate.pin_policy
        for candidate in toolbar_snapshot.candidates
    } == {
        "seed": OverridePinPolicy.DEFAULT_PINNED,
        "sampler_name": OverridePinPolicy.DEFAULT_PINNED,
        "scheduler": OverridePinPolicy.DEFAULT_PINNED,
        "steps": OverridePinPolicy.OPTIONAL,
        "cfg": OverridePinPolicy.OPTIONAL,
    }
    assert [control.override_key for control in toolbar_snapshot.active_controls] == [
        "sampler_name",
        "scheduler",
        "seed",
    ]


def test_toolbar_snapshot_default_pins_prompt_encode_style() -> None:
    """Prompt encode style should default-pin from its class-scoped behavior."""

    definitions = {
        "SimpleSyrup.PromptEncodeStyle": {
            "input": {
                "required": {
                    "encode_style": [
                        [
                            "A1111",
                            "Comfy",
                            "Comfy++",
                            "Compel",
                            "Down Weight",
                            "Perp",
                        ],
                        {"default": "A1111"},
                    ]
                }
            }
        }
    }
    cubes = {
        "A": cube_state(
            nodes={
                "prompt_encode_style": {
                    "class_type": "SimpleSyrup.PromptEncodeStyle",
                    "inputs": {},
                }
            },
            definitions=definitions,
        )
    }
    behavior_snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=behavior_snapshot,
        stack_order=["A"],
    )
    toolbar_snapshot = service.build_toolbar_snapshot(
        behavior_snapshot=behavior_snapshot,
        stack_order=["A"],
        overrides=overrides,
    )

    assert changed is True
    assert overrides == {"encode_style": {"value": "A1111", "mode": "global"}}
    candidate_by_key = {
        candidate.override_key: candidate for candidate in toolbar_snapshot.candidates
    }
    assert candidate_by_key["encode_style"].pin_policy == (
        OverridePinPolicy.DEFAULT_PINNED
    )
    assert candidate_by_key["encode_style"].label == "Encode Style"
    assert [control.override_key for control in toolbar_snapshot.active_controls] == [
        "encode_style"
    ]


def test_toolbar_snapshot_uses_preferred_global_override_order() -> None:
    """Built-in defaults should order encode style before sampler and seed last."""

    definitions = {
        "SimpleSyrup.PromptEncodeStyle": {
            "input": {
                "required": {
                    "encode_style": [
                        ["A1111", "Comfy"],
                        {"default": "A1111"},
                    ]
                }
            }
        },
        "KSampler": {
            "input": {
                "required": {
                    "seed": ["INT", {"min": 0, "max": 999999, "step": 1}],
                    "sampler_name": [["euler", "heun"], {}],
                    "scheduler": [["karras", "normal"], {}],
                    "steps": ["INT", {"min": 1, "max": 100, "step": 1}],
                    "cfg": ["FLOAT", {"min": 0.0, "max": 30.0, "step": 0.1}],
                }
            }
        },
    }
    cubes = {
        "A": cube_state(
            nodes={
                "prompt_encode_style": {
                    "class_type": "SimpleSyrup.PromptEncodeStyle",
                    "inputs": {},
                },
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": 123,
                        "sampler_name": "euler",
                        "scheduler": "karras",
                        "steps": 20,
                        "cfg": 7.0,
                    },
                },
            },
            definitions=definitions,
        )
    }
    behavior_snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=behavior_snapshot,
        stack_order=["A"],
    )
    toolbar_snapshot = service.build_toolbar_snapshot(
        behavior_snapshot=behavior_snapshot,
        stack_order=["A"],
        overrides=overrides,
    )

    assert [candidate.label for candidate in toolbar_snapshot.candidates] == [
        "Encode Style",
        "Sampler",
        "scheduler",
        "steps",
        "CFG",
        "seed",
    ]
    assert [control.override_key for control in toolbar_snapshot.active_controls] == [
        "encode_style",
        "sampler_name",
        "scheduler",
        "seed",
    ]
