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
    ActiveSafeManagedRuntimeStateRecorder,
    BootstrapReadinessService,
    ComfyTargetService,
    InstallationService,
    ManagedRuntimeService,
    OnboardingDraftState,
    OnboardingFlowService,
    OnboardingProvisioningFailure,
    OnboardingService,
    RuntimeService,
    SetupTransactionOptions,
    SetupTransactionService,
)
from substitute.application.onboarding.flow_service import OnboardingBundleProtocol
from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
)
from substitute.application.ports.managed_runtime_selection_policy import (
    ManagedRuntimeSelectionPolicy,
    ManagedRuntimeSelectionUnavailableError,
)
from substitute.application.ports.runtime_provisioner import RuntimeProvisioner
from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepositoryError,
)
from substitute.app.bootstrap.installation_context import (
    _discard_stale_attached_pending_for_active_managed_target,
    _recover_legacy_attached_managed_target,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
    ReadinessIssueCode,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
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
    FileSystemReadinessChecks,
)


@dataclass(frozen=True)
class _StaticInstallationService:
    """Return one optional persisted installation configuration."""

    configuration: InstallationConfiguration | None

    def load_persisted(self) -> InstallationConfiguration | None:
        """Return the configured installation value."""

        return self.configuration


@dataclass(frozen=True)
class _StaticRuntimeService:
    """Return one optional persisted runtime configuration."""

    configuration: RuntimeConfiguration | None

    def load_persisted(self) -> RuntimeConfiguration | None:
        """Return the configured runtime value."""

        return self.configuration


@dataclass(frozen=True)
class _StaticTargetService:
    """Return one optional persisted target configuration."""

    configuration: ComfyTargetConfiguration | None

    def load_persisted(self) -> ComfyTargetConfiguration | None:
        """Return the configured target value."""

        return self.configuration


@dataclass(frozen=True)
class _StaticManagedRuntimeService:
    """Return one optional persisted managed runtime configuration."""

    configuration: ManagedRuntimeConfiguration | None

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Return the configured managed runtime value."""

        return self.configuration


@dataclass(frozen=True)
class _FakeReadinessChecks:
    """Provide deterministic readiness outcomes for pending-state tests."""

    files: ConfigurationFileSet
    endpoint_reachable: bool = True
    runtime_python_present: bool = True

    def configuration_files(self, installation_root: Path) -> ConfigurationFileSet:
        """Return the configured file set."""

        _ = installation_root
        return self.files

    def is_installation_configuration_valid(
        self,
        configuration: InstallationConfiguration,
    ) -> bool:
        """Treat all supplied installation configurations as valid."""

        _ = configuration
        return True

    def is_runtime_configuration_valid(
        self,
        configuration: RuntimeConfiguration,
    ) -> bool:
        """Treat all supplied runtime configurations as valid."""

        _ = configuration
        return True

    def runtime_python_exists(self, configuration: RuntimeConfiguration) -> bool:
        """Return the configured runtime-python presence."""

        _ = configuration
        return self.runtime_python_present

    def is_target_configuration_valid(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Treat all supplied target configurations as valid."""

        _ = configuration
        return True

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Treat attached workspaces as present."""

        _ = workspace
        return True

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return the configured endpoint reachability."""

        _ = configuration
        return self.endpoint_reachable

    def is_managed_workspace_installed(self, workspace: Path) -> bool:
        """Treat managed workspace files as installed."""

        _ = workspace
        return True

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Treat managed workspace files as launchable."""

        _ = workspace
        return True

    def has_required_managed_nodepacks(self, workspace: Path) -> bool:
        """Treat required managed custom nodes as present."""

        _ = workspace
        return True

    def probe_managed_listener(
        self,
        *,
        installation: InstallationConfiguration,
        configuration: ComfyTargetConfiguration,
    ) -> ManagedListenerProbeResult:
        """Return no active managed listener."""

        _ = installation, configuration
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="No listener in this test.",
        )


@dataclass(frozen=True)
class _LegacyRecoveryChecks:
    """Provide deterministic checks for legacy attached-target recovery."""

    endpoint_reachable: bool = False
    managed_launchable: bool = True

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the stale attached target is reachable."""

        _ = configuration
        return self.endpoint_reachable

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return whether the local workspace can be launched as managed Comfy."""

        _ = workspace
        return self.managed_launchable


@dataclass
class _RecordingManagedRuntimeRepository:
    """Record managed runtime saves while satisfying the repository protocol."""

    saved: ManagedRuntimeConfiguration | None = None

    def exists(self) -> bool:
        """Return whether a configuration has been saved."""

        return self.saved is not None

    def build_default(self) -> ManagedRuntimeConfiguration:
        """Return the default managed runtime configuration."""

        return ManagedRuntimeConfiguration()

    def load(self) -> ManagedRuntimeConfiguration:
        """Return the saved configuration or default."""

        return self.saved or self.build_default()

    def save(self, configuration: ManagedRuntimeConfiguration) -> None:
        """Record one saved configuration."""

        self.saved = configuration


@dataclass(frozen=True)
class _StaticSelectionPolicy(ManagedRuntimeSelectionPolicy):
    """Return a deterministic managed runtime selection."""

    configuration: ManagedRuntimeConfiguration

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return the configured managed runtime."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        return self.configuration


@dataclass(frozen=True)
class _UnavailableSelectionPolicy(ManagedRuntimeSelectionPolicy):
    """Report that managed Comfy is unsupported on the detected machine."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Raise the expected capability error for every selection attempt."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        raise ManagedRuntimeSelectionUnavailableError("No Linux accelerator detected.")


