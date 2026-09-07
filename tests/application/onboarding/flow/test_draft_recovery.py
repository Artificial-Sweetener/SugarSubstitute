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

from datetime import UTC, datetime
from pathlib import Path


from substitute.application.onboarding import (
    OnboardingDraftState,
    OnboardingFlowService,
)
from substitute.domain.comfy_environment import ComfyModelRootStatus
from substitute.domain.generation import (
    OutputOrganizationSettings,
    OutputPreferences,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    ManagedRuntimeConfiguration,
    ReadinessAssessment,
    SetupTransaction,
    SetupTransactionMode,
    SetupTransactionStatus,
)

from .preference_support import (
    _Bundle,
    _CivitaiCredentialService,
    _ExternalModelLibraryConfigurator,
    _ModelRootProvider,
    _OutputPreferenceService,
)
from .runtime_support import (
    _FakeRuntimeLaunchService,
    _FakeSetupTransactionService,
    _StaticManagedRuntimeService,
    _StaticOnboardingService,
    _StaticReadinessService,
    _build_context,
    _python_binding,
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
    webui_models = tmp_path / "WebUI" / "models"
    custom_outputs = tmp_path / "Images"
    external_models = _ExternalModelLibraryConfigurator(models_root=webui_models)
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
                configured_model_root=str(tmp_path / "Models"),
                active_model_root=str(tmp_path / "Models"),
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
        external_model_library_configurator=external_models,
    )

    draft = service.load_draft(tmp_path)

    assert draft.managed_model_root == webui_models
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


def test_flow_service_preserves_explicit_attached_choice_during_first_run(
    tmp_path: Path,
) -> None:
    """First-run setup must not reinterpret an explicit attached-local choice."""

    context = _build_context(tmp_path, ComfyTargetMode.MANAGED_LOCAL)
    transaction_service = _FakeSetupTransactionService(context)
    provisioned_workspaces: list[Path] = []
    workspace = context.comfy_target.workspace_path
    assert workspace is not None

    def _reject_managed_provisioning(**kwargs: object) -> Path:
        """Fail if first-run attached setup enters managed provisioning."""

        _ = kwargs
        raise AssertionError("Explicit attached-local choice used managed setup.")

    def _record_attached_provisioning(**kwargs: object) -> ComfyPythonBinding:
        """Record the attached workspace selected during first-run setup."""

        selected_workspace = kwargs["workspace"]
        assert isinstance(selected_workspace, Path)
        provisioned_workspaces.append(selected_workspace)
        return _python_binding(selected_workspace)

    service = OnboardingFlowService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=transaction_service,
        ),
        managed_workspace_provisioner=_reject_managed_provisioning,
        attached_workspace_provisioner=_record_attached_provisioning,
        entrypoint_path=tmp_path / "main.py",
        transaction_mode=SetupTransactionMode.FIRST_RUN,
    )

    service.provision(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
            endpoint_host=context.comfy_target.endpoint.host,
            endpoint_port=context.comfy_target.endpoint.port,
            managed_workspace_path=tmp_path / "unused-managed",
            attached_workspace_path=workspace,
            attached_python_binding=_python_binding(workspace),
        ),
        restart_required=False,
        on_status=lambda message: None,
        on_log=lambda line: None,
    )

    assert provisioned_workspaces == [workspace]
    assert transaction_service.transaction is not None
    assert transaction_service.transaction.target is not None
    assert transaction_service.transaction.target.mode is ComfyTargetMode.ATTACHED_LOCAL
