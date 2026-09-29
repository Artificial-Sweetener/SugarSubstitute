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
from typing import Protocol, cast

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackInstallCandidate,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
    WorkflowNodepackRecoveryPlanService,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
)
from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
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
from substitute.presentation.shell.workflow_nodepack_progress_presentation import (
    describe_nodepack_install_progress,
)
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRouteFactory,
)
from substitute.presentation.shell.workflow_nodepack_recovery_tasks import (
    WorkflowNodepackRecoveryTasks,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

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


class NodepackRecoveryHandoffPort(Protocol):
    """Keep the splash and old shell alive across installation and GUI reload."""

    def begin(self) -> bool:
        """Hide the shell behind a recovery splash when safe."""

    def report(self, message: ApplicationText) -> None:
        """Publish the current recovery stage."""

    def reload(self) -> bool:
        """Save the session and rebuild the GUI after Comfy verification."""

    def cancel(self) -> None:
        """Return to the preserved shell after a recoverable failure."""


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
        present_review: NodepackReviewPresenter,
        present_failure: RecoveryFailurePresenter,
        can_restart: Callable[[], bool],
        handoff_provider: Callable[[], NodepackRecoveryHandoffPort | None],
        request_restart: Callable[[], bool],
        route_factory: WorkflowNodepackRecoveryRouteFactory,
    ) -> None:
        """Store planning, acquisition, recovery, and owner-thread collaborators."""

        self._plan_service = plan_service
        self._installer = installer
        self._workspace = workspace
        self._python_executable = python_executable
        self._present_review = present_review
        self._present_failure = present_failure
        self._can_restart = can_restart
        self._handoff_provider = handoff_provider
        self._request_restart = request_restart
        self._tasks = WorkflowNodepackRecoveryTasks(route_factory)
        self._pending: dict[str, _PendingRecovery] = {}
        self._reassessment_ids: set[str] = set()
        self._active_handoff: NodepackRecoveryHandoffPort | None = None

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

    def reassess_open_workflow(
        self,
        *,
        workflow: JsonObject,
        target_workflow_id: str,
        refresh_projection: Callable[[WorkflowNodeDefinitionAssessment], None],
    ) -> None:
        """Recheck a visible saved workflow and replace stale node-card state."""

        if (
            self._active_handoff is not None
            or self._pending
            or target_workflow_id in self._reassessment_ids
        ):
            return
        self._reassessment_ids.add(target_workflow_id)
        try:
            self._submit_plan(
                workflow=workflow,
                target_workflow_id=target_workflow_id,
                verification=False,
                refresh_projection=refresh_projection,
            )
        except Exception as error:
            self._reassessment_ids.discard(target_workflow_id)
            log_exception(
                _LOGGER,
                "Could not schedule open workflow nodepack reassessment",
                error=error,
                workflow_id=target_workflow_id,
            )
            self._present_failure(target_workflow_id, "resolve_nodepacks", error)

    def observe_connection(self, change: ComfyConnectionStateChange) -> None:
        """Verify pending workflows after a restart reconnects or report failure."""

        if change.current.phase is ComfyConnectionPhase.RESTART_FAILED:
            for workflow_id in tuple(self._pending):
                self._fail_recovery(
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
            try:
                if self._active_handoff is not None:
                    self._active_handoff.report(
                        app_text("Checking required custom nodes in restarted ComfyUI")
                    )
                self._submit_plan(
                    workflow=pending.workflow,
                    target_workflow_id=workflow_id,
                    verification=True,
                )
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Could not schedule post-restart nodepack verification",
                    error=error,
                    workflow_id=workflow_id,
                )
                self._fail_recovery(workflow_id, "verify_nodepacks", error)

    def close(self) -> None:
        """Release active task scopes during shell teardown."""

        self._tasks.close()
        if self._active_handoff is not None:
            self._active_handoff.cancel()
            self._active_handoff = None
        self._pending.clear()
        self._reassessment_ids.clear()

    def _submit_plan(
        self,
        *,
        workflow: JsonObject,
        target_workflow_id: str,
        verification: bool,
        refresh_projection: Callable[[WorkflowNodeDefinitionAssessment], None]
        | None = None,
    ) -> None:
        """Run live definition assessment and package lookup off the owner thread."""

        active, request_id = self._tasks.begin(target_workflow_id)
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

            self._tasks.finish(active)
            if refresh_projection is not None:
                self._reassessment_ids.discard(target_workflow_id)
            if outcome.status != "succeeded":
                if outcome.status == "failed":
                    stage = "verify_nodepacks" if verification else "resolve_nodepacks"
                    error = outcome.error or RuntimeError(
                        "Workflow nodepack resolution failed."
                    )
                    if verification:
                        self._fail_recovery(target_workflow_id, stage, error)
                    else:
                        self._present_failure(target_workflow_id, stage, error)
                elif verification:
                    self._cancel_recovery(target_workflow_id)
                return
            plan = cast(WorkflowNodepackRecoveryPlan, outcome.result)
            if verification:
                self._finish_verification(target_workflow_id, plan)
                return
            if refresh_projection is not None:
                refresh_projection(plan.assessment)
            if not plan.requires_review:
                return
            if (
                self._workspace is None
                or self._python_executable is None
                or not self._can_restart()
                or self._handoff_provider() is None
            ):
                log_warning(
                    _LOGGER,
                    "Skipped unavailable custom node installation offer",
                    workflow_id=target_workflow_id,
                    missing_node_classes=",".join(plan.assessment.missing_class_types),
                )
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

        self._tasks.submit(active, request, receive)

    def _install(
        self,
        *,
        candidates: tuple[WorkflowNodepackInstallCandidate, ...],
        workflow: JsonObject,
        target_workflow_id: str,
    ) -> None:
        """Install one approved batch behind the recovery splash."""

        if not candidates:
            return
        workspace = self._workspace
        python_executable = self._python_executable
        if workspace is None or python_executable is None:
            log_warning(
                _LOGGER,
                "Skipped approved custom node installation without a local runtime",
                workflow_id=target_workflow_id,
            )
            return
        try:
            handoff = self._handoff_provider()
            prepared = bool(
                self._can_restart() and handoff is not None and handoff.begin()
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Could not prepare approved nodepack installation",
                error=error,
                workflow_id=target_workflow_id,
            )
            prepared = False
            handoff = None
        if not prepared or handoff is None:
            self._present_failure(
                target_workflow_id,
                "prepare_restart",
                WorkflowNodepackRestartUnavailableError(
                    "Cannot safely restart this ComfyUI session and GUI."
                ),
            )
            return
        self._active_handoff = handoff
        try:
            active, request_id = self._tasks.begin(target_workflow_id)
        except Exception as error:
            self._fail_recovery(target_workflow_id, "install_nodepacks", error)
            return
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
                on_progress=lambda progress: active.route.publish(
                    lambda: handoff.report(
                        describe_nodepack_install_progress(progress)
                    ),
                    "workflow_nodepack_install_progress",
                ),
            ),
        )

        def receive(outcome: TaskOutcome[object]) -> None:
            """Request restart after successful source installation settles."""

            self._tasks.finish(active)
            if outcome.status != "succeeded":
                if outcome.status == "failed":
                    self._fail_recovery(
                        target_workflow_id,
                        "install_nodepacks",
                        outcome.error
                        or RuntimeError("Workflow nodepack installation failed."),
                    )
                else:
                    self._cancel_recovery(target_workflow_id)
                return
            result = cast(WorkflowNodepackInstallResult, outcome.result)
            if result.failed:
                log_warning(
                    _LOGGER,
                    "Approved nodepack batch contained installation failures",
                    workflow_id=target_workflow_id,
                    failed_package_count=(
                        len(result.items) - len(result.installed_package_ids)
                    ),
                )
            if not result.installed_package_ids:
                if result.failed:
                    self._fail_recovery(
                        target_workflow_id,
                        "install_nodepacks",
                        WorkflowNodepackInstallIncompleteError(
                            "One or more approved custom node packages could not be installed."
                        ),
                    )
                else:
                    self._cancel_recovery(target_workflow_id)
                return
            self._pending[target_workflow_id] = _PendingRecovery(workflow=workflow)
            handoff.report(
                app_text("Restarting ComfyUI to apply updated dependencies.")
            )
            try:
                restart_accepted = self._request_restart()
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Could not request managed Comfy restart after nodepack install",
                    error=error,
                    workflow_id=target_workflow_id,
                )
                restart_accepted = False
            if not restart_accepted:
                self._fail_recovery(
                    target_workflow_id,
                    "restart",
                    WorkflowNodepackRestartUnavailableError(
                        "Installed custom nodes require a ComfyUI restart."
                    ),
                )

        try:
            self._tasks.submit(active, request, receive)
        except Exception as error:
            self._fail_recovery(target_workflow_id, "install_nodepacks", error)

    def _finish_verification(
        self,
        target_workflow_id: str,
        plan: WorkflowNodepackRecoveryPlan,
    ) -> None:
        """Reload with fresh metadata even when some definitions remain unavailable."""

        if plan.assessment.missing:
            log_warning(
                _LOGGER,
                "Custom node definitions remain unavailable after restart",
                workflow_id=target_workflow_id,
                missing_node_classes=",".join(plan.assessment.missing_class_types),
            )
        self._pending.pop(target_workflow_id, None)
        handoff = self._active_handoff
        try:
            reload_accepted = handoff is not None and handoff.reload()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Could not request GUI reload after nodepack verification",
                error=error,
                workflow_id=target_workflow_id,
            )
            reload_accepted = False
        if not reload_accepted:
            self._fail_recovery(
                target_workflow_id,
                "reload_gui",
                WorkflowNodepackRestartUnavailableError(
                    "Substitute could not reload the GUI after ComfyUI restarted."
                ),
            )
            return
        self._active_handoff = None
        log_info(
            _LOGGER,
            "Assessed nodepacks and requested session-preserving GUI reload",
            workflow_id=target_workflow_id,
            missing_node_classes=",".join(plan.assessment.missing_class_types),
        )

    def _cancel_recovery(self, target_workflow_id: str) -> None:
        """Release the handoff without discarding the visible workflow."""

        self._pending.pop(target_workflow_id, None)
        handoff = self._active_handoff
        self._active_handoff = None
        if handoff is not None:
            handoff.cancel()

    def _fail_recovery(
        self, target_workflow_id: str, stage: str, error: BaseException
    ) -> None:
        """Restore the shell before reporting a recoverable failure."""

        self._cancel_recovery(target_workflow_id)
        self._present_failure(target_workflow_id, stage, error)


__all__ = [
    "DirectWorkflowNodepackRecoveryController",
    "NodepackRecoveryHandoffPort",
    "NodepackReviewPresenter",
    "RecoveryFailurePresenter",
    "WorkflowNodepackInstallIncompleteError",
    "WorkflowNodepackRestartUnavailableError",
]
