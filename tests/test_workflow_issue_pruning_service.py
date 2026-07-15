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

"""Tests for generation workflow pruning around cube runtime issues."""

from __future__ import annotations

from typing import cast

from substitute.application.generation import WorkflowIssuePruningService
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.domain.workflow import CubeState, WorkflowState


def test_pruned_for_generation_removes_errored_cubes_without_mutating_source() -> None:
    """Generation pruning should remove errored cubes from a copied workflow only."""

    workflow = WorkflowState(
        cubes={
            "Good": CubeState(
                cube_id="good",
                version="1",
                alias="Good",
                original_cube={},
                buffer={"nodes": {"good": {"class_type": "GoodNode"}}},
            ),
            "Bad": CubeState(
                cube_id="bad",
                version="1",
                alias="Bad",
                original_cube={},
                buffer={"nodes": {"bad": {"class_type": "BadNode"}}},
            ),
        },
        stack_order=["Good", "Bad"],
    )

    pruned = WorkflowIssuePruningService().pruned_for_generation(
        workflow=workflow,
        errored_aliases={"Bad"},
    )

    assert pruned is not workflow
    assert pruned.stack_order == ["Good"]
    assert set(pruned.cubes) == {"Good"}
    assert workflow.stack_order == ["Good", "Bad"]
    assert set(workflow.cubes) == {"Good", "Bad"}


def test_pruned_activation_overrides_remove_omitted_aliases() -> None:
    """Activation overrides should not reference omitted cube aliases."""

    pruned = WorkflowIssuePruningService().pruned_activation_overrides(
        {"Good": ("node",), "Bad": ("node",)},
        errored_aliases={"Bad"},
    )

    assert pruned == {"Good": ("node",)}


def test_pruned_global_override_scopes_drop_empty_partial_scopes() -> None:
    """Partial override scopes should drop omitted fields and empty scopes."""

    retained_scope = GlobalOverrideSerializationScope(
        override_key="sampler",
        value="euler",
        mode="partial",
        full_participation=False,
        participant_fields=frozenset(
            {
                ("Good", "sampler", "sampler_name"),
                ("Bad", "sampler", "sampler_name"),
            }
        ),
    )
    removed_scope = GlobalOverrideSerializationScope(
        override_key="cfg",
        value=7,
        mode="partial",
        full_participation=False,
        participant_fields=frozenset({("Bad", "sampler", "cfg")}),
    )
    full_scope = GlobalOverrideSerializationScope(
        override_key="steps",
        value=20,
        mode="full",
        full_participation=True,
        participant_fields=frozenset(),
    )

    pruned = WorkflowIssuePruningService().pruned_global_override_scopes(
        {
            "sampler": retained_scope,
            "cfg": removed_scope,
            "steps": full_scope,
        },
        errored_aliases={"Bad"},
    )

    assert pruned is not None
    assert set(pruned) == {"sampler", "steps"}
    assert pruned["steps"] == full_scope
    sampler_scope = cast(GlobalOverrideSerializationScope, pruned["sampler"])
    assert sampler_scope.participant_fields == frozenset(
        {("Good", "sampler", "sampler_name")}
    )
