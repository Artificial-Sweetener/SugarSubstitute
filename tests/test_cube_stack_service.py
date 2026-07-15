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

"""Contract tests for cube stack alias orchestration."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.cubes import CubeStackService


def test_apply_cube_rename_resolves_collisions_and_updates_workflow_state() -> None:
    """Rename application should return the resolved alias and keep workflow state aligned."""
    old_cube_state = SimpleNamespace(alias="Old")
    taken_cube_state = SimpleNamespace(alias="Taken")
    service = CubeStackService()
    workflow = SimpleNamespace(
        cubes={"Old": old_cube_state, "Taken": taken_cube_state},
        stack_order=["Old", "Taken"],
    )

    resolution = service.apply_cube_rename(workflow, "Old", "Taken")

    assert resolution.old_alias == "Old"
    assert resolution.requested_alias == "Taken"
    assert resolution.resolved_alias == "Taken 2"
    assert workflow.cubes["Taken 2"] is old_cube_state
    assert old_cube_state.alias == "Taken 2"
    assert workflow.stack_order == ["Taken 2", "Taken"]


def test_resolve_cube_rename_excludes_current_alias_from_collision_check() -> None:
    """Rename planning should allow keeping a cube's current visible alias."""
    service = CubeStackService()
    workflow = SimpleNamespace(
        cubes={
            "Shared": SimpleNamespace(cube_id="cube_a"),
            "Shared 2": SimpleNamespace(cube_id="cube_b"),
        },
        stack_order=["Shared", "Shared 2"],
    )

    resolution = service.resolve_cube_rename(workflow, "Shared 2", "Shared 2")

    assert resolution.resolved_alias == "Shared 2"


def test_apply_cube_addition_targets_only_passed_workflow() -> None:
    """Cube addition should mutate only the explicitly supplied workflow."""

    service = CubeStackService()
    workflow_a = SimpleNamespace(cubes={}, stack_order=[])
    workflow_b = SimpleNamespace(cubes={}, stack_order=[])
    cube_state = SimpleNamespace(cube_id="cube_a", alias="Alias")

    service.apply_cube_addition(workflow_a, "cube_a", "Alias", cube_state)

    assert workflow_a.cubes == {"Alias": cube_state}
    assert workflow_a.stack_order == ["Alias"]
    assert workflow_b.cubes == {}
    assert workflow_b.stack_order == []


def test_set_cube_bypassed_updates_only_target_cube() -> None:
    """Bypass mutation should not alter stack order or neighboring cubes."""

    service = CubeStackService()
    target = SimpleNamespace(cube_id="cube_a", alias="A", bypassed=False)
    neighbor = SimpleNamespace(cube_id="cube_b", alias="B", bypassed=False)
    workflow = SimpleNamespace(
        cubes={"A": target, "B": neighbor},
        stack_order=["A", "B"],
    )

    changed = service.set_cube_bypassed(workflow, "A", True)

    assert changed is True
    assert target.bypassed is True
    assert neighbor.bypassed is False
    assert workflow.stack_order == ["A", "B"]


def test_set_cube_bypassed_noops_when_value_is_unchanged() -> None:
    """Setting the current bypass value should report no mutation."""

    service = CubeStackService()
    cube_state = SimpleNamespace(cube_id="cube_a", alias="A", bypassed=True)
    workflow = SimpleNamespace(cubes={"A": cube_state}, stack_order=["A"])

    changed = service.set_cube_bypassed(workflow, "A", True)

    assert changed is False
    assert cube_state.bypassed is True


def test_toggle_cube_bypassed_returns_new_value() -> None:
    """Toggle should flip the target cube and return the resulting state."""

    service = CubeStackService()
    cube_state = SimpleNamespace(cube_id="cube_a", alias="A", bypassed=False)
    workflow = SimpleNamespace(cubes={"A": cube_state}, stack_order=["A"])

    first = service.toggle_cube_bypassed(workflow, "A")
    second = service.toggle_cube_bypassed(workflow, "A")

    assert first is True
    assert second is False
    assert cube_state.bypassed is False


def test_cube_bypass_mutation_ignores_missing_alias() -> None:
    """Missing aliases should not create cube state or disturb ordering."""

    service = CubeStackService()
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    changed = service.set_cube_bypassed(workflow, "Missing", True)
    toggled = service.toggle_cube_bypassed(workflow, "Missing")

    assert changed is False
    assert toggled is False
    assert workflow.cubes == {}
    assert workflow.stack_order == []
