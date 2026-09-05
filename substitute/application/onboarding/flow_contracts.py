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

"""Define typed contracts shared by onboarding flow collaborators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
)
from substitute.application.onboarding.setup_transaction_service import (
    SetupTransactionOptions,
)
from substitute.domain.civitai import CivitaiPreferences
from substitute.domain.comfy_environment import ComfyModelRootStatus
from substitute.domain.danbooru.preferences import DanbooruPreferences
from substitute.domain.generation import OutputPreferences
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyTargetConfiguration,
    InstallationConfiguration,
    InstallationContext,
    ManagedRuntimeConfiguration,
    RuntimeConfiguration,
)
from substitute.domain.onboarding.readiness_models import ReadinessAssessment
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.domain.prompt.preferences.models import PromptEditorPreferences


@dataclass(frozen=True)
class OnboardingDraftState:
    """Capture onboarding selections using presentation-safe primitive types."""

    installation_root: Path
    target_mode: str
    endpoint_host: str
    endpoint_port: int
    managed_workspace_path: Path
    attached_workspace_path: Path | None
    attached_python_binding: ComfyPythonBinding | None = None
    managed_model_root: Path | None = None
    managed_model_root_uses_default: bool = True
    output_root: Path | None = None
    output_root_uses_default: bool = True
    danbooru_tag_help_enabled: bool = True
    danbooru_safe_previews_enabled: bool = True
    danbooru_image_rating_policy: str = "safe_only"
    civitai_model_help_enabled: bool = True
    civitai_downloads_enabled: bool = True
    civitai_safe_thumbnails_enabled: bool = True
    civitai_thumbnail_safety_policy: str = "sfw_only"
    civitai_api_key_configured: bool = False
    detected_platform: str | None = None
    detected_accelerator: str | None = None
    selected_install_target: str | None = None
    selected_python_version: str | None = None
    selected_comfy_channel: str | None = None
    selected_backend_policy: str | None = None
    selected_torch_channel: str | None = None
    selected_torch_reason: str | None = None
    selected_stability: str | None = None
    force_cpu_mode: bool = False
    prefer_edge_torch: bool = False
    prefer_edge_comfy_channel: bool = False


@dataclass(frozen=True)
class OnboardingCompletionResult:
    """Capture the result of a successful onboarding or repair run."""

    context: InstallationContext
    restart_required: bool
    launch_command: tuple[str, ...]


@dataclass(frozen=True)
class OnboardingProvisioningFailure(Exception):
    """Describe a user-facing onboarding failure with remediation guidance."""

    headline: ApplicationText
    user_message: ApplicationText
    technical_detail: str
    remediation_steps: tuple[ApplicationText, ...]
    transaction_id: str | None = None
    failed_task: str | None = None

    def __str__(self) -> str:
        """Render the technical detail when coerced to a string."""

        return self.technical_detail


class OnboardingServiceProtocol(Protocol):
    """Describe onboarding configuration operations used by the flow."""

    def load_draft_context(self) -> InstallationContext:
        """Load persisted or default onboarding context."""

    def build_managed_local_context(
        self, *, endpoint: ComfyEndpoint, workspace_path: Path
    ) -> InstallationContext:
        """Build managed-local state without active writes."""

    def build_attached_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
        python_binding: ComfyPythonBinding | None = None,
    ) -> InstallationContext:
        """Build attached-local state without active writes."""

    def build_remote_context(self, *, endpoint: ComfyEndpoint) -> InstallationContext:
        """Build remote state without active writes."""


class RuntimeLaunchServiceProtocol(Protocol):
    """Describe runtime launch behavior used by the onboarding flow."""

    def provision_draft(
        self, configuration: RuntimeConfiguration | None = None
    ) -> RuntimeConfiguration:
        """Provision runtime files without active configuration writes."""

    def build_launch_command(
        self, configuration: RuntimeConfiguration, entrypoint_path: Path
    ) -> list[str]:
        """Build the authoritative runtime launch command."""


class ReadinessServiceProtocol(Protocol):
    """Describe readiness assessment behavior used by onboarding."""

    def assess(self) -> ReadinessAssessment:
        """Assess active bootstrap readiness."""

    def assess_candidate(
        self,
        *,
        installation: InstallationConfiguration,
        runtime: RuntimeConfiguration,
        target: ComfyTargetConfiguration,
        managed_runtime: ManagedRuntimeConfiguration | None = None,
    ) -> ReadinessAssessment:
        """Assess pending setup state before commit."""


class OnboardingModelRootProviderProtocol(Protocol):
    """Describe BackEnd-owned model-root state used by onboarding."""

    def load(self, target: ComfyTargetConfiguration) -> ComfyModelRootStatus | None:
        """Return connected host model-root state when available."""


class OutputPreferenceServiceProtocol(Protocol):
    """Describe output preference operations used by onboarding."""

    def load_preferences(self) -> OutputPreferences:
        """Load output preferences."""

    def effective_output_root(
        self, preferences: OutputPreferences | None = None
    ) -> Path:
        """Return the concrete output root."""


class PromptEditorPreferenceServiceProtocol(Protocol):
    """Describe prompt editor preference operations used by onboarding."""

    def load_preferences(self) -> PromptEditorPreferences:
        """Load prompt editor preferences."""


class DanbooruPreferenceServiceProtocol(Protocol):
    """Describe Danbooru preference operations used by onboarding."""

    def load_preferences(self) -> DanbooruPreferences:
        """Load Danbooru viewer preferences."""


class CivitaiPreferenceServiceProtocol(Protocol):
    """Describe CivitAI preference operations used by onboarding."""

    def load_preferences(self) -> CivitaiPreferences:
        """Load CivitAI preferences."""


class CivitaiCredentialServiceProtocol(Protocol):
    """Describe CivitAI credential state used by onboarding."""

    def has_api_key(self) -> bool:
        """Return whether a CivitAI API key is stored."""


class OnboardingPreferenceSetupServiceProtocol(Protocol):
    """Describe onboarding preference persistence used by the flow."""

    def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
        """Persist non-secret onboarding choices."""

    def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
        """Persist optional onboarding credentials."""


class ManagedRuntimeServiceProtocol(Protocol):
    """Describe managed runtime strategy selection."""

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Load the persisted managed runtime selection."""

    def load_draft_configuration(self) -> ManagedRuntimeConfiguration:
        """Load an onboarding-safe managed runtime selection."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Detect hardware and return a strategy without saving it."""


