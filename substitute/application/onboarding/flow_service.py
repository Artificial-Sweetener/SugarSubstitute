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

"""Coordinate onboarding draft loading and provisioning without Qt dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonResolutionError,
    ComfyPythonResolutionFailure,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ManagedRuntimeConfiguration,
    RuntimeConfiguration,
)
from substitute.application.onboarding.managed_runtime_state_recorder import (
    PendingManagedRuntimeStateRecorder,
)
from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
    OnboardingPreferenceSetupFailure,
)
from substitute.application.onboarding.setup_transaction_service import (
    SetupTransactionOptions,
)
from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepositoryError,
)
from substitute.domain.onboarding.readiness_models import (
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
)
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.domain.civitai import CivitaiPreferences, CivitaiThumbnailSafetyPolicy
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_environment import ComfyModelRootStatus
from substitute.domain.danbooru.preferences import DanbooruPreferences
from substitute.domain.generation import OutputOrganizationPreferences
from substitute.domain.prompt import PromptEditorFeature, PromptEditorPreferences
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.onboarding.flow_service")


@dataclass(frozen=True)
class OnboardingDraftState:
    """Capture onboarding selections using presentation-safe primitive types."""

    installation_root: Path
    target_mode: str
    endpoint_host: str
    endpoint_port: int
    managed_workspace_path: Path
    attached_workspace_path: Path | None
    attached_python_executable: Path | None = None
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

    headline: str
    user_message: str
    technical_detail: str
    remediation_steps: tuple[str, ...]

    def __str__(self) -> str:
        """Render the technical detail when coerced to a string."""

        return self.technical_detail


class OnboardingServiceProtocol(Protocol):
    """Describe the onboarding application operations used by the flow service."""

    def load_draft_context(self) -> InstallationContext:
        """Load persisted or default onboarding context."""

    def configure_managed_local(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Configure managed-local onboarding state."""

    def build_managed_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Build managed-local onboarding state without active writes."""

    def configure_attached_local(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Configure existing-local onboarding state."""

    def build_attached_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
        python_binding: ComfyPythonBinding | None = None,
    ) -> InstallationContext:
        """Build existing-local onboarding state without active writes."""

    def configure_remote(self, *, endpoint: ComfyEndpoint) -> InstallationContext:
        """Configure remote onboarding state."""

    def build_remote_context(self, *, endpoint: ComfyEndpoint) -> InstallationContext:
        """Build remote onboarding state without active writes."""


