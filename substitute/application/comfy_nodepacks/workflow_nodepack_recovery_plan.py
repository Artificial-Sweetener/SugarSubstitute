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

"""Plan missing workflow nodepack recovery from authoritative live state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackResolutionPlan,
    WorkflowNodepackResolutionService,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
    WorkflowNodeDefinitionAssessmentService,
)


@dataclass(frozen=True, slots=True)
class WorkflowNodepackRecoveryPlan:
    """Carry observed node availability and its reviewable acquisition plan."""

    assessment: WorkflowNodeDefinitionAssessment
    resolution: WorkflowNodepackResolutionPlan

    @property
    def requires_review(self) -> bool:
        """Return whether any missing nodes need user-visible recovery details."""

        return bool(self.assessment.missing)


class WorkflowNodepackRecoveryPlanService:
    """Assess live definitions before resolving only the observed missing nodes."""

    def __init__(
        self,
        *,
        assessment: WorkflowNodeDefinitionAssessmentService,
        resolution: WorkflowNodepackResolutionService,
    ) -> None:
        """Store the two ordered recovery planning stages."""

        self._assessment = assessment
        self._resolution = resolution

    def plan(self, workflow: Mapping[str, object]) -> WorkflowNodepackRecoveryPlan:
        """Build one deterministic recovery plan from current Comfy availability."""

        assessment = self._assessment.assess(workflow)
        return WorkflowNodepackRecoveryPlan(
            assessment=assessment,
            resolution=self._resolution.resolve(assessment.missing),
        )


__all__ = [
    "WorkflowNodepackRecoveryPlan",
    "WorkflowNodepackRecoveryPlanService",
]
