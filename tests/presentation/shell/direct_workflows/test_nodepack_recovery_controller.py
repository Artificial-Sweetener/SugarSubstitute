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
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackResolutionPlan,
    WorkflowNodepackSourceKind,
    UnresolvedWorkflowNode,
    UnresolvedWorkflowNodeReason,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
    WorkflowNodepackRecoveryPlanService,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
)
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
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
)
from tests.support.execution import ImmediateTaskSubmitter
from tests.support.nodepack_recovery import (
    Handoff as _Handoff,
    Installer as _Installer,
    Plans as _Plans,
    change as _change,
    plan as _plan,
)


def test_approved_install_restarts_verifies_and_reloads_same_workflow(
    tmp_path: Path,
) -> None:
    """Successful recovery reloads the GUI only after fresh Comfy verification."""

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
    handoff = _Handoff()
    reviews: list[WorkflowNodepackRecoveryPlan] = []
    failures: list[tuple[str, str, BaseException]] = []
    restarts: list[str] = []
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
        present_review=present_review,
        present_failure=lambda workflow_id, stage, error: failures.append(
            (workflow_id, stage, error)
        ),
        can_restart=lambda: True,
        handoff_provider=lambda: handoff,
        request_restart=request_restart,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: closed.append("closed"),
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow=workflow, target_workflow_id="workflow-1")

    assert reviews == [_plan(missing=True)]
    assert len(installer.calls) == 1
    assert restarts == ["restart"]
    assert failures == []
    assert handoff.events == ["begin", "report", "report"]

    controller.observe_connection(
        _change(ComfyConnectionPhase.RESTARTING, ComfyConnectionPhase.READY)
    )

    assert plans.workflows == [workflow, workflow]
    assert handoff.events == ["begin", "report", "report", "report", "reload"]
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
        present_review=present_review,
        present_failure=lambda _workflow_id, _stage, _error: None,
        can_restart=lambda: True,
        handoff_provider=lambda: _Handoff(),
        request_restart=request_restart,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert cancelled == ["shown"]
    assert installer.calls == []
    assert restarts == []


def test_reassessed_open_workflow_updates_cards_before_install_offer(
    tmp_path: Path,
) -> None:
    """A restored workflow can become degraded and offer repair without a reload."""

    plan = _plan(missing=True)
    events: list[str] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(WorkflowNodepackRecoveryPlanService, _Plans([plan])),
        installer=cast(
            WorkflowNodepackInstaller,
            _Installer(WorkflowNodepackInstallResult(items=())),
        ),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=lambda _plan, _approve, _cancel: events.append("offer"),
        present_failure=lambda _workflow_id, _stage, _error: events.append("failure"),
        can_restart=lambda: True,
        handoff_provider=lambda: _Handoff(),
        request_restart=lambda: True,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.reassess_open_workflow(
        workflow={"nodes": [{"id": 1, "type": "Missing"}]},
        target_workflow_id="existing-workflow",
        refresh_projection=lambda assessment: events.append(
            f"cards:{','.join(assessment.missing_class_types)}"
        ),
    )

    assert events == ["cards:Missing", "offer"]


def test_unknown_missing_node_does_not_offer_unavailable_install(
    tmp_path: Path,
) -> None:
    """An unidentified package leaves the workflow visible without a false offer."""

    plan = _plan(missing=True)
    unresolved_plan = replace(
        plan,
        resolution=WorkflowNodepackResolutionPlan(
            candidates=(),
            unresolved=(
                UnresolvedWorkflowNode(
                    node=plan.assessment.missing[0],
                    reason=UnresolvedWorkflowNodeReason.NOT_IN_CATALOG,
                ),
            ),
        ),
    )
    reviews: list[WorkflowNodepackRecoveryPlan] = []
    failures: list[BaseException] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(
            WorkflowNodepackRecoveryPlanService, _Plans([unresolved_plan])
        ),
        installer=cast(
            WorkflowNodepackInstaller,
            _Installer(WorkflowNodepackInstallResult(items=())),
        ),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=lambda review, _approve, _cancel: reviews.append(review),
        present_failure=lambda _workflow_id, _stage, error: failures.append(error),
        can_restart=lambda: True,
        handoff_provider=lambda: _Handoff(),
        request_restart=lambda: True,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert reviews == []
    assert failures == []


