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

"""Tests for onboarding flow failure mapping and readiness-driven recovery copy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sugarsubstitute_shared.localization import render_source_application_text
from sugarsubstitute_shared.windows_long_paths import (
    ExternalLongPathCompatibilityError,
    WindowsPathComponentTooLongError,
)

import pytest

from substitute.application.onboarding import (
    OnboardingCredentialDraft,
    OnboardingDraftState,
    OnboardingFlowService,
    OnboardingPreferenceSetupDraft,
    OnboardingProvisioningFailure,
)
from substitute.domain.civitai import (
    CivitaiPreferences,
    default_civitai_preferences,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_environment import ComfyModelRootStatus
from substitute.domain.danbooru.preferences import (
    DanbooruPreferences,
    default_danbooru_preferences,
)
from substitute.domain.generation import (
    OutputOrganizationSettings,
    OutputPreferences,
    default_output_preferences,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonResolutionError,
    ComfyPythonResolutionFailure,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ManagedRuntimeConfiguration,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
    SetupTransaction,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.domain.prompt import PromptEditorPreferences
from substitute.infrastructure.persistence.file_prompt_editor_preference_repository import (
    _default_preferences as _default_prompt_preferences,
)


@dataclass(frozen=True)
class _FakeRuntimeLaunchService:
    """Return one deterministic runtime launch command for flow tests."""

    def provision_draft(
        self,
        configuration: RuntimeConfiguration | None = None,
    ) -> RuntimeConfiguration:
        """Return a ready runtime configuration without side effects."""

        assert configuration is not None
        return configuration

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return a stable launch command."""

        _ = configuration
        return ["python", str(entrypoint_path)]


@dataclass(frozen=True)
class _StaticReadinessService:
    """Return one deterministic readiness assessment for flow tests."""

    assessment: ReadinessAssessment

    def assess(self) -> ReadinessAssessment:
        """Return the configured readiness assessment."""

        return self.assessment

    def assess_candidate(
        self,
        *,
        installation: InstallationConfiguration,
        runtime: RuntimeConfiguration,
        target: ComfyTargetConfiguration,
        managed_runtime: ManagedRuntimeConfiguration | None = None,
    ) -> ReadinessAssessment:
        """Return the configured readiness assessment for pending state."""

        _ = installation, runtime, target, managed_runtime
        return self.assessment


