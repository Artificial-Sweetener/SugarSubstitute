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

"""Execute onboarding provisioning and adapt progress to the Qt owner thread."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from PySide6.QtCore import QObject, Signal

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingCredentialDraft,
    OnboardingDraftState,
    OnboardingProvisioningFailure,
)
from substitute.application.onboarding.preparation_service import (
    OnboardingPreparationResult,
)
from substitute.application.onboarding.setup_progress import SetupProgressEvent
from substitute.domain.model_recommendations import ModelInstallPlan
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingDraft,
    OnboardingFlowMode,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.onboarding.provisioning_executor")
_ONBOARDING_PROVISIONING_LANE = "onboarding_provisioning"


class OnboardingFlowServiceLike(Protocol):
    """Describe application onboarding behavior used by presentation owners."""

    def load_draft(self, installation_root: Path) -> OnboardingDraftState:
        """Load onboarding draft state for one installation root."""

    def provision(
        self,
        *,
        draft: OnboardingDraftState,
        credential_draft: OnboardingCredentialDraft | None = None,
        restart_required: bool,
        on_status: Callable[[ApplicationText], None],
        on_log: Callable[[ApplicationText], None],
        model_install_plan: ModelInstallPlan | None = None,
        setup_generation: int = 1,
        on_setup_progress: Callable[[SetupProgressEvent], None] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> OnboardingCompletionResult:
        """Provision the selected onboarding draft and return its completion."""


class OnboardingPreparationServiceLike(Protocol):
    """Describe choice-independent background preparation."""

    def prepare(
        self,
        *,
        draft: OnboardingDraftState,
        generation: int,
        on_progress: Callable[[SetupProgressEvent], None],
        on_log: Callable[[ApplicationText], None],
        cancellation: CancellationToken | None = None,
    ) -> OnboardingPreparationResult:
        """Prepare runtime and local ComfyUI files without committing setup."""


class OnboardingOwnerThreadPublisher(Protocol):
    """Publish provisioning callbacks on the onboarding owner's thread."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Queue one reason-tagged callback for owner-thread delivery."""


@dataclass(frozen=True)
class OnboardingProvisioningExecutionRoute:
    """Bundle the task submitter and owner-thread publication route."""

    submitter: TaskSubmitter
    close_submitter: Callable[[], None]
    progress_publisher: OnboardingOwnerThreadPublisher


class OnboardingProvisioningSubmitterFactory(Protocol):
    """Create execution submitters for one onboarding presentation owner."""

    def __call__(self, owner: QObject) -> OnboardingProvisioningExecutionRoute:
        """Return execution and publication routes scoped to the owner."""


@dataclass(frozen=True)
class ProvisioningSelection:
    """Capture the target-specific selection being provisioned."""

    draft: OnboardingDraft
    flow_mode: OnboardingFlowMode
    credential_draft: OnboardingCredentialDraft
    model_install_plan: ModelInstallPlan | None = None


@dataclass(frozen=True)
class _ProgressEvent:
    """Record one provisioning progress publication requested by task work."""

    kind: Literal["status", "log"]
    message: ApplicationText


@dataclass(frozen=True)
class _TaskResult:
    """Carry one completed provisioning outcome to the owner thread."""

    completion: OnboardingCompletion | None
    failure: OnboardingProvisioningFailure | None


