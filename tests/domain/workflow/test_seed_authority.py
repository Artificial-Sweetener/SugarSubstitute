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

"""Test authoritative effective workflow seed selection."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workflow import (
    WorkflowSeedAuthority,
    WorkflowSeedSource,
)


def _cube(*, controls: list[dict[str, object]], nodes: dict[str, object]) -> object:
    """Build one lightweight cube state for seed authority tests."""

    return SimpleNamespace(
        original_cube={"surface": {"controls": controls}},
        buffer={"nodes": nodes},
    )


def _seed_cube(control_id: str, symbol: str, seed: object) -> object:
    """Build one cube exposing a single authored seed control."""

    return _cube(
        controls=[
            {
                "control_id": control_id,
                "symbol": symbol,
                "input_name": "seed",
            }
        ],
        nodes={symbol: {"inputs": {"seed": seed}}},
    )


def test_global_seed_override_wins_over_every_cube_seed() -> None:
    """The valid global override should own effective seed selection."""

    workflow = SimpleNamespace(
        global_overrides={"seed": {"value": 987, "mode": "global"}},
        stack_order=["First", "Prompt"],
        cubes={
            "First": _seed_cube("first.seed", "first", 111),
            "Prompt": _seed_cube("prompt.seed", "prompt", 222),
        },
    )

    selection = WorkflowSeedAuthority().select(workflow)

    assert selection.seed == 987
    assert selection.source == WorkflowSeedSource.GLOBAL_OVERRIDE
    assert selection.override_key == "seed"
    assert selection.cube_alias is None
    assert selection.control_id is None


def test_first_workflow_seed_is_used_without_global_override() -> None:
    """Workflow stack order should determine the fallback seed."""

    workflow = SimpleNamespace(
        global_overrides={},
        stack_order=["First", "Prompt"],
        cubes={
            "Prompt": _seed_cube("prompt.seed", "prompt", 123),
            "First": _seed_cube("first.seed", "first", 456),
        },
    )

    selection = WorkflowSeedAuthority().select(workflow)

    assert selection.seed == 456
    assert selection.source == WorkflowSeedSource.CUBE_CONTROL
    assert selection.cube_alias == "First"
    assert selection.control_id == "first.seed"


def test_invalid_global_seed_falls_back_to_first_workflow_seed() -> None:
    """Malformed global state should not hide a valid workflow seed."""

    workflow = SimpleNamespace(
        global_overrides={"seed": {"value": True, "mode": "global"}},
        stack_order=["First"],
        cubes={"First": _seed_cube("first.seed", "first", 321)},
    )

    selection = WorkflowSeedAuthority().select(workflow)

    assert selection.seed == 321
    assert selection.source == WorkflowSeedSource.CUBE_CONTROL
    assert selection.cube_alias == "First"


def test_invalid_cube_seed_is_ignored() -> None:
    """Boolean and non-integer cube values should not become seeds."""

    workflow = SimpleNamespace(
        global_overrides={},
        stack_order=["Prompt"],
        cubes={"Prompt": _seed_cube("bad.seed", "bad", True)},
    )

    selection = WorkflowSeedAuthority().select(workflow)

    assert selection.seed is None
    assert selection.source is None


def test_active_global_seed_override_identity_uses_stored_key() -> None:
    """Override randomization should address the workflow's stored seed key."""

    workflow = SimpleNamespace(
        global_overrides={"seed": {"value": 123}},
        stack_order=[],
        cubes={},
    )

    assert WorkflowSeedAuthority.active_global_override_key(workflow) == "seed"