def test_missing_local_install_environment_does_not_offer_false_repair() -> None:
    """A known package is not offered when this Comfy target cannot install it."""

    reviews: list[WorkflowNodepackRecoveryPlan] = []
    failures: list[BaseException] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(
            WorkflowNodepackRecoveryPlanService, _Plans([_plan(missing=True)])
        ),
        installer=cast(
            WorkflowNodepackInstaller,
            _Installer(WorkflowNodepackInstallResult(items=())),
        ),
        workspace=None,
        python_executable=None,
        present_review=lambda plan, _approve, _cancel: reviews.append(plan),
        present_failure=lambda _workflow_id, _stage, error: failures.append(error),
        can_restart=lambda: True,
        handoff_provider=lambda: _Handoff(),
        request_restart=lambda: True,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert reviews == []
    assert failures == []


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
    handoff = _Handoff()
    failures: list[BaseException] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(
            WorkflowNodepackRecoveryPlanService, _Plans([_plan(missing=True)])
        ),
        installer=cast(WorkflowNodepackInstaller, _Installer(result)),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=lambda plan, approve, _cancel: approve(
            plan.resolution.candidates
        ),
        present_failure=lambda _workflow_id, _stage, error: failures.append(error),
        can_restart=lambda: True,
        handoff_provider=lambda: handoff,
        request_restart=lambda: False,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")

    assert handoff.events == ["begin", "report", "report", "cancel"]
    assert any(
        isinstance(error, WorkflowNodepackRestartUnavailableError) for error in failures
    )


@pytest.mark.parametrize(
    ("post_restart_phase", "reload_accepted"),
    [
        (ComfyConnectionPhase.RESTART_FAILED, True),
        (ComfyConnectionPhase.READY, False),
    ],
)
def test_recovery_failure_restores_old_shell_without_false_success(
    tmp_path: Path,
    post_restart_phase: ComfyConnectionPhase,
    reload_accepted: bool,
) -> None:
    """Restart and GUI reload failures both restore the visible old shell."""

    installed = WorkflowNodepackInstallResult(
        items=(
            WorkflowNodepackInstallItemResult(
                package_id="missing-pack",
                version="1.0.0",
                source_kind=WorkflowNodepackSourceKind.REGISTRY,
                status=WorkflowNodepackInstallStatus.INSTALLED,
            ),
        )
    )
    plans = _Plans([_plan(missing=True), _plan(missing=False)])
    handoff = _Handoff(reload_accepted=reload_accepted)
    failures: list[tuple[str, BaseException]] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(WorkflowNodepackRecoveryPlanService, plans),
        installer=cast(WorkflowNodepackInstaller, _Installer(installed)),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=lambda plan, approve, _cancel: approve(
            plan.resolution.candidates
        ),
        present_failure=lambda _id, stage, error: failures.append((stage, error)),
        can_restart=lambda: True,
        handoff_provider=lambda: handoff,
        request_restart=lambda: True,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")
    controller.observe_connection(
        _change(ComfyConnectionPhase.RESTARTING, post_restart_phase)
    )

    assert len(failures) == 1
    assert handoff.events[-1] == "cancel"
    assert handoff.events.count("reload") == (
        1 if post_restart_phase is ComfyConnectionPhase.READY else 0
    )


def test_remaining_missing_nodes_reload_gui_with_fresh_degraded_cards(
    tmp_path: Path,
) -> None:
    """A partial Comfy recovery must not preserve stale old-shell definitions."""

    installed = WorkflowNodepackInstallResult(
        items=(
            WorkflowNodepackInstallItemResult(
                package_id="missing-pack",
                version="1.0.0",
                source_kind=WorkflowNodepackSourceKind.REGISTRY,
                status=WorkflowNodepackInstallStatus.INSTALLED,
            ),
        )
    )
    handoff = _Handoff()
    failures: list[BaseException] = []
    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=cast(
            WorkflowNodepackRecoveryPlanService,
            _Plans([_plan(missing=True), _plan(missing=True)]),
        ),
        installer=cast(WorkflowNodepackInstaller, _Installer(installed)),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=lambda plan, approve, _cancel: approve(
            plan.resolution.candidates
        ),
        present_failure=lambda _id, _stage, error: failures.append(error),
        can_restart=lambda: True,
        handoff_provider=lambda: handoff,
        request_restart=lambda: True,
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow={"nodes": [], "links": []}, target_workflow_id="wf")
    controller.observe_connection(
        _change(ComfyConnectionPhase.RESTARTING, ComfyConnectionPhase.READY)
    )

    assert handoff.events == ["begin", "report", "report", "report", "reload"]
    assert failures == []
