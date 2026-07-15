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

"""Tests for extracted editor panel projection preparation ownership."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TypeVar

import pytest

from substitute.presentation.editor.panel.projection_preparation import (
    EditorProjectionPreparationController,
    EditorProjectionPreparationRequest,
    begin_behavior_refresh_transaction,
    end_behavior_refresh_transaction,
)

_T = TypeVar("_T")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)


class _Panel:
    """Panel test double exposing projection preparation inputs."""

    def __init__(self) -> None:
        self._cube_states: dict[str, object] | None = None
        self._stack_order: list[str] | None = None
        self._current_search_hidden_keys: set[object] | None = {("Cube", "Node")}
        self._current_search_matching_nodes: set[object] | None = {"Cube.Node"}
        self._current_node_search_text: str | None = "node"
        self.reconciled = False
        self.links_refreshed = 0

    def reconcile_prompt_link_state(self, **_kwargs: object) -> None:
        """Record prompt-link reconciliation."""

        self.reconciled = True

    def _build_behavior_snapshot(self, **_kwargs: object) -> object:
        """Return a behavior snapshot object."""

        return SimpleNamespace(snapshot=True)

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Record link-state refresh."""

        self.links_refreshed += 1


class _RuntimeIssues:
    """Runtime issue test double for successful projection preparation."""

    def __init__(self) -> None:
        self.hydrated = False

    def hydrate_node_definitions_for_projection(
        self,
        *,
        reason: str,
        workflow_id: str,
    ) -> None:
        """Record definition hydration."""

        self.hydrated = bool(reason and workflow_id)

    def cube_runtime_error_aliases(self) -> frozenset[str]:
        """Return one stable runtime issue alias."""

        return frozenset({"Errored"})

    def run_projection_metadata_step(
        self,
        *,
        workflow_id: str,
        reason: str,
        action: Callable[[frozenset[str]], _T],
    ) -> _T:
        """Run metadata actions with the current errored aliases."""

        del workflow_id, reason
        return action(self.cube_runtime_error_aliases())

    def run_with_pruned_panel_state(
        self,
        errored_aliases: frozenset[str],
        action: Callable[[], _T],
    ) -> _T:
        """Run one pruned-state action."""

        del errored_aliases
        return action()


class _FailingRuntimeIssues(_RuntimeIssues):
    """Runtime issue test double that fails while building behavior snapshots."""

    def run_projection_metadata_step(
        self,
        *,
        workflow_id: str,
        reason: str,
        action: Callable[[frozenset[str]], _T],
    ) -> _T:
        """Raise during behavior snapshot preparation."""

        if reason == "behavior_snapshot":
            raise RuntimeError("snapshot failed")
        return super().run_projection_metadata_step(
            workflow_id=workflow_id,
            reason=reason,
            action=action,
        )


def test_projection_preparation_identity_includes_phase26_freshness_inputs() -> None:
    """Preparation identity must include every Phase 26.2 freshness input."""

    panel = _Panel()
    runtime_issues = _RuntimeIssues()
    transactions: list[tuple[str, str, bool]] = []
    controller = EditorProjectionPreparationController(
        panel=panel,
        prompt_context=None,
        runtime_issues=runtime_issues,
        begin_behavior_transaction=lambda reason, workflow_id: bool(
            reason and workflow_id
        ),
        end_behavior_transaction=(
            lambda reason, workflow_id, started: transactions.append(
                (reason, workflow_id, started)
            )
        ),
    )
    cube_state = SimpleNamespace(
        cube_id="cube-id",
        version="v1",
        buffer={"nodes": {"Node": {"class_type": "KSampler", "inputs": {"seed": 1}}}},
    )

    preparation = controller.prepare_projection(
        [("Cube", cube_state)],
        cube_states={"Cube": cube_state},
        stack_order=["Cube"],
        reason="full_workflow_projection",
        workflow_id="workflow",
        previous_cube_states=None,
        previous_stack_order=None,
        prompt_context_required=False,
    )

    identity = preparation.identity
    assert runtime_issues.hydrated
    assert panel.reconciled
    assert panel.links_refreshed == 1
    assert identity.workflow_id == "workflow"
    assert identity.stack_order == ("Cube",)
    assert identity.runtime_issue_identity == ("Errored",)
    assert identity.search_identity == ("node", ("'Cube.Node'",))
    assert identity.hidden_field_identity == ("('Cube', 'Node')",)
    assert identity.prompt_context_identity == (
        False,
        id(preparation.request.cube_states),
        ("Cube",),
        "full_workflow_projection",
    )
    assert identity.projection_mode == "live"
    assert identity.cube_definition_identities[0][0] == "Cube"
    assert transactions == []