class OnboardingProvisioningExecutor(QObject):
    """Own provisioning task lifecycle and owner-thread event adaptation."""

    started = Signal()
    finished = Signal()
    progress_status_changed = Signal(object)
    progress_log_emitted = Signal(object)
    failure_reported = Signal(object)
    completion_ready = Signal(object)
    preparation_progress_changed = Signal(object)
    preparation_finished = Signal(object)

    def __init__(
        self,
        *,
        owner: QObject,
        flow_service: OnboardingFlowServiceLike,
        preparation_service: OnboardingPreparationServiceLike | None = None,
        submitter: TaskSubmitter | None = None,
        close_submitter: Callable[[], None] | None = None,
        progress_publisher: OnboardingOwnerThreadPublisher | None = None,
        submitter_factory: OnboardingProvisioningSubmitterFactory | None = None,
    ) -> None:
        """Resolve and own one scoped provisioning execution route."""

        super().__init__(owner)
        self._flow_service = flow_service
        self._preparation_service = preparation_service
        self._generation = 0
        self._preparation_generation = 0
        self._preparation_active = False
        self._queued_selection: ProvisioningSelection | None = None
        self._shutdown_requested = False
        if submitter is None:
            if close_submitter is not None or progress_publisher is not None:
                raise ValueError("Injected route parts require an injected submitter.")
            if submitter_factory is None:
                raise TypeError(
                    "submitter_factory is required for onboarding provisioning."
                )
            route = submitter_factory(owner)
            submitter = route.submitter
            close_submitter = route.close_submitter
            progress_publisher = route.progress_publisher
        elif submitter_factory is not None:
            raise ValueError("submitter_factory cannot be combined with submitter.")
        elif progress_publisher is None:
            raise TypeError(
                "progress_publisher is required with an injected submitter."
            )
        self._close_submitter = close_submitter
        self._progress_publisher = progress_publisher
        self._preparation_scope = TaskScope(
            submitter=submitter,
            scope_id="onboarding_preparation",
        )
        self._provisioning_scope = TaskScope(
            submitter=submitter,
            scope_id="onboarding_provisioning",
        )

    def start_preparation(self, draft: OnboardingDraft) -> bool:
        """Start or replace choice-independent preparation for one stable draft."""

        service = self._preparation_service
        if service is None or self._shutdown_requested:
            return False
        self._preparation_generation += 1
        generation = self._preparation_generation
        self._preparation_active = True
        self._preparation_scope.cancel_all(reason="preparation_inputs_changed")
        request: TaskRequest[OnboardingPreparationResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=generation,
                domain="onboarding_preparation",
                parts=(("operation_key", "choice_independent"),),
            ),
            context=ExecutionContext(
                operation="onboarding_preparation",
                reason="inputs_stable",
                lane=_ONBOARDING_PROVISIONING_LANE,
                owner_id="onboarding_controller",
                safe_fields=(("generation", generation),),
            ),
            work=lambda token: service.prepare(
                draft=_draft_state(draft),
                generation=generation,
                on_progress=lambda event: self._progress_publisher.publish(
                    lambda: self._deliver_preparation_progress(event),
                    reason="onboarding_preparation_progress",
                ),
                on_log=lambda message: self._progress_publisher.publish(
                    lambda: self.progress_log_emitted.emit(message),
                    reason="onboarding_preparation_log",
                ),
                cancellation=token,
            ),
        )
        handle = self._preparation_scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._deliver_preparation_outcome(generation, outcome),
            reason="onboarding_preparation_completed",
        )
        return True

    def start(self, selection: ProvisioningSelection) -> None:
        """Submit one provisioning selection to the dedicated execution lane."""

        if self._shutdown_requested:
            return
        if self._preparation_active:
            self._queued_selection = selection
            return
        self._submit_final(selection)

    def _submit_final(self, selection: ProvisioningSelection) -> None:
        """Submit final provisioning after background preparation reaches a barrier."""

        self._generation += 1
        request_id = self._generation
        self.started.emit()
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="onboarding",
                parts=(("operation_key", "provisioning"),),
            ),
            context=ExecutionContext(
                operation="onboarding_provisioning",
                reason="user_requested",
                lane=_ONBOARDING_PROVISIONING_LANE,
                owner_id="onboarding_controller",
                safe_fields=(
                    ("operation_key", "provisioning"),
                    ("generation", request_id),
                ),
            ),
            work=lambda token: self._run(selection, request_id, token),
        )
        handle = self._provisioning_scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._deliver_outcome(request_id, outcome),
            reason="onboarding_provisioning_completed",
        )

    def _deliver_preparation_progress(self, event: SetupProgressEvent) -> None:
        """Reject stale preparation progress before publishing it to presentation."""

        if self._shutdown_requested or event.generation != self._preparation_generation:
            return
        self.preparation_progress_changed.emit(event)

    def _deliver_setup_progress(self, event: SetupProgressEvent) -> None:
        """Publish only progress from the current final setup generation."""

        if self._shutdown_requested or event.generation != self._generation:
            return
        self.preparation_progress_changed.emit(event)

    def _deliver_preparation_outcome(
        self,
        generation: int,
        outcome: TaskOutcome[OnboardingPreparationResult],
    ) -> None:
        """Release the preparation barrier and route queued final work."""

        if self._shutdown_requested or generation != self._preparation_generation:
            return
        self._preparation_active = False
        if outcome.cancelled:
            return
        if outcome.error is not None:
            self._queued_selection = None
            self.failure_reported.emit(_generic_failure(outcome.error))
            return
        result = outcome.result
        if result is not None:
            self.preparation_finished.emit(result)
        selection, self._queued_selection = self._queued_selection, None
        if selection is not None:
            self._submit_final(selection)

    def shutdown(self) -> None:
        """Cancel provisioning work and release the owned execution lane."""

        self._shutdown_requested = True
        self._preparation_scope.close(reason="onboarding_controller_shutdown")
        self._provisioning_scope.close(reason="onboarding_controller_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _run(
        self,
        selection: ProvisioningSelection,
        request_id: int,
        cancellation: CancellationToken,
    ) -> _TaskResult:
        """Run provisioning and stream progress through the owner-thread route."""

        try:
            result = self._flow_service.provision(
                draft=_draft_state(selection.draft),
                credential_draft=selection.credential_draft,
                restart_required=(
                    selection.flow_mode is OnboardingFlowMode.RECONFIGURE
                ),
                on_status=lambda message: self._request_progress(
                    request_id, "status", message
                ),
                on_log=lambda message: self._request_progress(
                    request_id, "log", message
                ),
                model_install_plan=selection.model_install_plan,
                setup_generation=request_id,
                on_setup_progress=lambda event: self._progress_publisher.publish(
                    lambda: self._deliver_setup_progress(event),
                    reason="onboarding_setup_progress",
                ),
                cancellation=cancellation,
            )
            return _TaskResult(
                completion=OnboardingCompletion(
                    context=result.context,
                    restart_required=result.restart_required,
                    launch_command=result.launch_command,
                ),
                failure=None,
            )
        except Exception as error:
            log_exception(_LOGGER, "Onboarding provisioning failed", error=error)
            failure = (
                error
                if isinstance(error, OnboardingProvisioningFailure)
                else _generic_failure(error)
            )
            return _TaskResult(completion=None, failure=failure)

    def _request_progress(
        self,
        request_id: int,
        kind: Literal["status", "log"],
        message: ApplicationText,
    ) -> None:
        """Queue one background progress event for owner-thread delivery."""

        event = _ProgressEvent(kind, message)
        self._progress_publisher.publish(
            lambda: self._deliver_progress(request_id, event),
            reason=f"onboarding_provisioning_{kind}",
        )

    def _deliver_progress(self, request_id: int, event: _ProgressEvent) -> None:
        """Publish current provisioning progress from the owner thread."""

        if self._shutdown_requested or request_id != self._generation:
            return
        if event.kind == "status":
            self.progress_status_changed.emit(event.message)
        else:
            self.progress_log_emitted.emit(event.message)

    def _deliver_outcome(
        self,
        request_id: int,
        outcome: TaskOutcome[_TaskResult],
    ) -> None:
        """Publish a provisioning task outcome on the owner thread."""

        if self._shutdown_requested or request_id != self._generation:
            return
        if outcome.cancelled:
            return
        result = outcome.result
        if outcome.error is not None:
            result = _TaskResult(None, _generic_failure(outcome.error))
        if result is None:
            result = _TaskResult(
                None,
                _generic_failure(
                    RuntimeError("Onboarding provisioning produced no outcome.")
                ),
            )
        if result.completion is not None:
            self.completion_ready.emit(result.completion)
        elif result.failure is not None:
            self.failure_reported.emit(result.failure)
        self.finished.emit()


