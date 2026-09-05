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

"""Provide deterministic onboarding-controller test doubles."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.presentation.onboarding.readiness_issue_presenter import (
    ReadinessIssuePresentation,
)
from substitute.presentation.onboarding.model_onboarding_session import (
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)


class _FakeController(QObject):
    """Provide the minimum onboarding controller surface consumed by the window."""

    draft_changed = Signal(object)
    provisioning_started = Signal()
    provisioning_finished = Signal()
    progress_status_changed = Signal(str)
    progress_log_emitted = Signal(str)
    setup_progress_changed = Signal(object)
    background_preparation_finished = Signal(object)
    failure_reported = Signal(object)
    completion_ready = Signal(object)

    def __init__(self, draft: OnboardingDraft, flow_mode: OnboardingFlowMode) -> None:
        """Store fixed onboarding state for the window contract tests."""

        super().__init__()
        self._draft = draft
        self._flow_mode = flow_mode
        self._model_session = ModelOnboardingSession(
            flow_mode=flow_mode,
            target_mode=draft.target_mode,
        )
        self._readiness_assessment = ReadinessAssessment(
            route=BootstrapRoute.REPAIR,
            issues=(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_PYTHON_MISSING,
                    summary="Runtime Python executable is missing.",
                    detail="Repair the visible runtime before normal launch.",
                ),
            ),
        )
        self.provisioning_calls = 0
        self.last_civitai_api_key = ""

    @property
    def draft(self) -> OnboardingDraft:
        """Return the current onboarding draft."""

        return self._draft

    @property
    def flow_mode(self) -> OnboardingFlowMode:
        """Return the active onboarding mode."""

        return self._flow_mode

    @property
    def model_session(self) -> ModelOnboardingSession:
        """Return the fake window's model-onboarding session."""

        return self._model_session

    @property
    def readiness_assessment(self) -> ReadinessAssessment:
        """Return the repair-mode readiness assessment."""

        return self._readiness_assessment

    def present_readiness_issues(self) -> tuple[ReadinessIssuePresentation, ...]:
        """Return user-facing repair copy for the fake readiness issue."""

        return (
            ReadinessIssuePresentation(
                headline="Substitute's local setup is incomplete",
                user_message="A required local Python file is missing.",
                technical_detail="Missing runtime Python executable.",
            ),
        )

    def next_page(self, current_page: OnboardingPageId) -> OnboardingPageId:
        """Return the next page in a minimal deterministic sequence."""

        if current_page is OnboardingPageId.WELCOME:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.COMFY_PREFLIGHT:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.TARGET_MODE:
            return OnboardingPageId.MANAGED_LOCAL
        if current_page is OnboardingPageId.MANAGED_LOCAL:
            return OnboardingPageId.EXISTING_MODELS
        if current_page is OnboardingPageId.EXISTING_MODELS:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.FOLDERS:
            return OnboardingPageId.INTEGRATIONS
        if current_page is OnboardingPageId.INTEGRATIONS:
            return OnboardingPageId.PROVISIONING
        return current_page

    def previous_page(self, current_page: OnboardingPageId) -> OnboardingPageId:
        """Return the previous page in the minimal deterministic sequence."""

        if current_page is OnboardingPageId.TARGET_MODE:
            return OnboardingPageId.WELCOME
        if current_page is OnboardingPageId.COMFY_PREFLIGHT:
            return OnboardingPageId.WELCOME
        if current_page is OnboardingPageId.MANAGED_LOCAL:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.FOLDERS:
            return OnboardingPageId.EXISTING_MODELS
        if current_page is OnboardingPageId.EXISTING_MODELS:
            return OnboardingPageId.MANAGED_LOCAL
        if current_page is OnboardingPageId.INTEGRATIONS:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.PROVISIONING:
            return OnboardingPageId.INTEGRATIONS
        return current_page

    def set_installation_root(self, installation_root: Path) -> None:
        """Update the fake draft installation root."""

        self._draft = replace(self._draft, installation_root=installation_root)

    def update_target_mode(self, target_mode: OnboardingTargetMode) -> None:
        """Update the fake target mode."""

        self._draft = replace(self._draft, target_mode=target_mode)
        self._model_session.set_target_mode(target_mode)

    def update_endpoint(self, host: str, port: int) -> None:
        """Accept endpoint updates without side effects."""

        _ = host, port

    def update_managed_workspace(self, workspace_path: Path) -> None:
        """Accept managed workspace updates without side effects."""

        _ = workspace_path

    def update_attached_workspace(self, workspace_path: Path | None) -> None:
        """Accept attached workspace updates without side effects."""

        self._draft = replace(
            self._draft,
            attached_workspace_path=workspace_path,
            attached_python_binding=None,
        )

    def update_attached_python_binding(
        self,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Store a verified attached Python binding."""

        self._draft = replace(self._draft, attached_python_binding=binding)

    def update_managed_runtime_preferences(
        self,
        *,
        force_cpu_mode: bool,
        prefer_edge_torch: bool,
        prefer_edge_comfy_channel: bool,
    ) -> None:
        """Accept managed runtime preference updates without side effects."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel

    def start_background_preparation(self) -> bool:
        """Record no background work for the inert window double."""

        return False

    def update_folder_preferences(
        self,
        *,
        managed_model_root: Path | None,
        managed_model_root_uses_default: bool,
        output_root: Path | None,
        output_root_uses_default: bool,
    ) -> None:
        """Update fake folder preferences."""

        self._draft = OnboardingDraft(
            installation_root=self._draft.installation_root,
            target_mode=self._draft.target_mode,
            endpoint_host=self._draft.endpoint_host,
            endpoint_port=self._draft.endpoint_port,
            managed_workspace_path=self._draft.managed_workspace_path,
            attached_workspace_path=self._draft.attached_workspace_path,
            managed_model_root=managed_model_root,
            managed_model_root_uses_default=managed_model_root_uses_default,
            output_root=output_root,
            output_root_uses_default=output_root_uses_default,
        )

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
        """Update fake integration preferences."""

        self.last_civitai_api_key = civitai_api_key
        self._draft = OnboardingDraft(
            installation_root=self._draft.installation_root,
            target_mode=self._draft.target_mode,
            endpoint_host=self._draft.endpoint_host,
            endpoint_port=self._draft.endpoint_port,
            managed_workspace_path=self._draft.managed_workspace_path,
            attached_workspace_path=self._draft.attached_workspace_path,
            danbooru_tag_help_enabled=danbooru_tag_help_enabled,
            danbooru_safe_previews_enabled=danbooru_safe_previews_enabled,
            danbooru_image_rating_policy=danbooru_image_rating_policy,
            civitai_model_help_enabled=civitai_model_help_enabled,
            civitai_downloads_enabled=civitai_downloads_enabled,
            civitai_safe_thumbnails_enabled=civitai_safe_thumbnails_enabled,
            civitai_thumbnail_safety_policy=civitai_thumbnail_safety_policy,
        )

    def start_provisioning(self) -> None:
        """Emit immediate successful completion for the window contract."""

        self.provisioning_calls += 1
        self.provisioning_started.emit()
        installation = InstallationConfiguration.create_default(
            self._draft.installation_root
        )
        runtime = RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=installation.runtime_dir
            / ".venv"
            / "Scripts"
            / "python.exe",
            bootstrap_status=RuntimeBootstrapStatus.READY,
        )
        target = ComfyTargetConfiguration(
            mode=ComfyTargetMode(self._draft.target_mode.value),
            endpoint=ComfyEndpoint(
                host=self._draft.endpoint_host,
                port=self._draft.endpoint_port,
            ),
            workspace_path=self._draft.managed_workspace_path,
            install_owned=self._draft.target_mode is OnboardingTargetMode.MANAGED_LOCAL,
            launch_owned=self._draft.target_mode is OnboardingTargetMode.MANAGED_LOCAL,
        )
        self.completion_ready.emit(
            OnboardingCompletion(
                context=InstallationContext(
                    installation=installation,
                    runtime=runtime,
                    comfy_target=target,
                ),
                restart_required=self._flow_mode is OnboardingFlowMode.RECONFIGURE,
                launch_command=("python", "main.py"),
            )
        )
        self.provisioning_finished.emit()


class _ResettingDraftController(_FakeController):
    """Mirror the real controller's draft-changed side effects for field-order tests."""

    def update_endpoint(self, host: str, port: int) -> None:
        """Emit a real draft update so the window can accidentally reset other fields."""

        self._draft = OnboardingDraft(
            installation_root=self._draft.installation_root,
            target_mode=self._draft.target_mode,
            endpoint_host=host.strip(),
            endpoint_port=port,
            managed_workspace_path=self._draft.managed_workspace_path,
            attached_workspace_path=self._draft.attached_workspace_path,
        )
        self.draft_changed.emit(self._draft)

    def update_attached_workspace(self, workspace_path: Path | None) -> None:
        """Store the attached workspace like the real controller does."""

        self._draft = replace(
            self._draft,
            attached_workspace_path=workspace_path,
            attached_python_binding=None,
        )
        self.draft_changed.emit(self._draft)

    def update_attached_python_binding(
        self,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Store verified attached Python evidence like the real controller."""

        self._draft = replace(
            self._draft,
            attached_python_binding=binding,
        )
        self.draft_changed.emit(self._draft)
