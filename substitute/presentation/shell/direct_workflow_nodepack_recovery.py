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

"""Coordinate missing-node recovery for already materialized direct workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackInstallCandidate,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
    WorkflowNodepackRecoveryPlanService,
)
from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionStateChange,
)
from substitute.domain.common import JsonObject
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
    WorkflowNodepackInstallResult,
)
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
)
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
    WorkflowNodepackRecoveryRouteFactory,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("presentation.shell.direct_workflow_nodepack_recovery")

NodepackReviewPresenter = Callable[
    [
        WorkflowNodepackRecoveryPlan,
        Callable[[tuple[WorkflowNodepackInstallCandidate, ...]], None],
        Callable[[], None],
    ],
    None,
]
RecoveryFailurePresenter = Callable[[str, str, BaseException], None]


class WorkflowNodepackInstallIncompleteError(RuntimeError):
    """Report an approved batch that did not install every package."""


class WorkflowNodepackRestartUnavailableError(RuntimeError):
    """Report that installed packages cannot be activated automatically."""


class WorkflowNodepackRecoveryIncompleteError(RuntimeError):
    """Report definitions that remain unavailable after restart."""


class WorkflowNodepackInstallationUnavailableError(RuntimeError):
    """Report that the selected Comfy target has no writable local environment."""


@dataclass(slots=True)
class _ActiveOperation:
    """Retain one execution route until its owner-thread callback settles."""

    scope: TaskScope
    route: WorkflowNodepackRecoveryRoute
    busy_token: object | None = None


@dataclass(frozen=True, slots=True)
class _PendingRecovery:
    """Retain the same workflow across Comfy restart and verification."""

    workflow: JsonObject


class DirectWorkflowNodepackRecoveryController:
    """Recover missing workflow nodepacks without blocking the Qt owner thread."""

    def __init__(
        self,
        *,
        plan_service: WorkflowNodepackRecoveryPlanService,
        installer: WorkflowNodepackInstaller,
        workspace: Path | None,
        python_executable: Path | None,
        editor_busy: EditorBusyControllerProtocol,
        present_review: NodepackReviewPresenter,
        present_failure: RecoveryFailurePresenter,
        request_restart: Callable[[], bool],
        rehydrate_workflow: Callable[[str], None],
        route_factory: WorkflowNodepackRecoveryRouteFactory,
    ) -> None:
        """Store planning, acquisition, recovery, and owner-thread collaborators."""

        self._plan_service = plan_service
        self._installer = installer
        self._workspace = workspace
        self._python_executable = python_executable
        self._editor_busy = editor_busy
        self._present_review = present_review
        self._present_failure = present_failure
        self._request_restart = request_restart
        self._rehydrate_workflow = rehydrate_workflow
        self._route_factory = route_factory
        self._request_id = 0
        self._active: list[_ActiveOperation] = []
        self._pending: dict[str, _PendingRecovery] = {}

    def recover(self, *, workflow: JsonObject, target_workflow_id: str) -> None:
        """Assess one visible workflow and offer any deterministic package matches."""

        try:
            self._submit_plan(
                workflow=workflow,
                target_workflow_id=target_workflow_id,
                verification=False,
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Could not schedule workflow nodepack resolution",
                error=error,
                workflow_id=target_workflow_id,
            )
            self._present_failure(target_workflow_id, "resolve_nodepacks", error)

    def observe_connection(self, change: ComfyConnectionStateChange) -> None:
        """Verify pending workflows after a restart reconnects or report failure."""

        if change.current.phase is ComfyConnectionPhase.RESTART_FAILED:
            for workflow_id in tuple(self._pending):
                self._present_failure(
                    workflow_id,
                    "restart",
                    WorkflowNodepackRestartUnavailableError(
                        "ComfyUI did not restart after nodepack installation."
                    ),
                )
            return
        if (
            change.current.phase is not ComfyConnectionPhase.READY
            or change.previous.phase is ComfyConnectionPhase.READY
        ):
            return
        for workflow_id, pending in tuple(self._pending.items()):
            self._submit_plan(
                workflow=pending.workflow,
                target_workflow_id=workflow_id,
                verification=True,
            )

    def close(self) -> None:
        """Release active task scopes during shell teardown."""

        for active in tuple(self._active):
            self._finish(active)
        self._pending.clear()

    def _submit_plan(
        self,
        *,
        workflow: JsonObject,
        target_workflow_id: str,
        verification: bool,
    ) -> None:
        """Run live definition assessment and package lookup off the owner thread."""

        active, request_id = self._begin_operation(target_workflow_id)
        request: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="workflow_nodepack_verification"
                if verification
                else "workflow_nodepack_resolution",
                parts=(("workflow_id", target_workflow_id),),
            ),
            context=ExecutionContext(
                operation="verify_workflow_nodepacks"
                if verification
                else "resolve_workflow_nodepacks",
                reason="comfy_restart" if verification else "canonical_workflow_load",
                lane="package_maintenance",
                safe_fields=(("workflow_id", target_workflow_id),),
            ),
            work=lambda _token: self._plan_service.plan(workflow),
        )

        def receive(outcome: TaskOutcome[object]) -> None:
            """Continue with review, recovery completion, or diagnostics."""

            self._finish(active)
            if outcome.status != "succeeded":
                if outcome.status == "failed":
                    self._present_failure(
                        target_workflow_id,
                        "verify_nodepacks" if verification else "resolve_nodepacks",
                        outcome.error
                        or RuntimeError("Workflow nodepack resolution failed."),
                    )
                return
            plan = cast(WorkflowNodepackRecoveryPlan, outcome.result)
            if verification:
                self._finish_verification(target_workflow_id, plan)
                return
            if not plan.requires_review:
                return
            self._present_review(
                plan,
                lambda candidates: self._install(
                    candidates=candidates,
                    workflow=workflow,
                    target_workflow_id=target_workflow_id,
                ),
                lambda: log_info(
                    _LOGGER,
                    "Workflow nodepack installation review cancelled",
                    workflow_id=target_workflow_id,
                    missing_node_classes=",".join(plan.assessment.missing_class_types),
                ),
            )

        self._submit(active, request, receive)

    def _install(
        self,
        *,
        candidates: tuple[WorkflowNodepackInstallCandidate, ...],
        workflow: JsonObject,
        target_workflow_id: str,
    ) -> None:
        """Install one approved batch before requesting managed Comfy restart."""

        if not candidates:
            return
        workspace = self._workspace
        python_executable = self._python_executable
        if workspace is None or python_executable is None:
            self._present_failure(
                target_workflow_id,
                "install_nodepacks",
                WorkflowNodepackInstallationUnavailableError(
                    "Automatic custom node installation requires a local ComfyUI workspace and Python environment."
                ),
            )
            return
        active, request_id = self._begin_operation(
            target_workflow_id,
            busy_message=app_text("Installing required custom nodes"),
        )
        request: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="workflow_nodepack_install",
                parts=(("workflow_id", target_workflow_id),),
            ),
            context=ExecutionContext(
                operation="install_workflow_nodepacks",
                reason="user_approved_missing_nodes",
                lane="package_maintenance",
                safe_fields=(("workflow_id", target_workflow_id),),
            ),
            work=lambda _token: self._installer.install(
                candidates,
                workspace=workspace,
                python_executable=python_executable,
            ),
        )

        def receive(outcome: TaskOutcome[object]) -> None:
            """Request restart after successful source installation settles."""

            self._finish(active)
            if outcome.status != "succeeded":
                if outcome.status == "failed":
                    self._present_failure(
                        target_workflow_id,
                        "install_nodepacks",
                        outcome.error
                        or RuntimeError("Workflow nodepack installation failed."),
                    )
                return
            result = cast(WorkflowNodepackInstallResult, outcome.result)
            if result.failed:
                self._present_failure(
                    target_workflow_id,
                    "install_nodepacks",
                    WorkflowNodepackInstallIncompleteError(
                        "One or more approved custom node packages could not be installed."
                    ),
                )
            if not result.installed_package_ids:
                return
            self._pending[target_workflow_id] = _PendingRecovery(workflow=workflow)
            if not self._request_restart():
                self._present_failure(
                    target_workflow_id,
                    "restart",
                    WorkflowNodepackRestartUnavailableError(
                        "Installed custom nodes require a ComfyUI restart."
                    ),
                )

        self._submit(active, request, receive)

    def _finish_verification(
        self,
        target_workflow_id: str,
        plan: WorkflowNodepackRecoveryPlan,
    ) -> None:
        """Rehydrate a recovered workflow or preserve explicit degraded evidence."""

        if plan.assessment.missing:
            self._present_failure(
                target_workflow_id,
                "verify_nodepacks",
                WorkflowNodepackRecoveryIncompleteError(
                    "Missing definitions after restart: "
                    + ", ".join(plan.assessment.missing_class_types)
                ),
            )
            return
        self._pending.pop(target_workflow_id, None)
        self._rehydrate_workflow(target_workflow_id)
        log_info(
            _LOGGER,
            "Workflow nodepack recovery completed",
            workflow_id=target_workflow_id,
        )

    def _begin_operation(
        self,
        target_workflow_id: str,
        *,
        busy_message: ApplicationText | None = None,
    ) -> tuple[_ActiveOperation, int]:
        """Create and retain one package-maintenance task route."""

        self._request_id += 1
        request_id = self._request_id
        route = self._route_factory(
            request_id=request_id,
            target_workflow_id=target_workflow_id,
        )
        scope = TaskScope(
            submitter=route.submitter,
            scope_id=f"workflow_nodepack_recovery_{target_workflow_id}_{request_id}",
        )
        busy_token = (
            self._editor_busy.begin(target_workflow_id, message=busy_message)
            if busy_message is not None
            else None
        )
        active = _ActiveOperation(scope=scope, route=route, busy_token=busy_token)
        self._active.append(active)
        return active, request_id

    def _submit(
        self,
        active: _ActiveOperation,
        request: TaskRequest[object],
        receive: Callable[[TaskOutcome[object]], None],
    ) -> None:
        """Submit one operation and register its owner-thread completion."""

        try:
            handle = active.scope.submit(request)
            handle.add_done_callback(receive, reason="workflow_nodepack_recovery_done")
        except Exception:
            self._finish(active)
            raise

    def _finish(self, active: _ActiveOperation) -> None:
        """Release one completed or cancelled operation exactly once."""

        if active not in self._active:
            return
        if active.busy_token is not None:
            self._editor_busy.end(active.busy_token)
        active.scope.close(reason="workflow_nodepack_recovery_finished")
        active.route.close()
        self._active.remove(active)


__all__ = [
    "DirectWorkflowNodepackRecoveryController",
    "NodepackReviewPresenter",
    "RecoveryFailurePresenter",
    "WorkflowNodepackInstallIncompleteError",
    "WorkflowNodepackInstallationUnavailableError",
    "WorkflowNodepackRecoveryIncompleteError",
    "WorkflowNodepackRestartUnavailableError",
]
