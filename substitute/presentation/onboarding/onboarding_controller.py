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

"""Coordinate onboarding UI state, page flow, and background provisioning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol

from PySide6.QtCore import QObject, Signal

from substitute.application.execution import (
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
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.onboarding.controller")
_ONBOARDING_PROVISIONING_LANE = "onboarding_provisioning"


class ReadinessAssessmentLike(Protocol):
    """Describe readiness data consumed by the onboarding presentation layer."""

    @property
    def issues(self) -> tuple["ReadinessIssueLike", ...]:
        """Return the readiness issues shown in the onboarding banner."""


class ReadinessIssueLike(Protocol):
    """Describe one readiness issue rendered in onboarding UI."""

    @property
    def code(self) -> object:
        """Return the stable readiness issue code."""

    @property
    def detail(self) -> str:
        """Return the technical readiness detail for one issue."""

    @property
    def summary(self) -> str:
        """Return the end-user summary line for one readiness issue."""


class OnboardingFlowServiceLike(Protocol):
    """Describe the application onboarding flow behavior used by the controller."""

    def load_draft(self, installation_root: Path) -> OnboardingDraftState:
        """Load onboarding draft state for one installation root."""

    def provision(
        self,
        *,
        draft: OnboardingDraftState,
        credential_draft: OnboardingCredentialDraft | None = None,
        restart_required: bool,
        on_status: Callable[[str], None],
        on_log: Callable[[str], None],
    ) -> OnboardingCompletionResult:
        """Provision the selected onboarding draft and return its completion."""


class OnboardingOwnerThreadPublisher(Protocol):
    """Publish provisioning callbacks on the onboarding controller's thread."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Queue one reason-tagged callback for owner-thread delivery."""


@dataclass(frozen=True)
class OnboardingProvisioningExecutionRoute:
    """Bundle the task submitter and owner-thread publication route."""

    submitter: TaskSubmitter
    close_submitter: Callable[[], None]
    progress_publisher: OnboardingOwnerThreadPublisher


class OnboardingProvisioningSubmitterFactory(Protocol):
    """Create execution submitters for one onboarding controller owner."""

    def __call__(self, owner: QObject) -> OnboardingProvisioningExecutionRoute:
        """Return the execution and publication routes scoped to the owner."""


@dataclass(frozen=True)
class ProvisioningSelection:
    """Capture the target-specific selection being provisioned."""

    draft: OnboardingDraft
    flow_mode: OnboardingFlowMode
    credential_draft: OnboardingCredentialDraft


@dataclass(frozen=True)
class _OnboardingProvisioningProgressEvent:
    """Record one provisioning progress publication requested by task work."""

    kind: Literal["status", "log"]
    message: str


@dataclass(frozen=True)
class _OnboardingProvisioningTaskResult:
    """Carry one completed provisioning outcome to the owner thread."""

    completion: OnboardingCompletion | None
    failure: OnboardingProvisioningFailure | None


@dataclass(frozen=True)
class ReadinessIssuePresentation:
    """Describe the user-facing wording for one readiness issue."""

    headline: str
    user_message: str
    technical_detail: str


def _generic_provisioning_failure(
    error: BaseException,
) -> OnboardingProvisioningFailure:
    """Return a user-facing provisioning failure for unexpected errors."""

    return OnboardingProvisioningFailure(
        headline="Substitute ran into a setup problem",
        user_message="Review the details below, fix the reported issue, and try again.",
        technical_detail=str(error).strip() or type(error).__name__,
        remediation_steps=(),
    )


