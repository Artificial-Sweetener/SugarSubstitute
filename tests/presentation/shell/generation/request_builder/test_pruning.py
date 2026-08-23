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

"""Tests for shell generation request-building policy helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.shell.workspace_generation_request_builder import (
    GenerationWorkflowPruneReport,
    pruned_workflow_for_generation,
    workflow_stack_order,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_pruned_workflow_for_generation_omits_errored_cubes() -> None:
    """Workflow pruning should omit errored cubes and report safe diagnostics."""

    workflow = SimpleNamespace(
        stack_order=["A", "Errored"],
        cubes={"A": object(), "Errored": object()},
    )
    reports: list[GenerationWorkflowPruneReport] = []

    pruned = pruned_workflow_for_generation(
        view=SimpleNamespace(node_behavior_service=None),
        workflow=workflow,
        workflow_id="wf-a",
        workflow_name="Recipe",
        errored_aliases=("Errored",),
        empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        omission_logger=reports.append,
    )
    pruned_workflow = cast(Any, pruned)

    assert pruned is not workflow
    assert pruned_workflow.stack_order == ["A"]
    assert tuple(pruned_workflow.cubes) == ("A",)
    assert reports == [
        GenerationWorkflowPruneReport(
            workflow_id="wf-a",
            workflow_name="Recipe",
            omitted_cube_aliases=("Errored",),
            remaining_cube_count=1,
        )
    ]


def test_pruned_workflow_for_generation_fails_when_all_cubes_errored() -> None:
    """Workflow pruning should fail closed when no generation cubes remain."""

    workflow = SimpleNamespace(
        stack_order=["Errored"],
        cubes={"Errored": object()},
    )
    expected_error = RuntimeError("empty")

    try:
        pruned_workflow_for_generation(
            view=SimpleNamespace(node_behavior_service=None),
            workflow=workflow,
            workflow_id="wf-a",
            workflow_name="Recipe",
            errored_aliases=("Errored",),
            empty_workflow_error=lambda: expected_error,
        )
    except RuntimeError as error:
        assert error is expected_error
    else:
        raise AssertionError("expected empty workflow error")


def test_workflow_stack_order_returns_tuple() -> None:
    """Workflow stack-order lookup should normalize missing and list values."""

    assert workflow_stack_order(SimpleNamespace(stack_order=["A", "B"])) == ("A", "B")
    assert workflow_stack_order(SimpleNamespace()) == ()