@dataclass(frozen=True)
class _StaticOnboardingService:
    """Return deterministic install/runtime/target context for flow tests."""

    context: InstallationContext

    def load_draft_context(self) -> InstallationContext:
        """Return the deterministic onboarding context."""

        return self.context

    def configure_managed_local(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Return a managed-local context using the supplied endpoint and workspace."""

        _ = endpoint, workspace_path
        return self.context

    def build_managed_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Return a managed-local pending context."""

        return InstallationContext(
            installation=self.context.installation,
            runtime=self.context.runtime,
            comfy_target=ComfyTargetConfiguration(
                mode=ComfyTargetMode.MANAGED_LOCAL,
                endpoint=endpoint,
                workspace_path=workspace_path,
                install_owned=True,
                launch_owned=True,
            ),
        )

    def configure_attached_local(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Return an attached-local context using the supplied endpoint and workspace."""

        _ = endpoint, workspace_path
        return self.context

    def build_attached_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
        python_binding: ComfyPythonBinding | None = None,
    ) -> InstallationContext:
        """Return an attached-local pending context."""

        return InstallationContext(
            installation=self.context.installation,
            runtime=self.context.runtime,
            comfy_target=ComfyTargetConfiguration(
                mode=ComfyTargetMode.ATTACHED_LOCAL,
                endpoint=endpoint,
                workspace_path=workspace_path,
                install_owned=False,
                launch_owned=True,
                python_binding=python_binding,
            ),
        )

    def configure_remote(self, *, endpoint: ComfyEndpoint) -> InstallationContext:
        """Return a remote context using the supplied endpoint."""

        _ = endpoint
        return self.context

    def build_remote_context(self, *, endpoint: ComfyEndpoint) -> InstallationContext:
        """Return a remote pending context."""

        return InstallationContext(
            installation=self.context.installation,
            runtime=self.context.runtime,
            comfy_target=ComfyTargetConfiguration(
                mode=ComfyTargetMode.REMOTE,
                endpoint=endpoint,
                workspace_path=None,
                install_owned=False,
                launch_owned=False,
            ),
        )


@dataclass(frozen=True)
class _StaticManagedRuntimeService:
    """Return deterministic managed runtime selection for flow tests."""

    configuration: ManagedRuntimeConfiguration = ManagedRuntimeConfiguration(
        detected_platform="windows",
        detected_accelerator="nvidia",
        install_target="windows_nvidia",
        python_version="3.13",
        comfy_channel="latest",
        backend_policy="cuda_cu130",
    )

    def load_persisted(self) -> ManagedRuntimeConfiguration:
        """Return the deterministic managed runtime configuration."""

        return self.configuration

    def load_draft_configuration(self) -> ManagedRuntimeConfiguration:
        """Return the deterministic onboarding-safe configuration."""

        return self.configuration

    def detect_and_select(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return the deterministic managed runtime configuration."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        return self.configuration

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return the deterministic managed runtime configuration."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        return self.configuration


@dataclass
class _FakeSetupTransactionService:
    """Record setup transaction calls for flow tests."""

    context: InstallationContext
    transaction: SetupTransaction | None = None
    failure_recorded: bool = False

    def load(self) -> SetupTransaction | None:
        """Return the active fake transaction."""

        return self.transaction

    def begin(
        self,
        *,
        mode: SetupTransactionMode,
        options: object | None = None,
    ) -> SetupTransaction:
        """Create a fake pending transaction."""

        _ = options
        now = datetime.now(UTC)
        self.transaction = SetupTransaction(
            schema_version=1,
            transaction_id="transaction-id",
            mode=mode,
            status=SetupTransactionStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        return self.transaction

    def update_status(
        self,
        transaction_id: str,
        status: SetupTransactionStatus,
    ) -> SetupTransaction:
        """Update the fake transaction status."""

        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        self.transaction = SetupTransaction(
            schema_version=self.transaction.schema_version,
            transaction_id=self.transaction.transaction_id,
            mode=self.transaction.mode,
            status=status,
            created_at=self.transaction.created_at,
            updated_at=self.transaction.updated_at,
            installation=self.transaction.installation,
            runtime=self.transaction.runtime,
            target=self.transaction.target,
            managed_runtime=self.transaction.managed_runtime,
        )
        return self.transaction

    def record_installation(
        self,
        transaction_id: str,
        configuration: InstallationConfiguration,
    ) -> SetupTransaction:
        """Record pending installation configuration."""

        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        self.transaction = SetupTransaction(
            **{**self.transaction.__dict__, "installation": configuration}
        )
        return self.transaction

    def record_runtime(
        self,
        transaction_id: str,
        configuration: RuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending runtime configuration."""

        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        self.transaction = SetupTransaction(
            **{**self.transaction.__dict__, "runtime": configuration}
        )
        return self.transaction

    def record_target(
        self,
        transaction_id: str,
        configuration: ComfyTargetConfiguration,
    ) -> SetupTransaction:
        """Record pending target configuration."""

        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        self.transaction = SetupTransaction(
            **{**self.transaction.__dict__, "target": configuration}
        )
        return self.transaction

    def record_managed_runtime(
        self,
        transaction_id: str,
        configuration: ManagedRuntimeConfiguration,
    ) -> SetupTransaction:
        """Record pending managed runtime configuration."""

        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        self.transaction = SetupTransaction(
            **{**self.transaction.__dict__, "managed_runtime": configuration}
        )
        return self.transaction

    def record_failure(self, transaction_id: str, failure: object) -> SetupTransaction:
        """Record that the flow attempted to persist a failure."""

        _ = failure
        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        self.failure_recorded = True
        return self.transaction

    def commit(self, transaction_id: str) -> InstallationContext:
        """Return the committed fake context."""

        assert self.transaction is not None
        assert transaction_id == self.transaction.transaction_id
        return self.context


@dataclass
class _ModelRootProvider:
    """Return deterministic BackEnd-owned model-root state for flow tests."""

    status: ComfyModelRootStatus | None = None

    def load(
        self,
        _target: ComfyTargetConfiguration,
    ) -> ComfyModelRootStatus | None:
        """Return the configured host state."""

        return self.status


@dataclass
class _OutputPreferenceService:
    """Return deterministic output preferences for flow tests."""

    preferences: OutputPreferences = field(default_factory=default_output_preferences)
    effective_root: Path = Path("Substitute/user/outputs")

    def load_preferences(self) -> OutputPreferences:
        """Return default output organization preferences."""

        return self.preferences

    def effective_output_root(
        self,
        preferences: OutputPreferences | None = None,
    ) -> Path:
        """Return a deterministic effective output root."""

        _ = preferences
        return self.effective_root


class _PromptPreferenceService:
    """Return deterministic prompt editor preferences for flow tests."""

    def load_preferences(self) -> PromptEditorPreferences:
        """Return default prompt editor preferences."""

        return _default_prompt_preferences()


class _DanbooruPreferenceService:
    """Return deterministic Danbooru preferences for flow tests."""

    def load_preferences(self) -> DanbooruPreferences:
        """Return default Danbooru preferences."""

        return default_danbooru_preferences()


class _CivitaiPreferenceService:
    """Return deterministic CivitAI preferences for flow tests."""

    def load_preferences(self) -> CivitaiPreferences:
        """Return default CivitAI preferences."""

        return default_civitai_preferences()


@dataclass
class _CivitaiCredentialService:
    """Return deterministic CivitAI credential status for flow tests."""

    configured: bool = False

    def has_api_key(self) -> bool:
        """Return whether the fake credential store has a key."""

        return self.configured


@dataclass
class _PreferenceSetupService:
    """Record onboarding preference and credential saves for flow tests."""

    saved_preferences: list[OnboardingPreferenceSetupDraft] = field(
        default_factory=list
    )
    saved_credentials: list[OnboardingCredentialDraft] = field(default_factory=list)

    def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
        """Record non-secret onboarding preferences."""

        self.saved_preferences.append(draft)

    def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
        """Record optional onboarding credentials."""

        self.saved_credentials.append(draft)


@dataclass(frozen=True)
class _Bundle:
    """Provide the service bundle consumed by the onboarding flow service."""

    onboarding_service: _StaticOnboardingService
    runtime_service: _FakeRuntimeLaunchService
    readiness_service: _StaticReadinessService
    managed_runtime_service: _StaticManagedRuntimeService
    setup_transaction_service: _FakeSetupTransactionService
    model_root_provider: _ModelRootProvider = field(default_factory=_ModelRootProvider)
    output_preference_service: _OutputPreferenceService = field(
        default_factory=_OutputPreferenceService
    )
    prompt_editor_preference_service: _PromptPreferenceService = field(
        default_factory=_PromptPreferenceService
    )
    danbooru_preference_service: _DanbooruPreferenceService = field(
        default_factory=_DanbooruPreferenceService
    )
    civitai_preference_service: _CivitaiPreferenceService = field(
        default_factory=_CivitaiPreferenceService
    )
    civitai_credential_service: _CivitaiCredentialService = field(
        default_factory=_CivitaiCredentialService
    )
    preference_setup_service: _PreferenceSetupService = field(
        default_factory=_PreferenceSetupService
    )


def _build_context(tmp_path: Path, mode: ComfyTargetMode) -> InstallationContext:
    """Build one deterministic installation context for flow tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=mode,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=installation.default_managed_comfy_dir
            if mode is ComfyTargetMode.MANAGED_LOCAL
            else None,
            install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
            launch_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        ),
    )


def test_flow_service_load_draft_prefers_pending_transaction_state(
    tmp_path: Path,
) -> None:
    """Draft loading should prefill from interrupted pending setup state."""

    active_context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    pending_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="10.0.0.5", port=8189),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    pending_runtime = active_context.runtime
    pending_runtime_service = _FakeSetupTransactionService(active_context)
    now = datetime.now(UTC)
    pending_runtime_service.transaction = SetupTransaction(
        schema_version=1,
        transaction_id="transaction-id",
        mode=SetupTransactionMode.REPAIR,
        status=SetupTransactionStatus.TARGET_PROVISIONING,
        created_at=now,
        updated_at=now,
        installation=active_context.installation,
        runtime=pending_runtime,
        target=pending_target,
        managed_runtime=ManagedRuntimeConfiguration(
            detected_platform="windows",
            detected_accelerator="nvidia",
            install_target="windows_nvidia",
        ),
    )
    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(active_context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=pending_runtime_service,
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        entrypoint_path=tmp_path / "main.py",
    )

    draft = service.load_draft(tmp_path)

    assert draft.target_mode == ComfyTargetMode.REMOTE.value
    assert draft.endpoint_host == "10.0.0.5"
    assert draft.endpoint_port == 8189
    assert draft.selected_install_target == "windows_nvidia"


def test_flow_service_load_draft_includes_folder_and_preference_state(
    tmp_path: Path,
) -> None:
    """Draft loading should include folder defaults and safe helper preferences."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    custom_models = tmp_path / "Models"
    custom_outputs = tmp_path / "Images"
    bundle = _Bundle(
        onboarding_service=_StaticOnboardingService(context),
        runtime_service=_FakeRuntimeLaunchService(),
        readiness_service=_StaticReadinessService(
            ReadinessAssessment(route=BootstrapRoute.READY, issues=())
        ),
        managed_runtime_service=_StaticManagedRuntimeService(),
        setup_transaction_service=_FakeSetupTransactionService(context),
        model_root_provider=_ModelRootProvider(
            status=ComfyModelRootStatus(
                schema_version=1,
                default_model_root=str(context.managed_comfy_dir / "models"),
                configured_model_root=str(custom_models),
                active_model_root=str(custom_models),
                uses_default=False,
                restart_required=False,
            )
        ),
        output_preference_service=_OutputPreferenceService(
            preferences=OutputPreferences(
                organization=OutputOrganizationSettings(output_root=custom_outputs)
            ),
            effective_root=custom_outputs,
        ),
        civitai_credential_service=_CivitaiCredentialService(configured=True),
    )
    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: bundle,
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        entrypoint_path=tmp_path / "main.py",
    )

    draft = service.load_draft(tmp_path)

    assert draft.managed_model_root == custom_models
    assert draft.managed_model_root_uses_default is False
    assert draft.output_root == custom_outputs
    assert draft.output_root_uses_default is False
    assert draft.danbooru_tag_help_enabled is True
    assert draft.civitai_safe_thumbnails_enabled is True
    assert draft.danbooru_image_rating_policy == "safe_only"
    assert draft.civitai_thumbnail_safety_policy == "sfw_only"
    assert draft.civitai_api_key_configured is True


def test_flow_service_recovers_stale_attached_retry_to_managed_local(
    tmp_path: Path,
) -> None:
    """Retrying an already-open repair window should not keep stale attached mode."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    provisioned_workspaces: list[Path] = []

    def _record_provisioned_workspace(**kwargs: object) -> Path:
        """Record the workspace passed to managed provisioning."""

        workspace = kwargs["workspace"]
        assert isinstance(workspace, Path)
        provisioned_workspaces.append(workspace)
        return tmp_path / "unused"

    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=_record_provisioned_workspace,
        entrypoint_path=tmp_path / "main.py",
    )

    result = service.provision(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "wrong",
            attached_workspace_path=context.comfy_target.workspace_path,
        ),
        restart_required=False,
        on_status=lambda message: None,
        on_log=lambda line: None,
    )

    assert result.context.comfy_target.mode is ComfyTargetMode.MANAGED_LOCAL
    assert provisioned_workspaces == [context.comfy_target.workspace_path]


def test_flow_service_saves_preferences_model_root_and_credentials(
    tmp_path: Path,
) -> None:
    """Provisioning should persist onboarding choices through their owners."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    preference_setup = _PreferenceSetupService()
    bundle = _Bundle(
        onboarding_service=_StaticOnboardingService(context),
        runtime_service=_FakeRuntimeLaunchService(),
        readiness_service=_StaticReadinessService(
            ReadinessAssessment(route=BootstrapRoute.READY, issues=())
        ),
        managed_runtime_service=_StaticManagedRuntimeService(),
        setup_transaction_service=_FakeSetupTransactionService(context),
        preference_setup_service=preference_setup,
    )
    provisioner_kwargs: list[dict[str, object]] = []

    def _record_provisioning(**kwargs: object) -> Path:
        """Record managed provisioning arguments."""

        provisioner_kwargs.append(kwargs)
        return tmp_path / "unused"

    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: bundle,
        managed_workspace_provisioner=_record_provisioning,
        entrypoint_path=tmp_path / "main.py",
    )
    custom_models = tmp_path / "Models"
    custom_outputs = tmp_path / "Images"
    logs: list[str] = []

    service.provision(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=context.managed_comfy_dir,
            attached_workspace_path=None,
            managed_model_root=custom_models,
            managed_model_root_uses_default=False,
            output_root=custom_outputs,
            output_root_uses_default=False,
            danbooru_tag_help_enabled=False,
            danbooru_safe_previews_enabled=True,
            danbooru_image_rating_policy="safe_and_questionable",
            civitai_model_help_enabled=False,
            civitai_downloads_enabled=False,
            civitai_safe_thumbnails_enabled=True,
            civitai_thumbnail_safety_policy="allow_soft",
        ),
        credential_draft=OnboardingCredentialDraft("civitai-secret"),
        restart_required=False,
        on_status=lambda message: None,
        on_log=logs.append,
    )

    assert preference_setup.saved_preferences == [
        OnboardingPreferenceSetupDraft(
            output_root=custom_outputs,
            danbooru_tag_help_enabled=False,
            danbooru_safe_previews_enabled=True,
            danbooru_image_rating_policy="safe_and_questionable",
            civitai_model_help_enabled=False,
            civitai_downloads_enabled=False,
            civitai_safe_thumbnails_enabled=True,
            civitai_thumbnail_safety_policy="allow_soft",
        )
    ]
    assert preference_setup.saved_credentials == [
        OnboardingCredentialDraft("civitai-secret")
    ]
    assert provisioner_kwargs[0]["managed_model_root"] == custom_models
    assert provisioner_kwargs[0]["configure_model_root"] is True
    assert provisioner_kwargs[0]["refresh_core_nodepacks"] == frozenset(CoreNodepackId)
    assert provisioner_kwargs[0]["installer_temp_root"] == (
        tmp_path / "runtime" / "installer-temp" / "managed-comfy" / "transaction-id"
    )
    assert "civitai-secret" not in "\n".join(logs)