@dataclass(frozen=True)
class _ReadyRuntimeProvisioner(RuntimeProvisioner):
    """Return ready runtime configuration without installing dependencies."""

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Return the supplied configuration as ready."""

        return RuntimeConfiguration(
            runtime_root=configuration.runtime_root,
            python_executable=configuration.python_executable,
            bootstrap_status=RuntimeBootstrapStatus.READY,
            schema_version=configuration.schema_version,
        )

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return a deterministic launch command."""

        _ = configuration
        return ["python", str(entrypoint_path)]


def test_setup_transaction_repository_round_trips_pending_state(
    tmp_path: Path,
) -> None:
    """Pending setup transactions should survive JSON persistence."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _ready_runtime(installation)
    target = _managed_target(installation)
    managed_runtime = _valid_managed_runtime()
    repository = FileSetupTransactionRepository(installation.runtime_state_dir)
    transaction = SetupTransaction(
        schema_version=1,
        transaction_id="transaction-id",
        mode=SetupTransactionMode.REPAIR,
        status=SetupTransactionStatus.READY_TO_COMMIT,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        installation=installation,
        runtime=runtime,
        target=target,
        managed_runtime=managed_runtime,
        workspace_path=target.workspace_path,
        endpoint_host=target.endpoint.host,
        endpoint_port=target.endpoint.port,
        force_cpu_mode=True,
        failure=SetupTransactionFailure(
            code="example",
            message="example failure",
            recoverable=True,
            diagnostic_detail="detail",
        ),
    )

    repository.save(transaction)
    loaded = repository.load()

    assert loaded == transaction


def test_setup_transaction_repository_reports_corrupt_payload(
    tmp_path: Path,
) -> None:
    """Corrupt pending setup state should not be interpreted as active state."""

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "setup_transaction.json").write_text("{", encoding="utf-8")
    repository = FileSetupTransactionRepository(state_dir)

    with pytest.raises(SetupTransactionRepositoryError):
        repository.load()


def test_setup_transaction_service_commits_managed_transaction(
    tmp_path: Path,
) -> None:
    """Committing a valid managed transaction should write active files and clear pending."""

    installation = InstallationConfiguration.create_default(tmp_path)
    transaction_repository = FileSetupTransactionRepository(
        installation.runtime_state_dir
    )
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    runtime_service = RuntimeService(FileRuntimeConfigurationRepository(installation))
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    service = SetupTransactionService(
        repository=transaction_repository,
        installation_service=installation_service,
        runtime_service=runtime_service,
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    transaction = service.begin(
        mode=SetupTransactionMode.REPAIR,
        options=SetupTransactionOptions(
            workspace_path=installation.default_managed_comfy_dir,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
        ),
    )

    service.record_installation(transaction.transaction_id, installation)
    service.record_runtime(transaction.transaction_id, _ready_runtime(installation))
    service.record_target(transaction.transaction_id, _managed_target(installation))
    service.record_managed_runtime(
        transaction.transaction_id,
        _valid_managed_runtime(),
    )
    service.update_status(
        transaction.transaction_id,
        SetupTransactionStatus.READY_TO_COMMIT,
    )
    context = service.commit(transaction.transaction_id)

    assert context.comfy_target.mode is ComfyTargetMode.MANAGED_LOCAL
    assert transaction_repository.exists() is False
    assert (
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir)
        .load()
        .validation_status
        is ManagedRuntimeValidationStatus.VALID
    )
    assert (installation.user_settings_dir / "comfy_target.json").exists()


def test_managed_runtime_selection_does_not_persist_active_state() -> None:
    """Selecting a runtime should be side-effect free until explicitly saved."""

    selected = ManagedRuntimeConfiguration(install_target="windows_nvidia")
    repository = _RecordingManagedRuntimeRepository()
    service = ManagedRuntimeService(
        repository,
        selection_policy=_StaticSelectionPolicy(selected),
    )

    result = service.select_configuration()

    assert result == selected
    assert repository.saved is None


def test_managed_runtime_draft_falls_back_when_managed_install_is_unavailable() -> None:
    """Opening onboarding remains possible without a managed Comfy install target."""

    repository = _RecordingManagedRuntimeRepository()
    service = ManagedRuntimeService(
        repository,
        selection_policy=_UnavailableSelectionPolicy(),
    )

    result = service.load_draft_configuration()

    assert result == ManagedRuntimeConfiguration()
    assert repository.saved is None


def test_active_safe_recorder_preserves_valid_runtime_on_failure() -> None:
    """Launch failure recording should not downgrade a valid active runtime."""

    valid_runtime = _valid_managed_runtime()
    repository = _RecordingManagedRuntimeRepository(valid_runtime)
    service = ManagedRuntimeService(
        repository,
        selection_policy=_StaticSelectionPolicy(valid_runtime),
    )
    recorder = ActiveSafeManagedRuntimeStateRecorder(service)

    result = recorder.record_failure(
        status=ManagedRuntimeValidationStatus.INSTALL_FAILED,
        detail="interrupted during splash",
    )

    assert result.validation_status is ManagedRuntimeValidationStatus.VALID
    assert repository.saved == valid_runtime


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


def test_legacy_attached_managed_target_recovery_restores_managed_mode(
    tmp_path: Path,
) -> None:
    """Old corrupted attached-local managed state should recover to managed-local."""

    installation = InstallationConfiguration.create_default(tmp_path)
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(installation.runtime_state_dir),
        installation_service=installation_service,
        runtime_service=RuntimeService(
            FileRuntimeConfigurationRepository(installation)
        ),
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    stale_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=False,
        launch_owned=False,
    )
    installation_service.save(installation)
    assert stale_target.workspace_path is not None
    stale_target.workspace_path.mkdir(parents=True, exist_ok=True)
    target_service.configure(stale_target)
    managed_runtime_service.save_active_configuration(_valid_managed_runtime())
    transaction = setup_transaction_service.begin(
        mode=SetupTransactionMode.REPAIR,
        options=SetupTransactionOptions(
            workspace_path=stale_target.workspace_path,
            endpoint_host=stale_target.endpoint.host,
            endpoint_port=stale_target.endpoint.port,
        ),
    )
    setup_transaction_service.record_target(
        transaction.transaction_id,
        stale_target,
    )
    setup_transaction_service.record_failure(
        transaction.transaction_id,
        SetupTransactionFailure(
            code="endpoint_unreachable",
            message="ComfyUI did not respond.",
            recoverable=True,
        ),
    )

    _recover_legacy_attached_managed_target(
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
        setup_transaction_service=setup_transaction_service,
        checks=cast(FileSystemReadinessChecks, _LegacyRecoveryChecks()),
    )

    recovered_target = target_service.load_persisted()
    recovered_runtime = managed_runtime_service.load_persisted()
    assert recovered_target is not None
    assert recovered_runtime is not None
    assert recovered_target.mode is ComfyTargetMode.MANAGED_LOCAL
    assert recovered_target.launch_owned is True
    assert recovered_runtime.workspace_path == str(
        stale_target.workspace_path.resolve()
    )
    assert not (stale_target.workspace_path / ".comfy_installed").exists()
    assert setup_transaction_service.load() is None


def test_stale_attached_pending_is_discarded_when_active_target_is_managed(
    tmp_path: Path,
) -> None:
    """Failed attached pending state should not survive after active target recovery."""

    installation = InstallationConfiguration.create_default(tmp_path)
    installation_service = InstallationService(
        FileInstallationConfigurationRepository(tmp_path)
    )
    target_service = ComfyTargetService(
        FileComfyTargetConfigurationRepository(installation)
    )
    managed_runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(installation.runtime_state_dir),
        selection_policy=_StaticSelectionPolicy(_valid_managed_runtime()),
    )
    setup_transaction_service = SetupTransactionService(
        repository=FileSetupTransactionRepository(installation.runtime_state_dir),
        installation_service=installation_service,
        runtime_service=RuntimeService(
            FileRuntimeConfigurationRepository(installation)
        ),
        comfy_target_service=target_service,
        managed_runtime_service=managed_runtime_service,
    )
    active_target = _managed_target(installation)
    stale_target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=active_target.endpoint,
        workspace_path=active_target.workspace_path,
        install_owned=False,
        launch_owned=False,
    )
    installation_service.save(installation)
    target_service.configure(active_target)
    transaction = setup_transaction_service.begin(mode=SetupTransactionMode.REPAIR)
    setup_transaction_service.record_target(transaction.transaction_id, stale_target)
    setup_transaction_service.record_failure(
        transaction.transaction_id,
        SetupTransactionFailure(
            code="endpoint_unreachable",
            message="ComfyUI did not respond.",
            recoverable=True,
        ),
    )

    _discard_stale_attached_pending_for_active_managed_target(
        comfy_target_service=target_service,
        setup_transaction_service=setup_transaction_service,
    )

    assert setup_transaction_service.load() is None


def _build_readiness_service(
    *,
    installation: InstallationConfiguration,
    runtime: RuntimeConfiguration | None,
    target: ComfyTargetConfiguration | None,
    managed_runtime: ManagedRuntimeConfiguration | None,
    repository: FileSetupTransactionRepository,
    files_present: bool,
) -> BootstrapReadinessService:
    """Build one readiness service for pending-state tests."""

    file_set = ConfigurationFileSet(
        installation_path=installation.user_settings_dir / "installation.json",
        runtime_path=installation.user_settings_dir / "runtime.json",
        target_path=installation.user_settings_dir / "comfy_target.json",
    )
    if files_present:
        installation.user_settings_dir.mkdir(parents=True, exist_ok=True)
        file_set.installation_path.write_text("{}", encoding="utf-8")
        file_set.runtime_path.write_text("{}", encoding="utf-8")
        file_set.target_path.write_text("{}", encoding="utf-8")
    return BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation if files_present else None),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(ComfyTargetService, _StaticTargetService(target)),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeReadinessChecks(files=file_set),
        setup_transaction_repository=repository,
    )


def _ready_runtime(
    installation: InstallationConfiguration,
) -> RuntimeConfiguration:
    """Build a ready runtime configuration for tests."""

    return RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )


def _managed_target(
    installation: InstallationConfiguration,
) -> ComfyTargetConfiguration:
    """Build a managed-local target configuration for tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )


def _valid_managed_runtime() -> ManagedRuntimeConfiguration:
    """Build a valid managed runtime configuration for tests."""

    return ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
