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

"""Provide deterministic recovery plans and task collaborators for shell tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackResolutionPlan,
    WorkflowNodepackSourceKind,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)
from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem
from substitute.domain.onboarding import ComfyTargetMode
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstallProgress,
    WorkflowNodepackInstallResult,
    WorkflowNodepackInstallStage,
)


class Plans:
    """Return queued recovery plans in request order."""

    def __init__(self, plans: list[WorkflowNodepackRecoveryPlan]) -> None:
        """Store queued plans and initialize workflow recording."""

        self.plans = plans
        self.workflows: list[object] = []

    def plan(self, workflow: object) -> WorkflowNodepackRecoveryPlan:
        """Record the workflow and return the next plan."""

        self.workflows.append(workflow)
        return self.plans.pop(0)


class Installer:
    """Return one configured install result and record approved candidates."""

    def __init__(self, result: WorkflowNodepackInstallResult) -> None:
        """Store the result and initialize call recording."""

        self.result = result
        self.calls: list[tuple[object, Path, Path]] = []

    def install(
        self,
        candidates: object,
        *,
        workspace: Path,
        python_executable: Path,
        on_progress: Callable[[WorkflowNodepackInstallProgress], None] | None = None,
    ) -> WorkflowNodepackInstallResult:
        """Record the approved package batch and return its result."""

        self.calls.append((candidates, workspace, python_executable))
        if on_progress is not None:
            on_progress(
                WorkflowNodepackInstallProgress(
                    WorkflowNodepackInstallStage.SOURCE,
                    "Missing Pack",
                    1,
                    1,
                )
            )
        return self.result


class Handoff:
    """Record the splash and GUI-reload lifecycle."""

    def __init__(self, *, reload_accepted: bool = True) -> None:
        """Initialize visible recovery transition recording."""

        self.events: list[str] = []
        self.reload_accepted = reload_accepted

    def begin(self) -> bool:
        """Record the shell-to-splash handoff."""

        self.events.append("begin")
        return True

    def report(self, _message: object) -> None:
        """Record progress while the splash remains active."""

        self.events.append("report")

    def reload(self) -> bool:
        """Record the GUI rebuild after Comfy verification."""

        self.events.append("reload")
        return self.reload_accepted

    def cancel(self) -> None:
        """Record rollback to the old workflow shell."""

        self.events.append("cancel")


def candidate() -> WorkflowNodepackInstallCandidate:
    """Build one confirmed Registry candidate."""

    node = WorkflowNodeInventoryItem("1", "Missing", "Missing", None, None)
    return WorkflowNodepackInstallCandidate(
        nodepack=ResolvedWorkflowNodepack(
            identifier="missing-pack",
            display_name="Missing Pack",
            source_kind=WorkflowNodepackSourceKind.REGISTRY,
            repository_url=None,
            version="1.0.0",
        ),
        nodes=(node,),
        persisted_versions=(),
    )


def plan(*, missing: bool) -> WorkflowNodepackRecoveryPlan:
    """Build a missing or fully recovered assessment and resolution plan."""

    node = candidate().nodes[0]
    return WorkflowNodepackRecoveryPlan(
        assessment=WorkflowNodeDefinitionAssessment(
            available=() if missing else (node,),
            missing=(node,) if missing else (),
        ),
        resolution=WorkflowNodepackResolutionPlan(
            candidates=(candidate(),) if missing else (),
            unresolved=(),
        ),
    )


def change(
    previous: ComfyConnectionPhase,
    current: ComfyConnectionPhase,
) -> ComfyConnectionStateChange:
    """Build one managed-local connection transition."""

    return ComfyConnectionStateChange(
        previous=ComfyConnectionState(
            previous,
            ComfyTargetMode.MANAGED_LOCAL,
            True,
        ),
        current=ComfyConnectionState(
            current,
            ComfyTargetMode.MANAGED_LOCAL,
            True,
            revision=1,
        ),
    )
