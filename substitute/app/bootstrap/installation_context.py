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

"""Build pure installation-context and onboarding service helpers for bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from substitute.application.onboarding.readiness_service import (
    BootstrapReadinessService,
)
from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.installation_service import InstallationService
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.onboarding.onboarding_service import OnboardingService
from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.application.onboarding.setup_transaction_service import (
    SetupTransactionService,
)
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.runtime_compatibility import (
    EndpointBackendCompatibilityChecker,
)
from substitute.application.runtime_mode import ApplicationRuntimeModeService
from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
)
from substitute.domain.onboarding.setup_transaction_models import SetupTransaction
from substitute.infrastructure.onboarding import (
    FileComfyTargetConfigurationRepository,
    FileInstallationConfigurationRepository,
    FileManagedRuntimeConfigurationRepository,
    FileRuntimeConfigurationRepository,
    FileSetupTransactionRepository,
    LauncherManagedRuntimeProvisioner,
    SubstituteRuntimeProvisioner,
)
from substitute.infrastructure.comfy.managed_runtime_selection_policy import (
    HardwareAwareManagedRuntimeSelectionPolicy,
)
from substitute.infrastructure.comfy.managed_model_root import (
    ManagedModelRootStore,
)
from substitute.infrastructure.onboarding.readiness_checks import (
    FileSystemReadinessChecks,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

if TYPE_CHECKING:
    from substitute.application.civitai import (
        CivitaiCredentialService,
        CivitaiPreferenceService,
    )
    from substitute.application.danbooru import DanbooruPreferenceService
    from substitute.application.generation import OutputOrganizationPreferenceService
    from substitute.application.onboarding.preference_setup_service import (
        OnboardingPreferenceSetupService,
    )
    from substitute.application.prompt_editor import PromptEditorPreferenceService

_LOGGER = get_logger("app.bootstrap.installation_context")

_INSTALL_ROOT_ENV = "SUGARSUBSTITUTE_INSTALL_ROOT"


@dataclass(frozen=True)
class OnboardingServiceBundle:
    """Bundle onboarding services composed for one install root."""

    installation_service: InstallationService
    runtime_service: RuntimeService
    comfy_target_service: ComfyTargetService
    managed_runtime_service: ManagedRuntimeService
    setup_transaction_service: SetupTransactionService
    onboarding_service: OnboardingService
    readiness_service: BootstrapReadinessService
    managed_model_path_store: ManagedModelRootStore
    output_organization_service: OutputOrganizationPreferenceService
    danbooru_preference_service: DanbooruPreferenceService
    prompt_editor_preference_service: PromptEditorPreferenceService
    civitai_preference_service: CivitaiPreferenceService
    civitai_credential_service: CivitaiCredentialService
    preference_setup_service: OnboardingPreferenceSetupService


@dataclass(frozen=True)
class StartupReadinessServiceBundle:
    """Bundle only the services needed to select the startup route."""

    readiness_service: BootstrapReadinessService


@dataclass(frozen=True)
class _CoreOnboardingServices:
    """Bundle shared onboarding services without preference stack construction."""

    installation_root: Path
    installation_configuration: InstallationConfiguration
    installation_service: InstallationService
    runtime_service: RuntimeService
    comfy_target_service: ComfyTargetService
    managed_runtime_service: ManagedRuntimeService
    setup_transaction_service: SetupTransactionService
    onboarding_service: OnboardingService
    readiness_checks: FileSystemReadinessChecks


def resolve_installation_root(explicit_root: Path | None = None) -> Path:
    """Resolve the active installation root from explicit input, env, or repo root."""

    if explicit_root is not None:
        return explicit_root.resolve()
    env_root = os.environ.get(_INSTALL_ROOT_ENV)
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[3]


def build_onboarding_service_bundle(
    explicit_root: Path | None = None,
) -> OnboardingServiceBundle:
    """Compose onboarding services for one resolved installation root."""

    core_services = _build_core_onboarding_services(explicit_root)
    managed_model_path_store = ManagedModelRootStore()
    (
        output_organization_service,
        danbooru_preference_service,
        prompt_editor_preference_service,
        civitai_preference_service,
        civitai_credential_service,
        preference_setup_service,
    ) = _build_preference_setup_services(core_services.installation_configuration)
    readiness_service = _build_readiness_service(core_services)
    return OnboardingServiceBundle(
        installation_service=core_services.installation_service,
        runtime_service=core_services.runtime_service,
        comfy_target_service=core_services.comfy_target_service,
        managed_runtime_service=core_services.managed_runtime_service,
        setup_transaction_service=core_services.setup_transaction_service,
        onboarding_service=core_services.onboarding_service,
        readiness_service=readiness_service,
        managed_model_path_store=managed_model_path_store,
        output_organization_service=output_organization_service,
        danbooru_preference_service=danbooru_preference_service,
        prompt_editor_preference_service=prompt_editor_preference_service,
        civitai_preference_service=civitai_preference_service,
        civitai_credential_service=civitai_credential_service,
        preference_setup_service=preference_setup_service,
    )


def build_startup_readiness_service_bundle(
    explicit_root: Path | None = None,
) -> StartupReadinessServiceBundle:
    """Compose only startup route readiness services for one install root."""

    return StartupReadinessServiceBundle(
        readiness_service=_build_readiness_service(
            _build_core_onboarding_services(explicit_root)
        )
    )


def _build_core_onboarding_services(
    explicit_root: Path | None = None,
) -> _CoreOnboardingServices:
    """Compose install, runtime, target, and recovery services for startup."""

    installation_root = resolve_installation_root(explicit_root)
    installation_repository = FileInstallationConfigurationRepository(installation_root)
    installation_service = InstallationService(installation_repository)
    installation_configuration = (
        installation_service.load_persisted() or installation_service.create_default()
    )
    app_layout = resolve_app_layout(installation_root)
    runtime_service = RuntimeService(
        FileRuntimeConfigurationRepository(installation_configuration),
        provisioner=(
            LauncherManagedRuntimeProvisioner(
                install_root=installation_configuration.installation_root,
                requirements_path=app_layout.requirements_path,
            )
            if app_layout.installed_payload
            else SubstituteRuntimeProvisioner(
                requirements_path=app_layout.requirements_path
            )
        ),
    )
    comfy_target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation_configuration)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(
            installation_configuration.runtime_state_dir
        ),
        selection_policy=HardwareAwareManagedRuntimeSelectionPolicy(),
    )
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(
            installation_configuration.runtime_state_dir
        ),
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=comfy_target_service,
        managed_runtime_service=managed_runtime_service,
    )
    readiness_checks = FileSystemReadinessChecks()
    _recover_legacy_attached_managed_target(
        comfy_target_service=comfy_target_service,
        managed_runtime_service=managed_runtime_service,
        setup_transaction_service=setup_transaction_service,
        checks=readiness_checks,
    )
    _discard_stale_attached_pending_for_active_managed_target(
        comfy_target_service=comfy_target_service,
        setup_transaction_service=setup_transaction_service,
    )
    onboarding_service = OnboardingService(
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=comfy_target_service,
    )
    return _CoreOnboardingServices(
        installation_root=installation_root,
        installation_configuration=installation_configuration,
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=comfy_target_service,
        managed_runtime_service=managed_runtime_service,
        setup_transaction_service=setup_transaction_service,
        onboarding_service=onboarding_service,
        readiness_checks=readiness_checks,
    )


def _build_readiness_service(
    core_services: _CoreOnboardingServices,
) -> BootstrapReadinessService:
    """Build route-readiness service from shared startup-owned services."""

    return BootstrapReadinessService(
        installation_root=core_services.installation_root,
        installation_service=core_services.installation_service,
        runtime_service=core_services.runtime_service,
        comfy_target_service=core_services.comfy_target_service,
        managed_runtime_service=core_services.managed_runtime_service,
        setup_transaction_repository=core_services.setup_transaction_service.repository,
        backend_compatibility=EndpointBackendCompatibilityChecker(
            runtime_mode=ApplicationRuntimeModeService.from_environment()
        ),
        checks=core_services.readiness_checks,
    )


def _build_preference_setup_services(
    installation_configuration: InstallationConfiguration,
) -> tuple[
    "OutputOrganizationPreferenceService",
    "DanbooruPreferenceService",
    "PromptEditorPreferenceService",
    "CivitaiPreferenceService",
    "CivitaiCredentialService",
    "OnboardingPreferenceSetupService",
]:
    """Build preference services only when the full onboarding bundle is needed."""

    from substitute.application.civitai import (
        CivitaiCredentialService,
        CivitaiPreferenceService,
    )
    from substitute.application.danbooru import DanbooruPreferenceService
    from substitute.application.generation import OutputOrganizationPreferenceService
    from substitute.application.onboarding.preference_setup_service import (
        OnboardingPreferenceSetupService,
    )
    from substitute.application.prompt_editor import PromptEditorPreferenceService
    from substitute.infrastructure.persistence.file_civitai_preference_repository import (
        FileCivitaiPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_danbooru_preference_repository import (
        FileDanbooruPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_output_organization_preference_repository import (
        FileOutputOrganizationPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_prompt_editor_preference_repository import (
        FilePromptEditorPreferenceRepository,
    )
    from substitute.infrastructure.security import build_civitai_credential_store

    output_organization_service = OutputOrganizationPreferenceService(
        FileOutputOrganizationPreferenceRepository(
            installation_configuration.user_settings_dir
        ),
        default_output_root=installation_configuration.outputs_dir,
    )
    danbooru_preference_service = DanbooruPreferenceService(
        FileDanbooruPreferenceRepository(installation_configuration.user_settings_dir)
    )
    prompt_editor_preference_service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(
            installation_configuration.user_settings_dir
        )
    )
    civitai_preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(installation_configuration.user_settings_dir)
    )
    civitai_credential_service = CivitaiCredentialService(
        build_civitai_credential_store(installation_configuration.user_settings_dir)
    )
    preference_setup_service = OnboardingPreferenceSetupService(
        output_organization_service=output_organization_service,
        danbooru_preference_service=danbooru_preference_service,
        prompt_editor_preference_service=prompt_editor_preference_service,
        civitai_preference_service=civitai_preference_service,
        civitai_credential_service=civitai_credential_service,
    )
    return (
        output_organization_service,
        danbooru_preference_service,
        prompt_editor_preference_service,
        civitai_preference_service,
        civitai_credential_service,
        preference_setup_service,
    )


def _recover_legacy_attached_managed_target(
    *,
    comfy_target_service: ComfyTargetService,
    managed_runtime_service: ManagedRuntimeService,
    setup_transaction_service: SetupTransactionService,
    checks: FileSystemReadinessChecks,
) -> None:
    """Recover old interrupted setup state that saved managed Comfy as attached-local."""

    target = comfy_target_service.load_persisted()
    if target is None or target.mode is not ComfyTargetMode.ATTACHED_LOCAL:
        return
    workspace = target.workspace_path
    if workspace is None or not _is_localhost(target.endpoint.host):
        return
    managed_runtime = managed_runtime_service.load_persisted()
    if managed_runtime is None:
        return
    if checks.is_target_endpoint_reachable(target):
        return
    if not checks.is_managed_workspace_launchable(workspace):
        return
    managed_runtime_service.save_active_configuration(
        managed_runtime.for_workspace(workspace)
    )
    recovered_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=target.endpoint,
        workspace_path=workspace,
        install_owned=True,
        launch_owned=True,
    )
    comfy_target_service.configure(recovered_target)
    _discard_matching_attached_pending_transaction(
        setup_transaction_service=setup_transaction_service,
        recovered_target=recovered_target,
    )
    log_warning(
        _LOGGER,
        "Recovered stale attached-local target as managed-local.",
        workspace=workspace,
        host=target.endpoint.host,
        port=target.endpoint.port,
    )


def _discard_matching_attached_pending_transaction(
    *,
    setup_transaction_service: SetupTransactionService,
    recovered_target: ComfyTargetConfiguration,
) -> None:
    """Discard stale pending attached-local state superseded by target recovery."""

    try:
        transaction = setup_transaction_service.load()
    except Exception as error:
        log_info(
            _LOGGER,
            "Could not load pending setup transaction during target recovery.",
            error=error,
        )
        return
    if transaction is None or not _pending_matches_recovered_target(
        transaction=transaction,
        recovered_target=recovered_target,
    ):
        return
    setup_transaction_service.discard(transaction.transaction_id)


def _discard_stale_attached_pending_for_active_managed_target(
    *,
    comfy_target_service: ComfyTargetService,
    setup_transaction_service: SetupTransactionService,
) -> None:
    """Discard stale attached-local pending state after active target recovery."""

    recovered_target = comfy_target_service.load_persisted()
    if (
        recovered_target is None
        or recovered_target.mode is not ComfyTargetMode.MANAGED_LOCAL
    ):
        return
    _discard_matching_attached_pending_transaction(
        setup_transaction_service=setup_transaction_service,
        recovered_target=recovered_target,
    )


def _pending_matches_recovered_target(
    *,
    transaction: SetupTransaction,
    recovered_target: ComfyTargetConfiguration,
) -> bool:
    """Return whether pending state repeats the stale attached-local target."""

    pending_target = transaction.target
    if pending_target is None:
        return False
    return (
        pending_target.mode is ComfyTargetMode.ATTACHED_LOCAL
        and pending_target.workspace_path == recovered_target.workspace_path
        and pending_target.endpoint == recovered_target.endpoint
    )


def _is_localhost(host: str) -> bool:
    """Return whether one host string points at this machine."""

    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def load_persisted_installation_context(
    explicit_root: Path | None = None,
) -> InstallationContext | None:
    """Load persisted startup context without constructing preference services."""

    return _build_core_onboarding_services(
        explicit_root
    ).onboarding_service.load_persisted_context()


def create_default_installation_context(
    explicit_root: Path | None = None,
) -> InstallationContext:
    """Build default startup context without constructing preference services."""

    return _build_core_onboarding_services(
        explicit_root
    ).onboarding_service.create_default_context()


def load_default_installation_configuration() -> InstallationConfiguration:
    """Build the default installation configuration for compatibility helpers."""

    return create_default_installation_context().installation


__all__ = [
    "OnboardingServiceBundle",
    "StartupReadinessServiceBundle",
    "build_onboarding_service_bundle",
    "build_startup_readiness_service_bundle",
    "create_default_installation_context",
    "load_default_installation_configuration",
    "load_persisted_installation_context",
    "resolve_installation_root",
]
