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

"""Contract tests for sampler/scheduler value-link state derivation."""

from __future__ import annotations

from substitute.application.overrides.sampler_scheduler_link_state_service import (
    SamplerSchedulerLinkStateService,
)
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def test_service_builds_sampler_state_from_resolved_field_specs() -> None:
    """Sampler state should use resolved field specs for literals and link targets."""

    first = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "euler"},
            }
        }
    )
    second = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {},
                "sampler_link": {"from_cube": "A", "from_node": "sampler"},
            }
        }
    )
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": first, "B": second},
        stack_order=["A", "B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "heun"], {"default": "euler"}],
                    }
                }
            }
        },
    )

    link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
        behavior_snapshot=behavior_snapshot,
        all_buffers={"A": first.buffer, "B": second.buffer},
        stack_order=["A", "B"],
    )

    state = link_snapshot.sampler_fields[("B", "sampler")]
    assert state.literal_options == ("euler", "heun")
    assert state.options_resolved is True
    assert [target.label for target in state.link_targets] == ["🔗 A sampler"]
    assert state.active_link is not None
    assert state.active_link.from_cube == "A"
    assert state.active_link.from_node == "sampler"


def test_service_builds_scheduler_state_from_resolved_field_specs() -> None:
    """Scheduler state should mirror sampler handling through resolved field specs."""

    first = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"scheduler": "normal"},
            }
        }
    )
    second = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {},
                "scheduler_link": {"from_cube": "A", "from_node": "sampler"},
            }
        }
    )
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": first, "B": second},
        stack_order=["A", "B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "scheduler": [["normal", "karras"], {"default": "normal"}],
                    }
                }
            }
        },
    )

    link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
        behavior_snapshot=behavior_snapshot,
        all_buffers={"A": first.buffer, "B": second.buffer},
        stack_order=["A", "B"],
    )

    state = link_snapshot.scheduler_fields[("B", "sampler")]
    assert state.literal_options == ("normal", "karras")
    assert state.options_resolved is True
    assert [target.label for target in state.link_targets] == ["🔗 A sampler"]
    assert state.active_link is not None
    assert state.active_link.from_cube == "A"
    assert state.active_link.from_node == "sampler"


def test_service_uses_resolved_capability_when_raw_upstream_literal_is_absent() -> None:
    """Linked upstream nodes without literal input keys should remain valid targets."""

    first = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {},
                "sampler_link": {"from_cube": "Root", "from_node": "sampler"},
            }
        }
    )
    second = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "heun"},
            }
        }
    )
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": first, "B": second},
        stack_order=["A", "B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "heun"], {"default": "euler"}],
                    }
                }
            }
        },
    )

    link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
        behavior_snapshot=behavior_snapshot,
        all_buffers={"A": first.buffer, "B": second.buffer},
        stack_order=["A", "B"],
    )

    state = link_snapshot.sampler_fields[("B", "sampler")]
    assert [target.from_cube for target in state.link_targets] == ["A"]
    assert [target.from_node for target in state.link_targets] == ["sampler"]


def test_service_excludes_link_targets_with_different_choice_options() -> None:
    """Sampler links require exact option equality across source and target fields."""

    first = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "euler"},
            }
        }
    )
    second = cube_state(
        nodes={
            "sampler": {
                "class_type": "CustomSampler",
                "inputs": {"sampler_name": "euler"},
            }
        }
    )
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": first, "B": second},
        stack_order=["A", "B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "heun"], {"default": "euler"}],
                    }
                }
            },
            "CustomSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "ddim"], {"default": "euler"}],
                    }
                }
            },
        },
    )

    link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
        behavior_snapshot=behavior_snapshot,
        all_buffers={"A": first.buffer, "B": second.buffer},
        stack_order=["A", "B"],
    )

    assert link_snapshot.sampler_fields[("B", "sampler")].link_targets == ()


def test_service_marks_unresolved_options_without_fallback_literals() -> None:
    """Missing authoritative options should be explicit and never guessed."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "stale"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": ["LIST", {"dynamic": True}],
                    }
                }
            }
        },
    )
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    )

    link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
        behavior_snapshot=behavior_snapshot,
        all_buffers={"A": cube.buffer},
        stack_order=["A"],
    )

    state = link_snapshot.sampler_fields[("A", "sampler")]
    assert state.literal_options == ()
    assert state.options_resolved is False
    assert state.link_targets == ()