class RuntimeLaunchServiceProtocol(Protocol):
    """Describe runtime launch command behavior used by the flow service."""

    def provision_draft(
        self,
        configuration: RuntimeConfiguration | None = None,
    ) -> RuntimeConfiguration:
        """Provision runtime files and return configuration without active writes."""

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Build the authoritative runtime launch command."""


class ReadinessServiceProtocol(Protocol):
    """Describe readiness assessment behavior used by the flow service."""

    def assess(self) -> ReadinessAssessment:
        """Assess bootstrap readiness for the selected install root."""

    def assess_candidate(
        self,
        *,
        installation: InstallationConfiguration,
        runtime: RuntimeConfiguration,
        target: ComfyTargetConfiguration,
        managed_runtime: ManagedRuntimeConfiguration | None = None,
    ) -> ReadinessAssessment:
        """Assess pending setup state before it is committed."""


class OnboardingModelRootProviderProtocol(Protocol):
    """Describe BackEnd-owned model-root state used by onboarding."""

    def load(
        self,
        target: ComfyTargetConfiguration,
    ) -> ComfyModelRootStatus | None:
        """Return connected host model-root state when BackEnd is available."""


class OutputOrganizationPreferenceServiceProtocol(Protocol):
    """Describe output preference operations used by onboarding."""

    def load_preferences(self) -> OutputOrganizationPreferences:
        """Load output organization preferences."""

    def effective_output_root(
        self,
        preferences: OutputOrganizationPreferences | None = None,
    ) -> Path:
        """Return the concrete output root for the supplied preferences."""


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
        """Return whether a CivitAI API key is already stored."""


class OnboardingPreferenceSetupServiceProtocol(Protocol):
    """Describe onboarding preference persistence used by the flow service."""

    def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
        """Persist non-secret onboarding choices."""

    def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
        """Persist optional onboarding credentials."""


class OnboardingBundleProtocol(Protocol):
    """Describe the onboarding bundle consumed by the flow service."""

    @property
    def onboarding_service(self) -> OnboardingServiceProtocol:
        """Return the onboarding service used to load and save config."""

    @property
    def runtime_service(self) -> RuntimeLaunchServiceProtocol:
        """Return the runtime service used to build launch commands."""

    @property
    def readiness_service(self) -> ReadinessServiceProtocol:
        """Return the readiness service used after provisioning."""

    @property
    def managed_runtime_service(self) -> "ManagedRuntimeServiceProtocol":
        """Return the managed runtime service used for strategy selection."""

    @property
    def setup_transaction_service(self) -> "SetupTransactionServiceProtocol":
        """Return the setup transaction service used for pending state."""

    @property
    def model_root_provider(self) -> OnboardingModelRootProviderProtocol:
        """Return the connected BackEnd model-root provider."""

    @property
    def output_organization_service(
        self,
    ) -> OutputOrganizationPreferenceServiceProtocol:
        """Return the output organization preference service."""

    @property
    def prompt_editor_preference_service(
        self,
    ) -> PromptEditorPreferenceServiceProtocol:
        """Return the prompt editor preference service."""

    @property
    def danbooru_preference_service(self) -> DanbooruPreferenceServiceProtocol:
        """Return the Danbooru preference service."""

    @property
    def civitai_preference_service(self) -> CivitaiPreferenceServiceProtocol:
        """Return the CivitAI preference service."""

    @property
    def civitai_credential_service(self) -> CivitaiCredentialServiceProtocol:
        """Return the CivitAI credential service."""

    @property
    def preference_setup_service(self) -> OnboardingPreferenceSetupServiceProtocol:
        """Return the onboarding preference persistence service."""


class ManagedRuntimeServiceProtocol(Protocol):
    """Describe managed runtime selection behavior used by the flow service."""

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Load the persisted managed runtime configuration when present."""

    def load_draft_configuration(self) -> ManagedRuntimeConfiguration:
        """Load an onboarding-safe managed runtime configuration."""

    def detect_and_select(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Detect hardware and persist the selected managed install strategy."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Detect hardware and return the selected strategy without saving."""


class SetupTransactionServiceProtocol(Protocol):
    """Describe pending setup transaction operations used by the flow service."""

    def load(self) -> SetupTransaction | None:
        """Load the current pending setup transaction when present."""

    def begin(
        self,
        *,
        mode: SetupTransactionMode,
        options: SetupTransactionOptions | None = None,
    ) -> SetupTransaction:
        """Create a pending setup transaction."""

    def update_status(
        self,
        transaction_id: str,
        status: SetupTransactionStatus,
    ) -> SetupTransaction:
        """Update one pending setup transaction status."""

    def record_installation(
        self,
        transaction_id: str,
        configuration: InstallationConfiguration,
    ) -> SetupTransaction:
        """Record pending installation configuration."""

    def record_runtime(
        self,
        transaction_id: str,
        configuration: RuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending runtime configuration."""

    def record_target(
        self,
        transaction_id: str,
        configuration: ComfyTargetConfiguration,
    ) -> SetupTransaction:
        """Record pending Comfy target configuration."""

    def record_managed_runtime(
        self,
        transaction_id: str,
        configuration: ManagedRuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending managed runtime configuration."""

    def record_failure(
        self,
        transaction_id: str,
        failure: SetupTransactionFailure,
    ) -> SetupTransaction:
        """Record pending setup failure details."""

    def commit(self, transaction_id: str) -> InstallationContext:
        """Promote pending setup state into active configuration."""


ManagedWorkspaceProvisioner = Callable[..., Path]


class AttachedWorkspaceProvisioner(Protocol):
    """Prepare one attached Comfy workspace through a verified interpreter."""

    def __call__(
        self,
        *,
        workspace: Path,
        python_executable: Path | None = None,
        on_status: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        **unused: object,
    ) -> ComfyPythonBinding:
        """Prepare dependencies without replacing the selected interpreter."""


class AttachedPythonResolver(Protocol):
    """Resolve one verified binding for a stopped attached Comfy workspace."""

    def __call__(
        self,
        workspace: Path,
        *,
        explicit_executable: Path | None = None,
    ) -> ComfyPythonBinding:
        """Discover automatically or validate the user's explicit selection."""


OnboardingBundleFactory = Callable[[Path | None], OnboardingBundleProtocol]


@dataclass
class OnboardingFlowService:
    """Load onboarding drafts and provision the selected target end-to-end."""

    service_bundle_factory: OnboardingBundleFactory
    managed_workspace_provisioner: ManagedWorkspaceProvisioner
    entrypoint_path: Path
    attached_workspace_provisioner: AttachedWorkspaceProvisioner | None = None
    attached_python_resolver: AttachedPythonResolver | None = None
    transaction_mode: SetupTransactionMode = SetupTransactionMode.REPAIR

    def load_draft(self, installation_root: Path) -> OnboardingDraftState:
        """Load onboarding draft state from persisted config or defaults."""

        bundle = self.service_bundle_factory(installation_root)
        context = bundle.onboarding_service.load_draft_context()
        pending_transaction = self._load_pending_transaction(bundle)
        if (
            pending_transaction is not None
            and pending_transaction.installation is not None
            and pending_transaction.target is not None
        ):
            context = InstallationContext(
                installation=pending_transaction.installation,
                runtime=pending_transaction.runtime or context.runtime,
                comfy_target=pending_transaction.target,
            )
        managed_runtime = (
            pending_transaction.managed_runtime
            if pending_transaction is not None
            and pending_transaction.managed_runtime is not None
            else None
        ) or bundle.managed_runtime_service.load_draft_configuration()
        managed_workspace_path = (
            context.comfy_target.workspace_path or context.managed_comfy_dir
        )
        model_root_status = bundle.model_root_provider.load(context.comfy_target)
        default_model_root = managed_workspace_path / "models"
        reported_model_root = (
            Path(
                model_root_status.configured_model_root
                or model_root_status.default_model_root
            )
            if model_root_status is not None
            and context.comfy_target.workspace_path is not None
            else None
        )
        output_preferences = bundle.output_organization_service.load_preferences()
        output_root = bundle.output_organization_service.effective_output_root(
            output_preferences
        )
        prompt_preferences = bundle.prompt_editor_preference_service.load_preferences()
        danbooru_preferences = bundle.danbooru_preference_service.load_preferences()
        civitai_preferences = bundle.civitai_preference_service.load_preferences()
        return OnboardingDraftState(
            installation_root=context.install_root,
            target_mode=context.comfy_target.mode.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=managed_workspace_path,
            attached_workspace_path=context.comfy_target.workspace_path,
            attached_python_executable=(
                context.comfy_target.python_binding.executable
                if context.comfy_target.python_binding is not None
                else None
            ),
            managed_model_root=(reported_model_root or default_model_root),
            managed_model_root_uses_default=(
                model_root_status.uses_default
                if model_root_status is not None
                else True
            ),
            output_root=output_root,
            output_root_uses_default=output_preferences.output_root is None,
            danbooru_tag_help_enabled=(
                prompt_preferences.user_allows(PromptEditorFeature.DANBOORU_URL_IMPORT)
                or prompt_preferences.user_allows(
                    PromptEditorFeature.DANBOORU_WIKI_LOOKUP
                )
            ),
            danbooru_safe_previews_enabled=danbooru_preferences.show_wiki_images,
            danbooru_image_rating_policy=danbooru_preferences.allowed_image_ratings.value,
            civitai_model_help_enabled=(
                civitai_preferences.metadata_lookup_enabled
                or civitai_preferences.missing_model_lookup_enabled
            ),
            civitai_downloads_enabled=civitai_preferences.downloads_enabled,
            civitai_safe_thumbnails_enabled=(
                civitai_preferences.thumbnail_downloads_enabled
                and civitai_preferences.thumbnail_safety_policy
                is not CivitaiThumbnailSafetyPolicy.DISABLED
            ),
            civitai_thumbnail_safety_policy=(
                CivitaiThumbnailSafetyPolicy.SFW_ONLY.value
                if civitai_preferences.thumbnail_safety_policy
                is CivitaiThumbnailSafetyPolicy.DISABLED
                else civitai_preferences.thumbnail_safety_policy.value
            ),
            civitai_api_key_configured=self._civitai_api_key_is_configured(bundle),
            detected_platform=managed_runtime.detected_platform,
            detected_accelerator=managed_runtime.detected_accelerator,
            selected_install_target=managed_runtime.install_target,
            selected_python_version=managed_runtime.python_version,
            selected_comfy_channel=managed_runtime.comfy_channel,
            selected_backend_policy=managed_runtime.backend_policy,
            selected_torch_channel=managed_runtime.torch_release_channel,
            selected_torch_reason=managed_runtime.torch_selection_reason,
            selected_stability=managed_runtime.stability.value,
            force_cpu_mode=managed_runtime.force_cpu_mode,
            prefer_edge_torch=managed_runtime.prefer_edge_torch,
            prefer_edge_comfy_channel=managed_runtime.prefer_edge_comfy_channel,
        )

    @staticmethod
    def _load_pending_transaction(
        bundle: OnboardingBundleProtocol,
    ) -> SetupTransaction | None:
        """Load pending setup state for draft prefill and ignore corrupt state."""

        try:
            return bundle.setup_transaction_service.load()
        except SetupTransactionRepositoryError as error:
            log_warning(
                _LOGGER,
                "Pending setup transaction could not be loaded for draft prefill.",
                error=error,
            )
            return None

    @staticmethod
    def _civitai_api_key_is_configured(bundle: OnboardingBundleProtocol) -> bool:
        """Return secure credential presence without exposing the stored key."""

        try:
            return bundle.civitai_credential_service.has_api_key()
        except Exception as error:
            log_warning(
                _LOGGER,
                "CivitAI API key status could not be loaded for onboarding.",
                error=error,
            )
            return False

    def provision(
        self,
        *,
        draft: OnboardingDraftState,
        credential_draft: OnboardingCredentialDraft | None = None,
        restart_required: bool,
        on_status: Callable[[str], None],
        on_log: Callable[[str], None],
    ) -> OnboardingCompletionResult:
        """Provision the selected target and return the completion payload."""
        bundle = self.service_bundle_factory(draft.installation_root)
        draft = self._recover_stale_attached_managed_draft(
            bundle=bundle,
            draft=draft,
        )
        endpoint = ComfyEndpoint(
            host=draft.endpoint_host.strip(),
            port=int(draft.endpoint_port),
        )
        on_status("Starting setup.")
        on_log(f"Runtime root: {draft.installation_root / 'runtime'}")
        target_mode = ComfyTargetMode(draft.target_mode)
        transaction_id: str | None = None
        try:
            if target_mode is ComfyTargetMode.MANAGED_LOCAL:
                transaction = bundle.setup_transaction_service.begin(
                    mode=self.transaction_mode,
                    options=SetupTransactionOptions(
                        workspace_path=draft.managed_workspace_path,
                        endpoint_host=endpoint.host,
                        endpoint_port=endpoint.port,
                        force_cpu_mode=draft.force_cpu_mode,
                        prefer_edge_torch=draft.prefer_edge_torch,
                        prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                    ),
                )
                transaction_id = transaction.transaction_id
                pending_context = bundle.onboarding_service.build_managed_local_context(
                    endpoint=endpoint,
                    workspace_path=draft.managed_workspace_path,
                )
                bundle.setup_transaction_service.record_installation(
                    transaction.transaction_id,
                    pending_context.installation,
                )
                bundle.setup_transaction_service.record_target(
                    transaction.transaction_id,
                    pending_context.comfy_target,
                )
                self._save_setup_preferences(bundle=bundle, draft=draft)
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_RUNTIME_SELECTING,
                )
                managed_runtime = bundle.managed_runtime_service.select_configuration(
                    force_cpu_mode=draft.force_cpu_mode,
                    prefer_edge_torch=draft.prefer_edge_torch,
                    prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                )
                bundle.setup_transaction_service.record_managed_runtime(
                    transaction.transaction_id,
                    managed_runtime,
                )
                on_status("Saving your setup choices.")
                on_log(f"Managed workspace: {draft.managed_workspace_path}")
                on_log(
                    "[ManagedInstall] "
                    f"platform={managed_runtime.detected_platform or 'unknown'} "
                    f"accelerator={managed_runtime.detected_accelerator or 'unknown'} "
                    f"target={managed_runtime.install_target or 'unknown'} "
                    f"python={managed_runtime.python_version or 'unknown'} "
                    f"channel={managed_runtime.comfy_channel or 'unknown'} "
                    f"backend={managed_runtime.backend_policy or 'unknown'} "
                    f"torch_channel={managed_runtime.torch_release_channel or 'unknown'} "
                    f"stability={managed_runtime.stability.value}"
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.RUNTIME_PROVISIONING,
                )
                runtime = bundle.runtime_service.provision_draft(
                    pending_context.runtime
                )
                bundle.setup_transaction_service.record_runtime(
                    transaction.transaction_id,
                    runtime,
                )
                on_status("Installing ComfyUI and finishing setup.")
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
                )
                managed_model_root = self._managed_model_root_for_save(draft)
                self.managed_workspace_provisioner(
                    workspace=(
                        pending_context.comfy_target.workspace_path
                        or pending_context.managed_comfy_dir
                    ),
                    managed_model_root=managed_model_root,
                    configure_model_root=True,
                    force_cpu_mode=draft.force_cpu_mode,
                    prefer_edge_torch=draft.prefer_edge_torch,
                    prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                    refresh_core_nodepacks=(
                        frozenset(CoreNodepackId)
                        if self.transaction_mode is SetupTransactionMode.REPAIR
                        else frozenset()
                    ),
                    installer_temp_root=(
                        draft.installation_root
                        / "runtime"
                        / "installer-temp"
                        / "managed-comfy"
                        / transaction.transaction_id
                    ),
                    on_status=on_status,
                    on_log=on_log,
                    state_recorder=PendingManagedRuntimeStateRecorder(
                        transaction_service=bundle.setup_transaction_service,
                        transaction_id=transaction.transaction_id,
                    ),
                )
                current_transaction = bundle.setup_transaction_service.load()
                candidate_assessment = bundle.readiness_service.assess_candidate(
                    installation=pending_context.installation,
                    runtime=runtime,
                    target=pending_context.comfy_target,
                    managed_runtime=(
                        current_transaction.managed_runtime
                        if current_transaction is not None
                        else None
                    ),
                )
                if candidate_assessment.route is not BootstrapRoute.READY:
                    raise self._build_readiness_failure(
                        draft=draft,
                        target_mode=target_mode,
                        assessment=candidate_assessment,
                    )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.READY_TO_COMMIT,
                )
                context = bundle.setup_transaction_service.commit(
                    transaction.transaction_id
                )
            elif target_mode is ComfyTargetMode.ATTACHED_LOCAL:
                if draft.attached_workspace_path is None:
                    raise OnboardingProvisioningFailure(
                        headline="Choose your existing ComfyUI folder",
                        user_message=(
                            "Use My Current ComfyUI needs the folder that contains "
                            "your local ComfyUI installation."
                        ),
                        technical_detail="Existing local ComfyUI setup requires a folder path.",
                        remediation_steps=(
                            "Choose the folder that contains ComfyUI's main.py file.",
                            "Then run setup again.",
                        ),
                    )
                if self.attached_workspace_provisioner is None:
                    raise RuntimeError("Attached ComfyUI provisioning is unavailable.")
                if self.attached_python_resolver is None:
                    raise RuntimeError(
                        "Attached ComfyUI Python validation is unavailable."
                    )
                on_status("Finding the Python environment for this ComfyUI setup.")
                binding = self.attached_python_resolver(
                    draft.attached_workspace_path,
                    explicit_executable=draft.attached_python_executable,
                )
                transaction = bundle.setup_transaction_service.begin(
                    mode=self.transaction_mode,
                    options=SetupTransactionOptions(
                        workspace_path=draft.attached_workspace_path,
                        endpoint_host=endpoint.host,
                        endpoint_port=endpoint.port,
                    ),
                )
                transaction_id = transaction.transaction_id
                on_status("Preparing your existing ComfyUI setup.")
                on_log(f"Attached workspace: {draft.attached_workspace_path}")
                pending_context = (
                    bundle.onboarding_service.build_attached_local_context(
                        endpoint=endpoint,
                        workspace_path=draft.attached_workspace_path,
                        python_binding=binding,
                    )
                )
                bundle.setup_transaction_service.record_installation(
                    transaction.transaction_id,
                    pending_context.installation,
                )
                bundle.setup_transaction_service.record_target(
                    transaction.transaction_id,
                    pending_context.comfy_target,
                )
                self._save_setup_preferences(bundle=bundle, draft=draft)
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.RUNTIME_PROVISIONING,
                )
                runtime = bundle.runtime_service.provision_draft(
                    pending_context.runtime
                )
                bundle.setup_transaction_service.record_runtime(
                    transaction.transaction_id,
                    runtime,
                )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_RUNTIME_SELECTING,
                )
                managed_runtime = bundle.managed_runtime_service.select_configuration(
                    force_cpu_mode=draft.force_cpu_mode,
                    prefer_edge_torch=draft.prefer_edge_torch,
                    prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                )
                bundle.setup_transaction_service.record_managed_runtime(
                    transaction.transaction_id,
                    managed_runtime,
                )
                on_status("Preparing your existing ComfyUI installation.")
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
                )
                self.attached_workspace_provisioner(
                    workspace=draft.attached_workspace_path,
                    python_executable=binding.executable,
                    on_status=on_status,
                    on_log=on_log,
                )
                current_transaction = bundle.setup_transaction_service.load()
                candidate_assessment = bundle.readiness_service.assess_candidate(
                    installation=pending_context.installation,
                    runtime=runtime,
                    target=pending_context.comfy_target,
                    managed_runtime=(
                        current_transaction.managed_runtime
                        if current_transaction is not None
                        else None
                    ),
                )
                if candidate_assessment.route is not BootstrapRoute.READY:
                    raise self._build_readiness_failure(
                        draft=draft,
                        target_mode=target_mode,
                        assessment=candidate_assessment,
                    )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.READY_TO_COMMIT,
                )
                context = bundle.setup_transaction_service.commit(
                    transaction.transaction_id
                )
            else:
                transaction = bundle.setup_transaction_service.begin(
                    mode=self.transaction_mode,
                    options=SetupTransactionOptions(
                        endpoint_host=endpoint.host,
                        endpoint_port=endpoint.port,
                    ),
                )
                transaction_id = transaction.transaction_id
                on_status("Saving your remote ComfyUI connection.")
                on_log(f"Remote endpoint: {draft.endpoint_host}:{draft.endpoint_port}")
                pending_context = bundle.onboarding_service.build_remote_context(
                    endpoint=endpoint,
                )
                bundle.setup_transaction_service.record_installation(
                    transaction.transaction_id,
                    pending_context.installation,
                )
                bundle.setup_transaction_service.record_target(
                    transaction.transaction_id,
                    pending_context.comfy_target,
                )
                self._save_setup_preferences(bundle=bundle, draft=draft)
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.RUNTIME_PROVISIONING,
                )
                runtime = bundle.runtime_service.provision_draft(
                    pending_context.runtime
                )
                bundle.setup_transaction_service.record_runtime(
                    transaction.transaction_id,
                    runtime,
                )
                candidate_assessment = bundle.readiness_service.assess_candidate(
                    installation=pending_context.installation,
                    runtime=runtime,
                    target=pending_context.comfy_target,
                )
                if candidate_assessment.route is not BootstrapRoute.READY:
                    raise self._build_readiness_failure(
                        draft=draft,
                        target_mode=target_mode,
                        assessment=candidate_assessment,
                    )
                bundle.setup_transaction_service.update_status(
                    transaction.transaction_id,
                    SetupTransactionStatus.READY_TO_COMMIT,
                )
                context = bundle.setup_transaction_service.commit(
                    transaction.transaction_id
                )

            assessment = bundle.readiness_service.assess()
            if assessment.route is not BootstrapRoute.READY:
                raise self._build_readiness_failure(
                    draft=draft,
                    target_mode=target_mode,
                    assessment=assessment,
                )
            launch_command = bundle.runtime_service.build_launch_command(
                context.runtime,
                self.entrypoint_path,
            )
            self._save_optional_credentials(
                bundle=bundle,
                credential_draft=credential_draft,
                on_log=on_log,
            )
            return OnboardingCompletionResult(
                context=context,
                restart_required=restart_required,
                launch_command=tuple(launch_command),
            )
        except OnboardingProvisioningFailure as error:
            if transaction_id is not None:
                self._record_transaction_failure(
                    bundle=bundle,
                    transaction_id=transaction_id,
                    error=error,
                )
            raise
        except Exception as error:
            if transaction_id is not None:
                self._record_transaction_failure(
                    bundle=bundle,
                    transaction_id=transaction_id,
                    error=error,
                )
            raise self._build_provisioning_failure(
                draft=draft,
                target_mode=target_mode,
                error=error,
            ) from error

    @staticmethod
    def _recover_stale_attached_managed_draft(
        *,
        bundle: OnboardingBundleProtocol,
        draft: OnboardingDraftState,
    ) -> OnboardingDraftState:
        """Prefer recovered managed-local state over stale attached-local UI drafts."""

        if ComfyTargetMode(draft.target_mode) is not ComfyTargetMode.ATTACHED_LOCAL:
            return draft
        context = bundle.onboarding_service.load_draft_context()
        target = context.comfy_target
        if target.mode is not ComfyTargetMode.MANAGED_LOCAL:
            return draft
        if (
            target.endpoint.host != draft.endpoint_host.strip()
            or target.endpoint.port != int(draft.endpoint_port)
            or target.workspace_path != draft.attached_workspace_path
        ):
            return draft
        log_info(
            _LOGGER,
            "Recovered stale attached-local provisioning draft as managed-local.",
            workspace=target.workspace_path,
            host=target.endpoint.host,
            port=target.endpoint.port,
        )
        return replace(
            draft,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            managed_workspace_path=target.workspace_path or context.managed_comfy_dir,
            attached_workspace_path=target.workspace_path,
            endpoint_host=target.endpoint.host,
            endpoint_port=target.endpoint.port,
        )

    @staticmethod
    def _managed_model_root_for_save(draft: OnboardingDraftState) -> Path | None:
        """Return the selected managed model root, preserving explicit defaults."""

        if not draft.managed_model_root_uses_default:
            return draft.managed_model_root
        return None

    @staticmethod
    def _save_setup_preferences(
        *,
        bundle: OnboardingBundleProtocol,
        draft: OnboardingDraftState,
    ) -> None:
        """Persist non-secret setup choices with onboarding-friendly failures."""

        try:
            bundle.preference_setup_service.save_preferences(
                OnboardingPreferenceSetupDraft(
                    output_root=None
                    if draft.output_root_uses_default
                    else draft.output_root,
                    danbooru_tag_help_enabled=draft.danbooru_tag_help_enabled,
                    danbooru_safe_previews_enabled=(
                        draft.danbooru_safe_previews_enabled
                    ),
                    danbooru_image_rating_policy=draft.danbooru_image_rating_policy,
                    civitai_model_help_enabled=draft.civitai_model_help_enabled,
                    civitai_downloads_enabled=draft.civitai_downloads_enabled,
                    civitai_safe_thumbnails_enabled=(
                        draft.civitai_safe_thumbnails_enabled
                    ),
                    civitai_thumbnail_safety_policy=draft.civitai_thumbnail_safety_policy,
                )
            )
        except OnboardingPreferenceSetupFailure as error:
            raise OnboardingProvisioningFailure(
                headline="Substitute couldn't save these setup choices",
                user_message=(
                    "Substitute couldn't save one of the folder or helper settings."
                ),
                technical_detail=str(error).strip() or type(error).__name__,
                remediation_steps=(
                    "Review the folder choices and try again.",
                    "You can also finish setup with the defaults and adjust Settings later.",
                ),
            ) from error

    @staticmethod
    def _save_optional_credentials(
        *,
        bundle: OnboardingBundleProtocol,
        credential_draft: OnboardingCredentialDraft | None,
        on_log: Callable[[str], None],
    ) -> None:
        """Save optional credentials without failing completed core setup."""

        if credential_draft is None:
            return
        try:
            bundle.preference_setup_service.save_credentials(credential_draft)
        except OnboardingPreferenceSetupFailure as error:
            log_warning(
                _LOGGER,
                "Optional CivitAI API key could not be saved during onboarding.",
                error=error,
            )
            on_log(
                "CivitAI API key could not be saved. You can add it later in Settings."
            )

    @staticmethod
    def _record_transaction_failure(
        *,
        bundle: OnboardingBundleProtocol,
        transaction_id: str,
        error: Exception,
    ) -> None:
        """Persist transaction failure detail without masking the original error."""

        try:
            bundle.setup_transaction_service.record_failure(
                transaction_id,
                SetupTransactionFailure(
                    code=type(error).__name__,
                    message=str(error).strip() or type(error).__name__,
                    recoverable=True,
                    diagnostic_detail=str(error).strip() or type(error).__name__,
                ),
            )
        except Exception as transaction_error:
            log_warning(
                _LOGGER,
                "Failed to record onboarding transaction failure.",
                transaction_id=transaction_id,
                error=transaction_error,
            )

    @staticmethod
    def _build_readiness_failure(
        *,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
        assessment: ReadinessAssessment,
    ) -> OnboardingProvisioningFailure:
        """Translate readiness issues into target-specific onboarding failures."""

        issue = assessment.issues[0]
        technical_detail = (
            "\n".join(
                detail
                for detail in (
                    listed_issue.detail for listed_issue in assessment.issues
                )
                if detail
            )
            or issue.summary
        )
        if issue.code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING:
            return OnboardingProvisioningFailure(
                headline="The ComfyUI folder couldn't be found",
                user_message=(
                    "Substitute couldn't find the local ComfyUI folder you entered."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    "Check that the folder still exists.",
                    "Choose the folder that contains ComfyUI's main.py file.",
                    "Then try again.",
                ),
            )
        if issue.code is ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE:
            return OnboardingFlowService._endpoint_unreachable_failure(
                draft=draft,
                target_mode=target_mode,
                technical_detail=technical_detail,
            )
        return OnboardingProvisioningFailure(
            headline="Substitute couldn't finish this setup",
            user_message=(
                "Setup details were saved, but Substitute still found a problem that "
                "needs attention before it can continue."
            ),
            technical_detail=technical_detail,
            remediation_steps=tuple(
                OnboardingFlowService._remediation_step_for_issue(
                    issue=listed_issue,
                    draft=draft,
                    target_mode=target_mode,
                )
                for listed_issue in assessment.issues
            ),
        )

    @staticmethod
    def _build_provisioning_failure(
        *,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
        error: Exception,
    ) -> OnboardingProvisioningFailure:
        """Translate one provisioning exception into actionable onboarding guidance."""

        technical_detail = str(error).strip() or type(error).__name__
        if _is_storage_exhaustion_detail(technical_detail):
            return OnboardingProvisioningFailure(
                headline="Substitute ran out of temporary install space",
                user_message=(
                    "Setup could not finish while downloading or installing Python "
                    "packages for ComfyUI."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    f"Free space on the drive that contains {draft.installation_root}.",
                    "Or go back and choose an install location on a drive with more free space.",
                    "Then run setup again.",
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "invalid ComfyUI repository" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline="The ComfyUI folder needs to be cleared before setup can continue",
                user_message=(
                    "Substitute found leftover files in the selected ComfyUI folder, so "
                    "it could not install a fresh managed setup there."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    f"Delete the incomplete folder at {draft.managed_workspace_path}.",
                    "Or go back and choose a different empty ComfyUI folder.",
                    "Then run setup again.",
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "already contains files" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline="The ComfyUI folder needs to be empty first",
                user_message=(
                    "Substitute can't install a fresh managed ComfyUI setup into a "
                    "folder that already has other files in it."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    f"Empty the folder at {draft.managed_workspace_path}.",
                    "Or go back and choose a different empty folder.",
                    "Then try again.",
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "couldn't download ComfyUI" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline="Substitute couldn't download ComfyUI",
                user_message=("Setup couldn't download the ComfyUI files it needs."),
                technical_detail=technical_detail,
                remediation_steps=(
                    "Check your internet connection.",
                    "Make sure the selected folder is writable.",
                    "Then try again.",
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "Python packages" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline="Substitute couldn't finish installing ComfyUI",
                user_message=(
                    "ComfyUI was downloaded, but some of its Python packages could not be installed."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    "Check your internet connection.",
                    "Make sure security software is not blocking Python package downloads.",
                    "Then try again.",
                ),
            )
        if (
            target_mode is ComfyTargetMode.MANAGED_LOCAL
            and "required custom nodes" in technical_detail
        ):
            return OnboardingProvisioningFailure(
                headline="Substitute couldn't finish preparing ComfyUI",
                user_message=(
                    "ComfyUI was installed, but Substitute couldn't finish preparing the required node packs."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    "Check the live output for the custom-node problem.",
                    "Fix the reported issue if you can.",
                    "Then try again.",
                ),
            )
        if target_mode is ComfyTargetMode.MANAGED_LOCAL:
            return OnboardingProvisioningFailure(
                headline="Substitute couldn't finish setting up ComfyUI",
                user_message=(
                    "Setup stopped before ComfyUI was ready. Read the live output "
                    "below, fix the problem it mentions, and then try again."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    "Make sure the selected folder is writable and has enough free space.",
                    "Keep your internet connection available while setup runs.",
                    "If the folder already contains a partial install, delete it before retrying.",
                ),
            )
        if target_mode is ComfyTargetMode.ATTACHED_LOCAL:
            if isinstance(error, ComfyPythonResolutionError):
                return OnboardingFlowService._attached_python_resolution_failure(error)
            if "could not be found" in technical_detail.lower():
                return OnboardingProvisioningFailure(
                    headline="The ComfyUI folder couldn't be found",
                    user_message=(
                        "Substitute couldn't find the local ComfyUI folder you entered."
                    ),
                    technical_detail=technical_detail,
                    remediation_steps=(
                        "Check that the folder still exists.",
                        "Choose the folder that contains ComfyUI's main.py file.",
                        "Then try again.",
                    ),
                )
            if "did not respond at" in technical_detail.lower():
                return OnboardingFlowService._endpoint_unreachable_failure(
                    draft=draft,
                    target_mode=target_mode,
                    technical_detail=technical_detail,
                )
            return OnboardingProvisioningFailure(
                headline="Substitute could not prepare this local ComfyUI setup",
                user_message=(
                    "Review the existing ComfyUI folder and local address, then try again."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    "Make sure the folder points to the ComfyUI setup you want Substitute to launch.",
                    "Confirm the local host and port are free for Substitute to use.",
                ),
            )
        return OnboardingProvisioningFailure(
            headline="Substitute could not finish this remote connection setup",
            user_message=("Review the remote address details, then try again."),
            technical_detail=technical_detail,
            remediation_steps=(
                "Confirm the remote host and port are correct.",
                "Make sure this computer can reach the remote ComfyUI server.",
            ),
        )

    @staticmethod
    def _attached_python_resolution_failure(
        error: ComfyPythonResolutionError,
    ) -> OnboardingProvisioningFailure:
        """Translate typed Comfy Python failures into specific recovery guidance."""

        if error.reason is ComfyPythonResolutionFailure.WORKSPACE_INVALID:
            return OnboardingProvisioningFailure(
                headline="Choose the folder that contains ComfyUI",
                user_message=(
                    "The selected folder is not a complete ComfyUI installation."
                ),
                technical_detail=error.detail,
                remediation_steps=(
                    "Go back to My Current ComfyUI.",
                    "Choose the folder that contains ComfyUI's main.py file.",
                    "Then run setup again.",
                ),
            )
        if error.reason is ComfyPythonResolutionFailure.AMBIGUOUS:
            return OnboardingProvisioningFailure(
                headline="Choose which Python this ComfyUI setup uses",
                user_message=(
                    "Substitute found more than one working Python environment and "
                    "needs you to choose the one ComfyUI uses."
                ),
                technical_detail=error.detail,
                remediation_steps=(
                    "Go back to My Current ComfyUI.",
                    "Use Browse beside Python executable and choose this ComfyUI setup's Python.",
                    "Then run setup again.",
                ),
            )
        if error.reason is ComfyPythonResolutionFailure.EXPLICIT_SELECTION_INVALID:
            return OnboardingProvisioningFailure(
                headline="Choose a working Python for this ComfyUI setup",
                user_message=(
                    "The Python executable you selected could not run this ComfyUI "
                    "installation."
                ),
                technical_detail=error.detail,
                remediation_steps=(
                    "Go back to My Current ComfyUI.",
                    "Use Browse beside Python executable and choose the Python ComfyUI actually uses.",
                    "Then run setup again.",
                ),
            )
        return OnboardingProvisioningFailure(
            headline="Choose the Python this ComfyUI setup uses",
            user_message=(
                "Substitute could not identify a working Python environment "
                "automatically."
            ),
            technical_detail=error.detail,
            remediation_steps=(
                "Go back to My Current ComfyUI.",
                "Use Browse beside Python executable and choose the Python ComfyUI uses.",
                "Then run setup again.",
            ),
        )

    @staticmethod
    def _endpoint_unreachable_failure(
        *,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
        technical_detail: str,
    ) -> OnboardingProvisioningFailure:
        """Build a user-facing failure for an unreachable Comfy endpoint."""

        endpoint_label = f"{draft.endpoint_host}:{draft.endpoint_port}"
        if target_mode is ComfyTargetMode.ATTACHED_LOCAL:
            return OnboardingProvisioningFailure(
                headline="Substitute couldn't reach your ComfyUI setup",
                user_message=(
                    "Substitute couldn't connect to the local ComfyUI address you entered."
                ),
                technical_detail=technical_detail,
                remediation_steps=(
                    f"Make sure ComfyUI is running at {endpoint_label}.",
                    "Check that the host and port match your ComfyUI window.",
                    "Then try again.",
                ),
            )
        return OnboardingProvisioningFailure(
            headline="Substitute couldn't reach the remote ComfyUI server",
            user_message=(
                "Substitute couldn't connect to the remote ComfyUI address you entered."
            ),
            technical_detail=technical_detail,
            remediation_steps=(
                f"Make sure a ComfyUI server is running at {endpoint_label}.",
                "Check that the host and port are correct from this computer.",
                "Then try again.",
            ),
        )

    @staticmethod
    def _remediation_step_for_issue(
        *,
        issue: ReadinessIssue,
        draft: OnboardingDraftState,
        target_mode: ComfyTargetMode,
    ) -> str:
        """Return one short user-facing next step for a readiness issue."""

        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_INSTALLED:
            return "Run setup again so Substitute can finish installing ComfyUI."
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_LAUNCHABLE:
            return (
                "Run setup again after fixing the files mentioned in the live output."
            )
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NODEPACKS_MISSING:
            return "Run setup again so Substitute can install its required Comfy nodepacks."
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_VALIDATED:
            return "Run setup again so Substitute can validate the managed backend on this machine."
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_FOREIGN_LISTENER_BLOCKED:
            return f"Stop the other process using {draft.endpoint_host}:{draft.endpoint_port}, or choose a different managed port."
        if issue.code is ReadinessIssueCode.MANAGED_WORKSPACE_BACKEND_INVALID:
            return "Run setup again so Substitute can install the correct backend for the detected hardware."
        if issue.code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING:
            return "Check that the ComfyUI folder still exists, or clear that field."
        if issue.code is ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE:
            return f"Make sure ComfyUI is running at {draft.endpoint_host}:{draft.endpoint_port}."
        if target_mode is ComfyTargetMode.MANAGED_LOCAL:
            return "Check the managed ComfyUI folder and try again."
        return "Review the connection details and try again."


def _is_storage_exhaustion_detail(detail: str) -> bool:
    """Return whether an install failure describes exhausted temp storage."""

    normalized = detail.casefold()
    return any(
        marker in normalized
        for marker in (
            "managedinstallstorageerror",
            "temporary install space",
            "no space left on device",
            "oserror(28",
            "[errno 28]",
            "there is not enough space on the disk",
        )
    )