class SetupTransactionServiceProtocol(Protocol):
    """Describe pending setup transaction operations used by the flow."""

    def load(self) -> SetupTransaction | None:
        """Load the current pending transaction."""

    def begin(
        self,
        *,
        mode: SetupTransactionMode,
        options: SetupTransactionOptions | None = None,
    ) -> SetupTransaction:
        """Create a pending setup transaction."""

    def update_status(
        self, transaction_id: str, status: SetupTransactionStatus
    ) -> SetupTransaction:
        """Update a pending transaction status."""

    def record_installation(
        self, transaction_id: str, configuration: InstallationConfiguration
    ) -> SetupTransaction:
        """Record pending installation configuration."""

    def record_runtime(
        self, transaction_id: str, configuration: RuntimeConfiguration
    ) -> SetupTransaction:
        """Record pending runtime configuration."""

    def record_target(
        self, transaction_id: str, configuration: ComfyTargetConfiguration
    ) -> SetupTransaction:
        """Record pending Comfy target configuration."""

    def record_managed_runtime(
        self, transaction_id: str, configuration: ManagedRuntimeConfiguration
    ) -> SetupTransaction:
        """Record pending managed runtime configuration."""

    def record_failure(
        self, transaction_id: str, failure: SetupTransactionFailure
    ) -> SetupTransaction:
        """Record pending setup failure details."""

    def commit(self, transaction_id: str) -> InstallationContext:
        """Promote pending setup state into active configuration."""


class OnboardingBundleProtocol(Protocol):
    """Describe the installation-root-scoped onboarding collaborators."""

    @property
    def onboarding_service(self) -> OnboardingServiceProtocol:
        """Return onboarding configuration operations."""

    @property
    def runtime_service(self) -> RuntimeLaunchServiceProtocol:
        """Return runtime provisioning and launch operations."""

    @property
    def readiness_service(self) -> ReadinessServiceProtocol:
        """Return candidate-readiness assessment operations."""

    @property
    def managed_runtime_service(self) -> ManagedRuntimeServiceProtocol:
        """Return managed runtime policy operations."""

    @property
    def setup_transaction_service(self) -> SetupTransactionServiceProtocol:
        """Return pending setup transaction operations."""

    @property
    def model_root_provider(self) -> OnboardingModelRootProviderProtocol:
        """Return BackEnd-owned model-root state access."""

    @property
    def output_preference_service(self) -> OutputPreferenceServiceProtocol:
        """Return output preference operations."""

    @property
    def prompt_editor_preference_service(
        self,
    ) -> PromptEditorPreferenceServiceProtocol:
        """Return prompt editor preference operations."""

    @property
    def danbooru_preference_service(self) -> DanbooruPreferenceServiceProtocol:
        """Return Danbooru preference operations."""

    @property
    def civitai_preference_service(self) -> CivitaiPreferenceServiceProtocol:
        """Return CivitAI preference operations."""

    @property
    def civitai_credential_service(self) -> CivitaiCredentialServiceProtocol:
        """Return CivitAI credential-state operations."""

    @property
    def preference_setup_service(self) -> OnboardingPreferenceSetupServiceProtocol:
        """Return onboarding preference persistence operations."""


ManagedWorkspaceProvisioner = Callable[..., Path]


class AttachedWorkspaceProvisioner(Protocol):
    """Prepare one attached Comfy workspace through a verified interpreter."""

    def __call__(
        self,
        *,
        workspace: Path,
        python_binding: ComfyPythonBinding,
        model_root: Path | None = None,
        configure_model_root: bool = False,
        on_status: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        **unused: object,
    ) -> ComfyPythonBinding:
        """Prepare dependencies without replacing the selected interpreter."""


OnboardingBundleFactory = Callable[[Path | None], OnboardingBundleProtocol]


__all__ = [
    "AttachedWorkspaceProvisioner",
    "ManagedWorkspaceProvisioner",
    "OnboardingBundleFactory",
    "OnboardingBundleProtocol",
    "OnboardingCompletionResult",
    "OnboardingDraftState",
    "OnboardingProvisioningFailure",
]
