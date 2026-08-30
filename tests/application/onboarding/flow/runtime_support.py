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

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ManagedRuntimeConfiguration,
    ReadinessAssessment,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
    SetupTransaction,
    SetupTransactionMode,
    SetupTransactionStatus,
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