def test_projection_preparation_ends_behavior_transaction_on_failure() -> None:
    """Failed behavior snapshot preparation must close opened transactions."""

    panel = _Panel()
    ended: list[tuple[str, str, bool]] = []
    controller = EditorProjectionPreparationController(
        panel=panel,
        prompt_context=None,
        runtime_issues=_FailingRuntimeIssues(),
        begin_behavior_transaction=lambda _reason, _workflow_id: True,
        end_behavior_transaction=(
            lambda reason, workflow_id, started: ended.append(
                (reason, workflow_id, started)
            )
        ),
    )
    request = EditorProjectionPreparationRequest(
        cube_entries=(),
        cube_states={},
        stack_order=(),
        previous_cube_states=None,
        previous_stack_order=None,
        reason="full_workflow_projection",
        workflow_id="workflow",
        prompt_context_required=False,
    )

    with pytest.raises(RuntimeError, match="snapshot failed"):
        controller.prepare_projection(
            request.cube_entries,
            cube_states=request.cube_states,
            stack_order=request.stack_order,
            reason=request.reason,
            workflow_id=request.workflow_id,
            previous_cube_states=None,
            previous_stack_order=None,
        )

    assert ended == [("full_workflow_projection", "workflow", True)]


def test_behavior_refresh_transaction_helpers_call_supported_panel_hooks() -> None:
    """Preparation-owned transaction helpers should call optional panel hooks."""

    calls: list[tuple[str, str]] = []
    panel = SimpleNamespace(
        begin_behavior_refresh_transaction=(
            lambda *, reason: calls.append(("begin", reason))
        ),
        end_behavior_refresh_transaction=(
            lambda *, reason: calls.append(("end", reason))
        ),
    )

    started = begin_behavior_refresh_transaction(
        panel,
        reason="full_workflow_projection",
        workflow_id="workflow",
    )
    end_behavior_refresh_transaction(
        panel,
        reason="full_workflow_projection",
        workflow_id="workflow",
        transaction_started=started,
    )

    assert started is True
    assert calls == [
        ("begin", "full_workflow_projection"),
        ("end", "full_workflow_projection"),
    ]


def test_behavior_refresh_transaction_helpers_skip_missing_or_unstarted_hooks() -> None:
    """Preparation-owned transaction helpers should tolerate absent panel hooks."""

    panel = SimpleNamespace()

    started = begin_behavior_refresh_transaction(
        panel,
        reason="cube_added",
        workflow_id="workflow",
    )
    end_behavior_refresh_transaction(
        panel,
        reason="cube_added",
        workflow_id="workflow",
        transaction_started=started,
    )

    assert started is False


def test_projection_coordinator_no_longer_defines_preparation_wrappers() -> None:
    """Projection preparation pass-throughs should not return to the coordinator."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "_prepare_projection" not in coordinator_methods
    assert "_clear_projection_prompt_context_for_preparation" not in coordinator_methods
    assert "_end_preparation_behavior_transaction" not in coordinator_methods
    assert "_begin_behavior_refresh_transaction" not in coordinator_methods
    assert "_end_behavior_refresh_transaction" not in coordinator_methods
