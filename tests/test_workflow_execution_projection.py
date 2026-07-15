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

"""Tests for workflow cube execution projection."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workflow import (
    active_adjacent_alias_pairs,
    active_cube_aliases,
    bypassed_cube_aliases,
    is_cube_bypassed,
)


def _workflow(order: list[str], bypassed: set[str] | None = None) -> SimpleNamespace:
    """Return a simple workflow fixture with configured bypass state."""

    bypassed_aliases = bypassed or set()
    return SimpleNamespace(
        stack_order=order,
        cubes={
            alias: SimpleNamespace(bypassed=alias in bypassed_aliases)
            for alias in order
            if alias != "Missing"
        },
    )


def test_active_cube_aliases_include_all_present_non_bypassed_cubes() -> None:
    """All active cube aliases should project in stack order."""

    workflow = _workflow(["A", "B", "C"])

    assert active_cube_aliases(workflow) == ("A", "B", "C")
    assert bypassed_cube_aliases(workflow) == ()
    assert active_adjacent_alias_pairs(workflow) == (("A", "B"), ("B", "C"))


def test_active_cube_aliases_bridge_over_middle_bypassed_cube() -> None:
    """A bypassed middle cube should be excluded from active adjacency."""

    workflow = _workflow(["A", "B", "C"], {"B"})

    assert active_cube_aliases(workflow) == ("A", "C")
    assert bypassed_cube_aliases(workflow) == ("B",)
    assert active_adjacent_alias_pairs(workflow) == (("A", "C"),)


def test_active_cube_aliases_skip_bypassed_stack_edges() -> None:
    """Bypassed first and last cubes should not create dangling active pairs."""

    workflow = _workflow(["A", "B", "C"], {"A", "C"})

    assert active_cube_aliases(workflow) == ("B",)
    assert bypassed_cube_aliases(workflow) == ("A", "C")
    assert active_adjacent_alias_pairs(workflow) == ()


def test_active_cube_aliases_support_consecutive_bypassed_cubes() -> None:
    """Consecutive bypassed cubes should bridge between surrounding active cubes."""

    workflow = _workflow(["A", "B", "C", "D"], {"B", "C"})

    assert active_cube_aliases(workflow) == ("A", "D")
    assert active_adjacent_alias_pairs(workflow) == (("A", "D"),)


def test_active_cube_aliases_skip_all_bypassed_and_missing_cubes() -> None:
    """All-bypassed and missing stack entries should produce no active aliases."""

    workflow = _workflow(["A", "Missing", "B"], {"A", "B"})

    assert active_cube_aliases(workflow) == ()
    assert bypassed_cube_aliases(workflow) == ("A", "B")
    assert active_adjacent_alias_pairs(workflow) == ()


def test_is_cube_bypassed_treats_absent_or_non_true_values_as_active() -> None:
    """Only an explicit boolean true bypass flag should mark a cube bypassed."""

    assert is_cube_bypassed(SimpleNamespace()) is False
    assert is_cube_bypassed(SimpleNamespace(bypassed="true")) is False
    assert is_cube_bypassed(SimpleNamespace(bypassed=True)) is True
