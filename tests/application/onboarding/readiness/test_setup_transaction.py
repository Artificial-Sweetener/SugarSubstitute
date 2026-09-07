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

"""Regression tests for interruption-safe setup transaction state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from substitute.application.onboarding import (
    BootstrapReadinessService,
    ComfyTargetService,
    InstallationService,
    ManagedRuntimeService,
    OnboardingDraftState,
    OnboardingFlowService,
    OnboardingProvisioningFailure,
    OnboardingService,
    RuntimeService,
    SetupTransactionService,
)
from substitute.application.onboarding.flow_contracts import OnboardingBundleProtocol
from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyTargetMode,
    InstallationConfiguration,
    ReadinessIssueCode,
    SetupTransaction,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.infrastructure.onboarding import (
    FileComfyTargetConfigurationRepository,
    FileInstallationConfigurationRepository,
    FileManagedRuntimeConfigurationRepository,
    FileRuntimeConfigurationRepository,
    FileSetupTransactionRepository,
)
from substitute.infrastructure.onboarding.readiness_checks import (
    ConfigurationFileSet,
)


from tests.support.onboarding.setup_transaction_state import (
    _FakeReadinessChecks,
    _ReadyRuntimeProvisioner,
    _StaticSelectionPolicy,
    _build_readiness_service,
    _managed_target,
    _ready_runtime,
    _valid_managed_runtime,
)


def test_readiness_routes_ready_when_active_config_is_ready_with_pending_state(
    tmp_path: Path,
) -> None:
    """Last-known-good active state should win over interrupted pending state."""

    installation = InstallationConfiguration.create_default(tmp_path)
    repository = FileSetupTransactionRepository(installation.runtime_state_dir)
    repository.save(
        SetupTransaction(
            schema_version=1,
            transaction_id="transaction-id",
            mode=SetupTransactionMode.REPAIR,
            status=SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    service = _build_readiness_service(
        installation=installation,
        runtime=_ready_runtime(installation),
        target=_managed_target(installation),
        managed_runtime=_valid_managed_runtime(),
        repository=repository,
        files_present=True,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()


def test_readiness_routes_repair_when_no_active_config_has_pending_state(
    tmp_path: Path,
) -> None:
    """Interrupted setup without active config should route to repair/resume."""

    installation = InstallationConfiguration.create_default(tmp_path)
    repository = FileSetupTransactionRepository(installation.runtime_state_dir)
    repository.save(
        SetupTransaction(
            schema_version=1,
            transaction_id="transaction-id",
            mode=SetupTransactionMode.FIRST_RUN,
            status=SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    service = _build_readiness_service(
        installation=installation,
        runtime=None,
        target=None,
        managed_runtime=None,
        repository=repository,
        files_present=False,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert (
        assessment.issues[-1].code is ReadinessIssueCode.SETUP_TRANSACTION_INTERRUPTED
    )


def test_attached_endpoint_failure_does_not_replace_active_target(
    tmp_path: Path,
) -> None:
    """Candidate readiness should reject bad attached-local targets before commit."""

    installation = InstallationConfiguration.create_default(tmp_path)
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    runtime_service = RuntimeService(
        FileRuntimeConfigurationRepository(installation),
        provisioner=_ReadyRuntimeProvisioner(),
    )
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    installation_service.save(installation)
    runtime_service.save(_ready_runtime(installation))
    target_service.configure(_managed_target(installation))
    managed_runtime_service.save_active_configuration(_valid_managed_runtime())
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(installation.runtime_state_dir),
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    readiness_service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
        checks=_FakeReadinessChecks(
            files=ConfigurationFileSet(
                installation_path=installation.user_settings_dir / "installation.json",
                runtime_path=installation.user_settings_dir / "runtime.json",
                target_path=installation.user_settings_dir / "comfy_target.json",
            ),
            endpoint_reachable=False,
        ),
        setup_transaction_repository=setup_transaction_service.repository,
    )

    @dataclass(frozen=True)
    class _Bundle:
        """Expose real services as one flow bundle."""

        onboarding_service: OnboardingService
        runtime_service: RuntimeService
        readiness_service: BootstrapReadinessService
        managed_runtime_service: ManagedRuntimeService
        setup_transaction_service: SetupTransactionService
        preference_setup_service: "_NoOpPreferenceSetupService"

    class _NoOpPreferenceSetupService:
        """Ignore preference saves for transaction-focused tests."""

        def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
            """Accept non-secret onboarding preferences."""

            _ = draft

        def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
            """Accept optional onboarding credentials."""

            _ = draft

    flow_service = OnboardingFlowService(
        service_bundle_factory=lambda _root: cast(
            OnboardingBundleProtocol,
            _Bundle(
                onboarding_service=OnboardingService(
                    installation_service=installation_service,
                    runtime_service=runtime_service,
                    comfy_target_service=target_service,
                ),
                runtime_service=runtime_service,
                readiness_service=readiness_service,
                managed_runtime_service=managed_runtime_service,
                setup_transaction_service=setup_transaction_service,
                preference_setup_service=_NoOpPreferenceSetupService(),
            ),
        ),
        managed_workspace_provisioner=lambda **kwargs: (
            installation.default_managed_comfy_dir
        ),
        entrypoint_path=tmp_path / "main.py",
    )

    with pytest.raises(OnboardingProvisioningFailure):
        flow_service.provision(
            draft=OnboardingDraftState(
                installation_root=tmp_path,
                target_mode=ComfyTargetMode.ATTACHED_LOCAL.value,
                endpoint_host="127.0.0.1",
                endpoint_port=8199,
                managed_workspace_path=installation.default_managed_comfy_dir,
                attached_workspace_path=None,
            ),
            restart_required=False,
            on_status=lambda message: None,
            on_log=lambda line: None,
        )

    saved_target = FileComfyTargetConfigurationRepository(installation).load()
    assert saved_target.mode is ComfyTargetMode.MANAGED_LOCAL
    assert saved_target.endpoint.port == 8188