def test_flow_service_prepares_existing_local_comfy_without_endpoint_probe(
    tmp_path: Path,
) -> None:
    """Existing-local setup should prepare the folder without requiring a live endpoint."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    provisioner_kwargs: list[dict[str, object]] = []
    workspace = tmp_path / "ExternalComfy"
    custom_models = tmp_path / "SharedModels"

    def _record_provisioning(**kwargs: object) -> ComfyPythonBinding:
        """Record existing-local workspace preparation arguments."""

        provisioner_kwargs.append(kwargs)
        return _python_binding(tmp_path / "ExternalComfy")

    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        attached_workspace_provisioner=_record_provisioning,
        entrypoint_path=tmp_path / "main.py",
    )
    result = service.provision(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=workspace,
            attached_python_binding=_python_binding(workspace),
            managed_model_root=custom_models,
            managed_model_root_uses_default=False,
        ),
        restart_required=False,
        on_status=lambda message: None,
        on_log=lambda line: None,
    )

    assert result.context is context
    assert provisioner_kwargs[0]["workspace"] == workspace
    assert provisioner_kwargs[0]["python_binding"] == _python_binding(workspace)
    assert provisioner_kwargs[0]["model_root"] == custom_models
    assert provisioner_kwargs[0]["configure_model_root"] is True


def test_flow_service_rejects_existing_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Existing-local setup should require a ComfyUI folder before provisioning."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        attached_workspace_provisioner=lambda **kwargs: _python_binding(tmp_path),
        entrypoint_path=tmp_path / "main.py",
    )

    with pytest.raises(OnboardingProvisioningFailure) as error:
        service.provision(
            draft=OnboardingDraftState(
                installation_root=tmp_path,
                target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
                endpoint_host="127.0.0.1",
                endpoint_port=8188,
                managed_workspace_path=tmp_path / "comfyui",
                attached_workspace_path=None,
            ),
            restart_required=False,
            on_status=lambda message: None,
            on_log=lambda line: None,
        )

    assert error.value.headline == "Choose your existing ComfyUI folder"
    assert "needs the folder" in error.value.user_message


def test_flow_service_maps_missing_attached_workspace_to_user_copy(
    tmp_path: Path,
) -> None:
    """Attached-local missing-folder readiness should explain how to recover."""

    context = _build_context(tmp_path, ComfyTargetMode.ATTACHED_LOCAL)
    missing_workspace = tmp_path / "missing-comfyui"
    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(
                    route=BootstrapRoute.REPAIR,
                    issues=(
                        ReadinessIssue(
                            code=ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING,
                            summary="The saved ComfyUI folder could not be found.",
                            detail=(
                                "Attached ComfyUI folder does not exist: "
                                f"{missing_workspace}"
                            ),
                        ),
                    ),
                )
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=lambda **kwargs: tmp_path / "unused",
        attached_workspace_provisioner=lambda **kwargs: _python_binding(tmp_path),
        entrypoint_path=tmp_path / "main.py",
    )

    with pytest.raises(OnboardingProvisioningFailure) as error:
        service.provision(
            draft=OnboardingDraftState(
                installation_root=tmp_path,
                target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
                endpoint_host="127.0.0.1",
                endpoint_port=8190,
                managed_workspace_path=tmp_path / "comfyui",
                attached_workspace_path=missing_workspace,
                attached_python_binding=_python_binding(missing_workspace),
            ),
            restart_required=False,
            on_status=lambda message: None,
            on_log=lambda line: None,
        )

    assert error.value.headline == "The ComfyUI folder couldn't be found"
    assert "local ComfyUI folder you entered" in error.value.user_message
    assert "contains ComfyUI's main.py" in error.value.remediation_steps[1]


def _python_binding(root: Path) -> ComfyPythonBinding:
    """Return deterministic verified Python evidence for flow tests."""

    executable = root / ".venv" / "Scripts" / "python.exe"
    return ComfyPythonBinding(
        executable=executable,
        version="3.13",
        architecture="AMD64",
        prefix=executable.parent.parent,
        base_prefix=executable.parent.parent,
        source=ComfyPythonSelectionSource.DISCOVERED,
    )


def test_flow_service_maps_storage_exhaustion_to_temp_space_copy(
    tmp_path: Path,
) -> None:
    """Storage exhaustion should produce install-drive temporary-space guidance."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=RuntimeError("OSError: [Errno 28] No space left on device"),
    )

    assert failure.headline == "Substitute ran out of temporary install space"
    assert str(tmp_path) in render_source_application_text(failure.remediation_steps[0])
    assert "Python packages" in failure.user_message