def _generic_failure(error: BaseException) -> OnboardingProvisioningFailure:
    """Return a user-facing provisioning failure for unexpected errors."""

    return OnboardingProvisioningFailure(
        headline=app_text("Substitute ran into a setup problem"),
        user_message=app_text(
            "Review the details below, fix the reported issue, and try again."
        ),
        technical_detail=str(error).strip() or type(error).__name__,
        remediation_steps=(),
    )


def _draft_state(draft: OnboardingDraft) -> OnboardingDraftState:
    """Translate presentation draft state into application flow input."""

    return OnboardingDraftState(
        installation_root=draft.installation_root,
        target_mode=draft.target_mode.value,
        endpoint_host=draft.endpoint_host,
        endpoint_port=draft.endpoint_port,
        managed_workspace_path=draft.managed_workspace_path,
        attached_workspace_path=draft.attached_workspace_path,
        attached_python_binding=draft.attached_python_binding,
        managed_model_root=draft.managed_model_root,
        managed_model_root_uses_default=draft.managed_model_root_uses_default,
        output_root=draft.output_root,
        output_root_uses_default=draft.output_root_uses_default,
        danbooru_tag_help_enabled=draft.danbooru_tag_help_enabled,
        danbooru_safe_previews_enabled=draft.danbooru_safe_previews_enabled,
        danbooru_image_rating_policy=draft.danbooru_image_rating_policy,
        civitai_model_help_enabled=draft.civitai_model_help_enabled,
        civitai_downloads_enabled=draft.civitai_downloads_enabled,
        civitai_safe_thumbnails_enabled=draft.civitai_safe_thumbnails_enabled,
        civitai_thumbnail_safety_policy=draft.civitai_thumbnail_safety_policy,
        civitai_api_key_configured=draft.civitai_api_key_configured,
        detected_platform=draft.detected_platform,
        detected_accelerator=draft.detected_accelerator,
        selected_install_target=draft.selected_install_target,
        selected_python_version=draft.selected_python_version,
        selected_comfy_channel=draft.selected_comfy_channel,
        selected_backend_policy=draft.selected_backend_policy,
        selected_torch_channel=draft.selected_torch_channel,
        selected_torch_reason=draft.selected_torch_reason,
        selected_stability=draft.selected_stability,
        force_cpu_mode=draft.force_cpu_mode,
        prefer_edge_torch=draft.prefer_edge_torch,
        prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
    )


__all__ = [
    "OnboardingFlowServiceLike",
    "OnboardingOwnerThreadPublisher",
    "OnboardingPreparationServiceLike",
    "OnboardingProvisioningExecutionRoute",
    "OnboardingProvisioningExecutor",
    "OnboardingProvisioningSubmitterFactory",
    "ProvisioningSelection",
]
