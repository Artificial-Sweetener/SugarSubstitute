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
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from substitute.application.onboarding import OnboardingCredentialDraft
from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.model_onboarding_session import (
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.provisioning_executor import (
    OnboardingFlowServiceLike,
    OnboardingOwnerThreadPublisher,
    OnboardingPreparationServiceLike,
    OnboardingProvisioningExecutor,
    OnboardingProvisioningSubmitterFactory,
    ProvisioningSelection,
)
from substitute.presentation.onboarding.readiness_issue_presenter import (
    ReadinessIssueLike,
    ReadinessIssuePresentation,
    present_readiness_issue,
)
from substitute.application.execution import TaskSubmitter


class ReadinessAssessmentLike(Protocol):
    """Describe readiness data consumed by the onboarding presentation layer."""

    @property
    def issues(self) -> tuple["ReadinessIssueLike", ...]:
        """Return the readiness issues shown in the onboarding banner."""


class OnboardingController(QObject):
    """Drive onboarding flow state, provisioning execution, and completion signals."""

    draft_changed = Signal(object)
    provisioning_started = Signal()
    provisioning_finished = Signal()
    progress_status_changed = Signal(object)
    progress_log_emitted = Signal(object)
    setup_progress_changed = Signal(object)
    background_preparation_finished = Signal(object)
    failure_reported = Signal(object)
    completion_ready = Signal(object)

    def __init__(
        self,
        *,
        initial_install_root: Path,
        flow_mode: OnboardingFlowMode,
        readiness_assessment: ReadinessAssessmentLike,
        flow_service: OnboardingFlowServiceLike,
        preparation_service: OnboardingPreparationServiceLike | None = None,
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
        self._model_session = ModelOnboardingSession(
            flow_mode=flow_mode,
            target_mode=self._draft.target_mode,
        )
        self._provisioning_executor = OnboardingProvisioningExecutor(
            owner=self,
            flow_service=flow_service,
            preparation_service=preparation_service,
            submitter=submitter,
            close_submitter=close_submitter,
            progress_publisher=progress_publisher,
            submitter_factory=submitter_factory,
        )
        self._provisioning_executor.started.connect(self.provisioning_started)
        self._provisioning_executor.progress_status_changed.connect(
            self.progress_status_changed
        )
        self._provisioning_executor.progress_log_emitted.connect(
            self.progress_log_emitted
        )
        self._provisioning_executor.preparation_progress_changed.connect(
            self.setup_progress_changed
        )
        self._provisioning_executor.preparation_finished.connect(
            self.background_preparation_finished
        )
        self._provisioning_executor.failure_reported.connect(self.failure_reported)
        self._provisioning_executor.completion_ready.connect(self._accept_completion)
        self._provisioning_executor.finished.connect(self._finish_provisioning)
        self.destroyed.connect(self.shutdown)

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

    @property
    def model_session(self) -> ModelOnboardingSession:
        """Return the authoritative model-onboarding session."""

        return self._model_session

    def present_readiness_issues(self) -> tuple[ReadinessIssuePresentation, ...]:
        """Translate readiness issues into user-facing repair copy."""

        return tuple(
            present_readiness_issue(issue)
            for issue in self._readiness_assessment.issues
        )

    def set_installation_root(self, installation_root: Path) -> None:
        """Update the selected installation root and reload draft defaults."""

        self._draft = self._build_initial_draft(installation_root)
        self.draft_changed.emit(self._draft)

    def update_target_mode(self, target_mode: OnboardingTargetMode) -> None:
        """Update the selected target mode inside the draft."""

        self._draft = replace(self._draft, target_mode=target_mode)
        self._model_session.set_target_mode(target_mode)
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

        model_root = self._draft.managed_model_root
        if self._draft.managed_model_root_uses_default and workspace_path is not None:
            model_root = workspace_path / "models"
        self._draft = replace(
            self._draft,
            attached_workspace_path=workspace_path,
            attached_python_binding=None,
            managed_model_root=model_root,
        )
        self.draft_changed.emit(self._draft)

    def update_attached_python_binding(
        self,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Update the one verified Python binding for an attached ComfyUI setup."""

        self._draft = replace(
            self._draft,
            attached_python_binding=binding,
        )
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
        if current_page is OnboardingPageId.COMFY_PREFLIGHT:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.TARGET_MODE:
            return self._target_page(self._draft.target_mode)
        if current_page in {
            OnboardingPageId.MANAGED_LOCAL,
            OnboardingPageId.ATTACHED_LOCAL,
            OnboardingPageId.ATTACHED_PYTHON_CHOICE,
            OnboardingPageId.ATTACHED_PYTHON_PROCESS,
            OnboardingPageId.ATTACHED_PYTHON_MANUAL,
            OnboardingPageId.REMOTE,
        }:
            if self._model_session.enabled:
                return OnboardingPageId.EXISTING_MODELS
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.EXISTING_MODELS:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.FOLDERS:
            if self._model_session.enabled:
                if self._model_session.state.recommendation_pages:
                    return OnboardingPageId.MODEL_RECOMMENDATIONS
            return OnboardingPageId.INTEGRATIONS
        if current_page is OnboardingPageId.MODEL_RECOMMENDATIONS:
            if self._model_session.state.recommendation_page_index + 1 < len(
                self._model_session.state.recommendation_pages
            ):
                return OnboardingPageId.MODEL_RECOMMENDATIONS
            return OnboardingPageId.MODEL_DOWNLOAD_REVIEW
        if current_page is OnboardingPageId.MODEL_DOWNLOAD_REVIEW:
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
        if current_page is OnboardingPageId.COMFY_PREFLIGHT:
            return OnboardingPageId.WELCOME
        if current_page in {
            OnboardingPageId.MANAGED_LOCAL,
            OnboardingPageId.ATTACHED_LOCAL,
            OnboardingPageId.REMOTE,
        }:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.ATTACHED_PYTHON_CHOICE:
            return OnboardingPageId.ATTACHED_LOCAL
        if current_page in {
            OnboardingPageId.ATTACHED_PYTHON_PROCESS,
            OnboardingPageId.ATTACHED_PYTHON_MANUAL,
        }:
            return OnboardingPageId.ATTACHED_PYTHON_CHOICE
        if current_page in {
            OnboardingPageId.EXISTING_MODELS,
            OnboardingPageId.FOLDERS,
        }:
            if current_page is OnboardingPageId.FOLDERS and self._model_session.enabled:
                return OnboardingPageId.EXISTING_MODELS
            binding = self._draft.attached_python_binding
            if (
                self._draft.target_mode is OnboardingTargetMode.ATTACHED_LOCAL
                and binding is not None
                and binding.source
                in {
                    ComfyPythonSelectionSource.RUNNING_COMFY,
                    ComfyPythonSelectionSource.USER_SELECTED,
                }
            ):
                if binding.source is ComfyPythonSelectionSource.RUNNING_COMFY:
                    return OnboardingPageId.ATTACHED_PYTHON_PROCESS
                return OnboardingPageId.ATTACHED_PYTHON_MANUAL
            return self._target_page(self._draft.target_mode)
        if current_page is OnboardingPageId.INTEGRATIONS:
            if self._model_session.enabled:
                if self._model_session.state.selected_version_ids:
                    return OnboardingPageId.MODEL_DOWNLOAD_REVIEW
                if (
                    self._model_session.state.recommendation_pages
                    and not self._model_session.state.remaining_recommendations_declined
                ):
                    self._model_session.set_page_index(
                        len(self._model_session.state.recommendation_pages) - 1
                    )
                    return OnboardingPageId.MODEL_RECOMMENDATIONS
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.MODEL_RECOMMENDATIONS:
            if self._model_session.state.recommendation_page_index > 0:
                return OnboardingPageId.MODEL_RECOMMENDATIONS
            if self._model_session.state.has_existing_folder is False:
                return OnboardingPageId.EXISTING_MODELS
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.MODEL_DOWNLOAD_REVIEW:
            return OnboardingPageId.MODEL_RECOMMENDATIONS
        if current_page is OnboardingPageId.PROVISIONING:
            return OnboardingPageId.INTEGRATIONS
        if current_page is OnboardingPageId.COMPLETION:
            return OnboardingPageId.PROVISIONING
        return current_page

    def start_provisioning(self) -> None:
        """Provision the selected runtime and Comfy target through execution."""

        selection = ProvisioningSelection(
            self._draft,
            self._flow_mode,
            self._credential_draft,
            self._model_session.state.install_plan,
        )
        self._completion = None
        self._provisioning_executor.start(selection)

    def start_background_preparation(self) -> bool:
        """Start choice-independent setup once target/runtime inputs are stable."""

        if self._flow_mode is not OnboardingFlowMode.FIRST_RUN:
            return False
        if self._draft.target_mode is OnboardingTargetMode.REMOTE:
            return False
        return self._provisioning_executor.start_preparation(self._draft)

    def shutdown(self) -> None:
        """Cancel provisioning work and release the owned execution lane."""

        self._provisioning_executor.shutdown()

    def _accept_completion(self, completion: OnboardingCompletion) -> None:
        """Store and publish one successful provisioning completion."""

        self._completion = completion
        self.completion_ready.emit(completion)

    def _finish_provisioning(self) -> None:
        """Clear transient credentials and publish task completion."""

        self._credential_draft = OnboardingCredentialDraft()
        self.provisioning_finished.emit()

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

    @staticmethod
    def _target_page(target_mode: OnboardingTargetMode) -> OnboardingPageId:
        """Map one target mode to its dedicated options page."""

        if target_mode is OnboardingTargetMode.ATTACHED_LOCAL:
            return OnboardingPageId.ATTACHED_LOCAL
        if target_mode is OnboardingTargetMode.REMOTE:
            return OnboardingPageId.REMOTE
        return OnboardingPageId.MANAGED_LOCAL
