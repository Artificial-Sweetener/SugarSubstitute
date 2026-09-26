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

"""Tests for direct-workflow nodepack recovery orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

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
    WorkflowNodepackRecoveryPlanService,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)
from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem
from substitute.domain.onboarding import ComfyTargetMode
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
    WorkflowNodepackInstallItemResult,
    WorkflowNodepackInstallResult,
    WorkflowNodepackInstallStatus,
)
from substitute.presentation.shell.direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
    WorkflowNodepackRestartUnavailableError,
)
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
)
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
)
from tests.support.execution import ImmediateTaskSubmitter


class _Plans:
    """Return queued recovery plans in request order."""

    def __init__(self, plans: list[WorkflowNodepackRecoveryPlan]) -> None:
        """Store queued plans and initialize workflow recording."""

        self.plans = plans
        self.workflows: list[object] = []

    def plan(self, workflow: object) -> WorkflowNodepackRecoveryPlan:
        """Record the workflow and return the next plan."""

        self.workflows.append(workflow)
        return self.plans.pop(0)


class _Installer:
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
    ) -> WorkflowNodepackInstallResult:
        """Record the approved package batch and return its result."""

        self.calls.append((candidates, workspace, python_executable))
        return self.result


class _Busy:
    """Record workflow busy-token lifecycles."""

    def __init__(self) -> None:
        """Initialize busy operation recording."""

        self.begun: list[tuple[str, object]] = []
        self.ended: list[object] = []

    def begin(self, workflow_id: str, *, message: object) -> object:
        """Return a stable token for one busy operation."""

        token = object()
        self.begun.append((workflow_id, message))
        return token

    def end(self, token: object) -> None:
        """Record completion for one token."""

        self.ended.append(token)


def _candidate() -> WorkflowNodepackInstallCandidate:
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


def _plan(*, missing: bool) -> WorkflowNodepackRecoveryPlan:
    """Build a missing or fully recovered assessment and resolution plan."""

    node = _candidate().nodes[0]
    return WorkflowNodepackRecoveryPlan(
        assessment=WorkflowNodeDefinitionAssessment(
            available=() if missing else (node,),
            missing=(node,) if missing else (),
        ),
        resolution=WorkflowNodepackResolutionPlan(
            candidates=(_candidate(),) if missing else (),
            unresolved=(),
        ),
    )


def _change(
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


def test_approved_install_restarts_verifies_and_rehydrates_same_workflow(
    tmp_path: Path,
) -> None:
    """Successful recovery should preserve the workflow through reconnect."""

    plans = _Plans([_plan(missing=True), _plan(missing=False)])
    installer = _Installer(
        WorkflowNodepackInstallResult(
            items=(
                WorkflowNodepackInstallItemResult(
                    package_id="missing-pack",
                    version="1.0.0",
                    source_kind=WorkflowNodepackSourceKind.REGISTRY,
                    status=WorkflowNodepackInstallStatus.INSTALLED,
                ),
            )
        )
    )
    busy = _Busy()
    reviews: list[WorkflowNodepackRecoveryPlan] = []
    failures: list[tuple[str, str, BaseException]] = []
    restarts: list[str] = []
    rehydrated: list[str] = []
    closed: list[str] = []
    workflow: dict[str, object] = {"nodes": [], "links": []}

    def present_review(
        plan: WorkflowNodepackRecoveryPlan,
        approve: Callable[[tuple[WorkflowNodepackInstallCandidate, ...]], None],
        _cancel: Callable[[], None],
    ) -> None:
        """Record and approve the complete deterministic package plan."""

        reviews.append(plan)
        approve(plan.resolution.candidates)

    def request_restart() -> bool:
        """Record the accepted managed restart request."""

        restarts.append("restart")
        return True

    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(WorkflowNodepackRecoveryPlanService, plans),
        installer=cast(WorkflowNodepackInstaller, installer),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        editor_busy=cast(EditorBusyControllerProtocol, busy),
        present_review=present_review,
        present_failure=lambda workflow_id, stage, error: failures.append(
            (workflow_id, stage, error)
        ),
        request_restart=request_restart,
        rehydrate_workflow=rehydrated.append,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: closed.append("closed"),
        ),
    )

    controller.recover(workflow=workflow, target_workflow_id="workflow-1")

    assert reviews == [_plan(missing=True)]
    assert len(installer.calls) == 1
    assert restarts == ["restart"]
    assert failures == []
    assert len(busy.begun) == 1
    assert len(busy.ended) == 1

    controller.observe_connection(
        _change(ComfyConnectionPhase.RESTARTING, ComfyConnectionPhase.READY)
    )

    assert plans.workflows == [workflow, workflow]
    assert rehydrated == ["workflow-1"]
    assert len(closed) == 3


def test_cancelled_review_leaves_visible_workflow_untouched(tmp_path: Path) -> None:
    """Closing the install offer should not install, restart, or retain busy state."""

    plans = _Plans([_plan(missing=True)])
    installer = _Installer(WorkflowNodepackInstallResult(items=()))
    cancelled: list[str] = []
    restarts: list[str] = []

    def present_review(
        _plan: WorkflowNodepackRecoveryPlan,
        _approve: Callable[[tuple[WorkflowNodepackInstallCandidate, ...]], None],
        cancel: Callable[[], None],
    ) -> None:
        """Record and cancel the package review without mutation."""

        cancelled.append("shown")
        cancel()

    def request_restart() -> bool:
        """Record an unexpected restart request."""

        restarts.append("restart")
        return True

    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(WorkflowNodepackRecoveryPlanService, plans),
        installer=cast(WorkflowNodepackInstaller, installer),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        editor_busy=cast(EditorBusyControllerProtocol, _Busy()),
        present_review=present_review,
        present_failure=lambda _workflow_id, _stage, _error: None,
        request_restart=request_restart,
        rehydrate_workflow=lambda _workflow_id: None,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(), close=lambda: None
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert cancelled == ["shown"]
    assert installer.calls == []
    assert restarts == []


def test_restart_refusal_is_diagnostic_and_does_not_softlock(tmp_path: Path) -> None:
    """An unavailable restart must release busy state and retain actionable failure."""

    result = WorkflowNodepackInstallResult(
        items=(
            WorkflowNodepackInstallItemResult(
                package_id="missing-pack",
                version="1.0.0",
                source_kind=WorkflowNodepackSourceKind.REGISTRY,
                status=WorkflowNodepackInstallStatus.INSTALLED,
            ),
        )
    )
    busy = _Busy()
    failures: list[BaseException] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(
            WorkflowNodepackRecoveryPlanService, _Plans([_plan(missing=True)])
        ),
        installer=cast(WorkflowNodepackInstaller, _Installer(result)),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        editor_busy=cast(EditorBusyControllerProtocol, busy),
        present_review=lambda plan, approve, _cancel: approve(
            plan.resolution.candidates
        ),
        present_failure=lambda _workflow_id, _stage, error: failures.append(error),
        request_restart=lambda: False,
        rehydrate_workflow=lambda _workflow_id: None,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(), close=lambda: None
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert len(busy.begun) == len(busy.ended) == 1
    assert any(
        isinstance(error, WorkflowNodepackRestartUnavailableError) for error in failures
    )
