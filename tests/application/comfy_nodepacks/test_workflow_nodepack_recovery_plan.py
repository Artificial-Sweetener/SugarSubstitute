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

"""Tests for authoritative workflow nodepack recovery planning."""

from __future__ import annotations

from typing import cast

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackResolutionPlan,
    WorkflowNodepackResolutionService,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
    WorkflowNodeDefinitionAssessmentService,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlanService,
)
from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem


class _Assessment:
    """Return one configured live-definition assessment."""

    def __init__(self, value: WorkflowNodeDefinitionAssessment) -> None:
        """Store the assessment and initialize call recording."""

        self.value = value
        self.calls: list[object] = []

    def assess(self, workflow: object) -> WorkflowNodeDefinitionAssessment:
        """Record the workflow and return configured evidence."""

        self.calls.append(workflow)
        return self.value


class _Resolution:
    """Record only the missing nodes passed into package resolution."""

    def __init__(self) -> None:
        """Initialize call recording."""

        self.calls: list[tuple[WorkflowNodeInventoryItem, ...]] = []

    def resolve(
        self,
        missing: tuple[WorkflowNodeInventoryItem, ...],
    ) -> WorkflowNodepackResolutionPlan:
        """Record missing nodes and return an empty package plan."""

        self.calls.append(missing)
        return WorkflowNodepackResolutionPlan(candidates=(), unresolved=())


def test_plans_resolution_from_observed_missing_nodes_only() -> None:
    """Available nodes must never be offered as nodepack install candidates."""

    available = WorkflowNodeInventoryItem("1", "Ready", "Ready", None, None)
    missing = WorkflowNodeInventoryItem("2", "Missing", "Missing", None, None)
    assessment = _Assessment(
        WorkflowNodeDefinitionAssessment(available=(available,), missing=(missing,))
    )
    resolution = _Resolution()
    workflow: dict[str, object] = {"nodes": [], "links": []}

    plan = WorkflowNodepackRecoveryPlanService(
        assessment=cast(WorkflowNodeDefinitionAssessmentService, assessment),
        resolution=cast(WorkflowNodepackResolutionService, resolution),
    ).plan(workflow)

    assert assessment.calls == [workflow]
    assert resolution.calls == [(missing,)]
    assert plan.assessment.available == (available,)
    assert plan.requires_review