class OnboardingController(QObject):
    """Drive onboarding flow state, provisioning execution, and completion signals."""

    draft_changed = Signal(object)
    provisioning_started = Signal()
    provisioning_finished = Signal()
    progress_status_changed = Signal(str)
    progress_log_emitted = Signal(str)
    failure_reported = Signal(object)
    completion_ready = Signal(object)

    def __init__(
        self,
        *,
        initial_install_root: Path,
        flow_mode: OnboardingFlowMode,
        readiness_assessment: ReadinessAssessmentLike,
        flow_service: OnboardingFlowServiceLike,
        submitter: TaskSubmitter | None = None,
        close_submitter: Callable[[], None] | None = None,
        progress_publisher: OnboardingOwnerThreadPublisher | None = None,
        submitter_factory: OnboardingProvisioningSubmitterFactory | None = None,
    ) -> None:
        """Store onboarding inputs and load the current draft state."""

        super().__init__()
        self._flow_mode = flow_mode
        self._readiness_assessment = readiness_assessment
        self._flow_service = flow_service
        self._draft = self._build_initial_draft(initial_install_root)
        self._credential_draft = OnboardingCredentialDraft()
        self._completion: OnboardingCompletion | None = None
        self._provisioning_generation = 0
        self._shutdown_requested = False
        if submitter is None:
            if close_submitter is not None:
                raise ValueError("close_submitter requires an injected submitter.")
            if progress_publisher is not None:
                raise ValueError("progress_publisher requires an injected submitter.")
            if submitter_factory is None:
                raise TypeError(
                    "submitter_factory is required for onboarding provisioning."
                )
            execution_route = submitter_factory(self)
            submitter = execution_route.submitter
            close_submitter = execution_route.close_submitter
            progress_publisher = execution_route.progress_publisher
        elif submitter_factory is not None:
            raise ValueError("submitter_factory cannot be combined with submitter.")
        elif progress_publisher is None:
            raise TypeError(
                "progress_publisher is required with an injected submitter."
            )
        self._close_submitter = close_submitter
        self._progress_publisher = progress_publisher
        self._provisioning_scope = TaskScope(
            submitter=submitter,
            scope_id="onboarding_controller",
        )
        self.destroyed.connect(lambda _obj=None: self.shutdown())

    @property
    def flow_mode(self) -> OnboardingFlowMode:
        """Return the active onboarding entry mode."""

        return self._flow_mode

    @property
    def readiness_assessment(self) -> ReadinessAssessmentLike:
        """Return the readiness assessment that launched onboarding."""

        return self._readiness_assessment

    @property
    def draft(self) -> OnboardingDraft:
        """Return the current onboarding draft."""

        return self._draft

    @property
    def completion(self) -> OnboardingCompletion | None:
        """Return the last successful completion result when available."""

        return self._completion

    def present_readiness_issues(self) -> tuple[ReadinessIssuePresentation, ...]:
        """Translate readiness issues into user-facing repair copy."""

        return tuple(
            self._presentation_for_issue(issue)
            for issue in self._readiness_assessment.issues
        )

    def set_installation_root(self, installation_root: Path) -> None:
        """Update the selected installation root and reload draft defaults."""

        self._draft = self._build_initial_draft(installation_root)
        self.draft_changed.emit(self._draft)

    def update_target_mode(self, target_mode: OnboardingTargetMode) -> None:
        """Update the selected target mode inside the draft."""

        self._draft = replace(self._draft, target_mode=target_mode)
        self.draft_changed.emit(self._draft)

    def update_endpoint(self, host: str, port: int) -> None:
        """Update the endpoint host and port inside the draft."""

        self._draft = replace(
            self._draft,
            endpoint_host=host.strip(),
            endpoint_port=port,
        )
        self.draft_changed.emit(self._draft)

    def update_managed_workspace(self, workspace_path: Path) -> None:
        """Update the managed-local workspace path inside the draft."""

        managed_model_root = self._draft.managed_model_root
        if self._draft.managed_model_root_uses_default:
            managed_model_root = workspace_path / "models"
        self._draft = replace(
            self._draft,
            managed_workspace_path=workspace_path,
            managed_model_root=managed_model_root,
        )
        self.draft_changed.emit(self._draft)

    def update_attached_workspace(self, workspace_path: Path | None) -> None:
        """Update the existing local ComfyUI workspace path inside the draft."""

        self._draft = replace(self._draft, attached_workspace_path=workspace_path)
        self.draft_changed.emit(self._draft)

    def update_managed_runtime_preferences(
        self,
        *,
        force_cpu_mode: bool,
        prefer_edge_torch: bool,
        prefer_edge_comfy_channel: bool,
    ) -> None:
        """Update the managed runtime preference flags inside the draft."""

        self._draft = replace(
            self._draft,
            force_cpu_mode=force_cpu_mode,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy_channel=prefer_edge_comfy_channel,
        )
        self.draft_changed.emit(self._draft)

    def update_folder_preferences(
        self,
        *,
        managed_model_root: Path | None,
        managed_model_root_uses_default: bool,
        output_root: Path | None,
        output_root_uses_default: bool,
    ) -> None:
        """Update selected folder preferences inside the draft."""

        self._draft = replace(
            self._draft,
            managed_model_root=managed_model_root,
            managed_model_root_uses_default=managed_model_root_uses_default,
            output_root=output_root,
            output_root_uses_default=output_root_uses_default,
        )
        self.draft_changed.emit(self._draft)

    def update_integration_preferences(
        self,
        *,
        danbooru_tag_help_enabled: bool,
        danbooru_safe_previews_enabled: bool,
        danbooru_image_rating_policy: str,
        civitai_model_help_enabled: bool,
        civitai_downloads_enabled: bool,
        civitai_safe_thumbnails_enabled: bool,
        civitai_thumbnail_safety_policy: str,
        civitai_api_key: str = "",
    ) -> None:
        """Update helper integration preferences and in-memory credentials."""

        self._draft = replace(
            self._draft,
            danbooru_tag_help_enabled=danbooru_tag_help_enabled,
            danbooru_safe_previews_enabled=danbooru_safe_previews_enabled,
            danbooru_image_rating_policy=danbooru_image_rating_policy,
            civitai_model_help_enabled=civitai_model_help_enabled,
            civitai_downloads_enabled=civitai_downloads_enabled,
            civitai_safe_thumbnails_enabled=civitai_safe_thumbnails_enabled,
            civitai_thumbnail_safety_policy=civitai_thumbnail_safety_policy,
        )
        self._credential_draft = OnboardingCredentialDraft(
            civitai_api_key=civitai_api_key
        )
        self.draft_changed.emit(self._draft)

    def next_page(self, current_page: OnboardingPageId) -> OnboardingPageId:
        """Return the next page in the flow for the current target selection."""

        if current_page is OnboardingPageId.WELCOME:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.TARGET_MODE:
            return self._target_page(self._draft.target_mode)
        if current_page in {
            OnboardingPageId.MANAGED_LOCAL,
            OnboardingPageId.ATTACHED_LOCAL,
            OnboardingPageId.REMOTE,
        }:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.FOLDERS:
            return OnboardingPageId.INTEGRATIONS
        if current_page is OnboardingPageId.INTEGRATIONS:
            return OnboardingPageId.PROVISIONING
        if (
            current_page is OnboardingPageId.PROVISIONING
            and self._completion is not None
        ):
            return OnboardingPageId.COMPLETION
        return current_page

    def previous_page(self, current_page: OnboardingPageId) -> OnboardingPageId:
        """Return the previous page in the flow for the current target selection."""

        if current_page is OnboardingPageId.TARGET_MODE:
            return OnboardingPageId.WELCOME
        if current_page in {
            OnboardingPageId.MANAGED_LOCAL,
            OnboardingPageId.ATTACHED_LOCAL,
            OnboardingPageId.REMOTE,
        }:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.FOLDERS:
            return self._target_page(self._draft.target_mode)
        if current_page is OnboardingPageId.INTEGRATIONS:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.PROVISIONING:
            return OnboardingPageId.INTEGRATIONS
        if current_page is OnboardingPageId.COMPLETION:
            return OnboardingPageId.PROVISIONING
        return current_page

    def start_provisioning(self) -> None:
        """Provision the selected runtime and Comfy target through execution."""

        if self._shutdown_requested:
            return
        selection = ProvisioningSelection(
            self._draft,
            self._flow_mode,
            self._credential_draft,
        )
        self._completion = None
        self._provisioning_generation += 1
        request_id = self._provisioning_generation
        self.provisioning_started.emit()
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
            work=lambda _token: self._run_provisioning(selection, request_id),
        )
        handle = self._provisioning_scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._deliver_provisioning_outcome(
                request_id=request_id,
                outcome=outcome,
            ),
            reason="onboarding_provisioning_completed",
        )

    def shutdown(self) -> None:
        """Cancel provisioning work and release the owned execution lane."""

        self._shutdown_requested = True
        self._provisioning_scope.close(reason="onboarding_controller_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _build_initial_draft(self, installation_root: Path) -> OnboardingDraft:
        """Build the current onboarding draft from persisted state or defaults."""

        draft = self._flow_service.load_draft(installation_root)
        return OnboardingDraft(
            installation_root=draft.installation_root,
            target_mode=OnboardingTargetMode(draft.target_mode),
            endpoint_host=draft.endpoint_host,
            endpoint_port=draft.endpoint_port,
            managed_workspace_path=draft.managed_workspace_path,
            attached_workspace_path=draft.attached_workspace_path,
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

    def _run_provisioning(
        self,
        selection: ProvisioningSelection,
        request_id: int,
    ) -> _OnboardingProvisioningTaskResult:
        """Run provisioning and stream progress through the owner-thread route."""

        try:
            result = self._flow_service.provision(
                draft=self._draft_state(selection.draft),
                credential_draft=selection.credential_draft,
                restart_required=(
                    selection.flow_mode is OnboardingFlowMode.RECONFIGURE
                ),
                on_status=lambda message: self._request_progress_publication(
                    request_id=request_id,
                    kind="status",
                    message=message,
                ),
                on_log=lambda message: self._request_progress_publication(
                    request_id=request_id,
                    kind="log",
                    message=message,
                ),
            )
            return _OnboardingProvisioningTaskResult(
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
                else _generic_provisioning_failure(error)
            )
            return _OnboardingProvisioningTaskResult(
                completion=None,
                failure=failure,
            )

    def _request_progress_publication(
        self,
        *,
        request_id: int,
        kind: Literal["status", "log"],
        message: str,
    ) -> None:
        """Queue one background progress event for controller-thread delivery."""

        event = _OnboardingProvisioningProgressEvent(kind=kind, message=message)
        self._progress_publisher.publish(
            lambda: self._deliver_provisioning_progress(
                request_id=request_id,
                event=event,
            ),
            reason=f"onboarding_provisioning_{kind}",
        )

    def _deliver_provisioning_progress(
        self,
        *,
        request_id: int,
        event: _OnboardingProvisioningProgressEvent,
    ) -> None:
        """Publish current provisioning progress from the controller thread."""

        if self._shutdown_requested or request_id != self._provisioning_generation:
            return
        if event.kind == "status":
            self.progress_status_changed.emit(event.message)
            return
        self.progress_log_emitted.emit(event.message)

    def _deliver_provisioning_outcome(
        self,
        *,
        request_id: int,
        outcome: TaskOutcome[_OnboardingProvisioningTaskResult],
    ) -> None:
        """Publish a provisioning task outcome on the controller owner thread."""

        if self._shutdown_requested or request_id != self._provisioning_generation:
            return
        if outcome.cancelled:
            return
        result = outcome.result
        if outcome.error is not None:
            result = _OnboardingProvisioningTaskResult(
                completion=None,
                failure=_generic_provisioning_failure(outcome.error),
            )
        if result is None:
            result = _OnboardingProvisioningTaskResult(
                completion=None,
                failure=_generic_provisioning_failure(
                    RuntimeError("Onboarding provisioning produced no outcome.")
                ),
            )
        if result.completion is not None:
            self._completion = result.completion
            self.completion_ready.emit(result.completion)
        elif result.failure is not None:
            self.failure_reported.emit(result.failure)
        self._credential_draft = OnboardingCredentialDraft()
        self.provisioning_finished.emit()

    @staticmethod
    def _draft_state(draft: OnboardingDraft) -> OnboardingDraftState:
        """Translate presentation draft state into application flow input."""

        return OnboardingDraftState(
            installation_root=draft.installation_root,
            target_mode=draft.target_mode.value,
            endpoint_host=draft.endpoint_host,
            endpoint_port=draft.endpoint_port,
            managed_workspace_path=draft.managed_workspace_path,
            attached_workspace_path=draft.attached_workspace_path,
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

    @staticmethod
    def _target_page(target_mode: OnboardingTargetMode) -> OnboardingPageId:
        """Map one target mode to its dedicated options page."""

        if target_mode is OnboardingTargetMode.ATTACHED_LOCAL:
            return OnboardingPageId.ATTACHED_LOCAL
        if target_mode is OnboardingTargetMode.REMOTE:
            return OnboardingPageId.REMOTE
        return OnboardingPageId.MANAGED_LOCAL

    @staticmethod
    def _presentation_for_issue(
        issue: ReadinessIssueLike,
    ) -> ReadinessIssuePresentation:
        """Return user-facing repair wording for one readiness issue."""

        presentations = {
            "installation_config_missing": ReadinessIssuePresentation(
                headline="Substitute still needs a home folder",
                user_message=(
                    "Finish setup so Substitute knows where to keep its files."
                ),
                technical_detail="Installation configuration has not been saved yet.",
            ),
            "installation_config_invalid": ReadinessIssuePresentation(
                headline="Substitute's saved folder settings need to be fixed",
                user_message=(
                    "The stored folder locations no longer match this installation."
                ),
                technical_detail=issue.detail,
            ),
            "runtime_config_missing": ReadinessIssuePresentation(
                headline="Substitute still needs its local runtime",
                user_message=(
                    "Continue setup so Substitute can prepare the local Python files it needs to run."
                ),
                technical_detail="Runtime configuration has not been created yet.",
            ),
            "runtime_config_invalid": ReadinessIssuePresentation(
                headline="Substitute's local runtime settings need repair",
                user_message=(
                    "Some saved runtime paths no longer line up with this installation."
                ),
                technical_detail=issue.detail,
            ),
            "runtime_not_provisioned": ReadinessIssuePresentation(
                headline="Substitute is not fully prepared yet",
                user_message=(
                    "The local runtime has not been set up yet, so the app cannot open normally."
                ),
                technical_detail="The local runtime has not been provisioned.",
            ),
            "runtime_provisioning_incomplete": ReadinessIssuePresentation(
                headline="Substitute's local setup was interrupted",
                user_message=(
                    "Finish repairing the local runtime before opening the app."
                ),
                technical_detail=issue.detail,
            ),
            "runtime_python_missing": ReadinessIssuePresentation(
                headline="Local setup is incomplete",
                user_message="A required local Python file is missing.",
                technical_detail="Missing runtime Python executable.",
            ),
            "target_config_missing": ReadinessIssuePresentation(
                headline="Substitute still needs a ComfyUI connection",
                user_message=(
                    "Choose whether Substitute should set up ComfyUI, use an existing copy, or connect to another machine."
                ),
                technical_detail="ComfyUI target configuration has not been saved yet.",
            ),
            "target_config_invalid": ReadinessIssuePresentation(
                headline="The saved ComfyUI connection needs to be fixed",
                user_message=(
                    "Some required connection details are missing or no longer valid."
                ),
                technical_detail=issue.detail,
            ),
            "managed_workspace_not_configured": ReadinessIssuePresentation(
                headline="Substitute needs a ComfyUI folder to finish setup",
                user_message=(
                    "Choose where Substitute should place the managed ComfyUI files."
                ),
                technical_detail="Managed local mode is missing its ComfyUI folder path.",
            ),
            "managed_workspace_not_installed": ReadinessIssuePresentation(
                headline="ComfyUI still needs to be installed",
                user_message=(
                    "The managed ComfyUI setup is not ready yet. Continue repair to install it."
                ),
                technical_detail="Managed ComfyUI workspace is not installed.",
            ),
            "managed_workspace_not_launchable": ReadinessIssuePresentation(
                headline="ComfyUI needs repair before it can start",
                user_message=(
                    "The managed ComfyUI files are present, but the setup is not ready to launch."
                ),
                technical_detail="Managed ComfyUI workspace is not launchable.",
            ),
            "managed_workspace_not_validated": ReadinessIssuePresentation(
                headline="ComfyUI still needs hardware validation",
                user_message=(
                    "Substitute has not finished validating the managed backend for this machine yet."
                ),
                technical_detail=issue.detail,
            ),
            "managed_workspace_foreign_listener_blocked": ReadinessIssuePresentation(
                headline="Another process is already using the saved ComfyUI address",
                user_message=(
                    "Substitute will not start over a different app that is already listening on the managed port."
                ),
                technical_detail=issue.detail,
            ),
            "managed_workspace_backend_invalid": ReadinessIssuePresentation(
                headline="The managed ComfyUI backend does not match this hardware",
                user_message=(
                    "Repair will re-install ComfyUI with a backend that matches the detected accelerator."
                ),
                technical_detail=issue.detail,
            ),
            "attached_workspace_missing": ReadinessIssuePresentation(
                headline="The saved ComfyUI folder couldn't be found",
                user_message=(
                    "Check that the local ComfyUI folder still exists, then choose the folder that contains ComfyUI's main.py file."
                ),
                technical_detail=issue.detail,
            ),
            "target_endpoint_invalid": ReadinessIssuePresentation(
                headline="The saved ComfyUI address needs to be fixed",
                user_message=(
                    "Review the host and port so Substitute knows where to find ComfyUI."
                ),
                technical_detail=issue.detail,
            ),
            "target_endpoint_unreachable": ReadinessIssuePresentation(
                headline="Substitute couldn't reach the saved ComfyUI address",
                user_message=(
                    "Make sure ComfyUI is running at the saved address, then try again."
                ),
                technical_detail=issue.detail,
            ),
            "backend_compatibility_failed": ReadinessIssuePresentation(
                headline="The saved ComfyUI runtime needs an extension update",
                user_message=(
                    "Repair the target so Substitute BackEnd and SugarCubes match this version of Substitute."
                ),
                technical_detail=issue.detail,
            ),
            "setup_transaction_interrupted": ReadinessIssuePresentation(
                headline="Setup was interrupted",
                user_message=(
                    "Continue setup to finish validating the selected ComfyUI runtime."
                ),
                technical_detail=issue.detail,
            ),
            "setup_transaction_failed": ReadinessIssuePresentation(
                headline="Setup did not finish",
                user_message=(
                    "Review the setup details below, fix the reported issue, and try again."
                ),
                technical_detail=issue.detail,
            ),
            "setup_transaction_corrupt": ReadinessIssuePresentation(
                headline="Setup state could not be read",
                user_message=(
                    "Start setup again so Substitute can save a clean setup state."
                ),
                technical_detail=issue.detail,
            ),
        }
        return presentations.get(
            getattr(issue, "code").value,
            ReadinessIssuePresentation(
                headline="Substitute found a setup problem",
                user_message=(
                    "Review the details below and continue through repair to finish setting things up."
                ),
                technical_detail=issue.detail,
            ),
        )