def test_flow_service_maps_external_long_path_failure_to_actionable_copy(
    tmp_path: Path,
) -> None:
    """A known third-party path failure should name the boundary and both remedies."""

    long_path = tmp_path / "deep" / "ComfyUI"
    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=long_path,
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=ExternalLongPathCompatibilityError(
            component="7-Zip",
            path=long_path,
            detail="[WinError 206] The filename or extension is too long",
        ),
    )

    assert failure.headline == "A Windows component could not use this long path"
    assert "7-Zip" in render_source_application_text(failure.user_message)
    assert "shorter folder" in failure.remediation_steps[0]
    assert "enable Win32 long paths" in failure.remediation_steps[1]


def test_flow_service_maps_component_limit_to_specific_copy(tmp_path: Path) -> None:
    """An impossible individual name should not be reported as a total-path failure."""

    offending_name = "x" * 256
    path = tmp_path / offending_name
    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=path,
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=WindowsPathComponentTooLongError(
            path=path,
            component=offending_name,
        ),
    )

    assert failure.headline == "A file or folder name is too long for Windows"
    assert "255 characters" in failure.user_message
    assert str(path) in render_source_application_text(failure.remediation_steps[0])


@pytest.mark.parametrize(
    ("reason", "expected_headline"),
    (
        (
            ComfyPythonResolutionFailure.WORKSPACE_INVALID,
            "Choose the folder that contains ComfyUI",
        ),
        (
            ComfyPythonResolutionFailure.AUTOMATIC_DISCOVERY_FAILED,
            "Choose the Python this ComfyUI setup uses",
        ),
        (
            ComfyPythonResolutionFailure.AMBIGUOUS,
            "Choose which Python this ComfyUI setup uses",
        ),
        (
            ComfyPythonResolutionFailure.EXPLICIT_SELECTION_INVALID,
            "Choose a working Python for this ComfyUI setup",
        ),
    ),
)
def test_flow_service_maps_python_resolution_failures_to_browse_guidance(
    tmp_path: Path,
    reason: ComfyPythonResolutionFailure,
    expected_headline: str,
) -> None:
    """Attached Python failures should tell the user where to make the choice."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=tmp_path / "ExternalComfy",
        ),
        target_mode=ComfyTargetMode.ATTACHED_LOCAL,
        error=ComfyPythonResolutionError(reason, "probe detail"),
    )

    assert failure.headline == expected_headline
    if reason is ComfyPythonResolutionFailure.WORKSPACE_INVALID:
        assert "main.py" in failure.remediation_steps[1]
    else:
        assert "Browse beside Python executable" in failure.remediation_steps[1]


@pytest.mark.parametrize(
    ("technical_detail", "expected_headline"),
    (
        (
            "Substitute couldn't download ComfyUI into the selected folder.",
            "Substitute couldn't download ComfyUI",
        ),
        (
            "Substitute couldn't finish installing ComfyUI's Python packages.",
            "Substitute couldn't finish installing ComfyUI",
        ),
        (
            "Substitute couldn't finish preparing the required custom nodes.",
            "Substitute couldn't finish preparing ComfyUI",
        ),
    ),
)
def test_flow_service_maps_specific_managed_failures_to_specific_copy(
    tmp_path: Path,
    technical_detail: str,
    expected_headline: str,
) -> None:
    """Managed install failure classes should not collapse into one generic message."""

    failure = OnboardingFlowService._build_provisioning_failure(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=None,
        ),
        target_mode=ComfyTargetMode.MANAGED_LOCAL,
        error=RuntimeError(technical_detail),
    )

    assert failure.headline == expected_headline
    assert "try again" in failure.remediation_steps[-1].lower()
