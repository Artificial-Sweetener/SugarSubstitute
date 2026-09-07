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

"""Provide inert setup collaborators for installer-experience qualification."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from sugarsubstitute_shared.localization import ApplicationText, app_text
from substitute.application.execution import CancellationToken
from substitute.application.errors import ErrorReport, SubstituteOperationContext
from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingCredentialDraft,
    OnboardingDraftState,
    OnboardingProvisioningFailure,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupProgressUnit,
    SetupTaskId,
    SetupTaskState,
)
from substitute.domain.model_recommendations import ModelInstallPlan
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonDiscoveryResult,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingTargetMode,
)


@dataclass(slots=True)
class SetupSideEffectAudit:
    """Record simulated work separately from forbidden external work."""

    network_calls: int = 0
    subprocess_calls: int = 0
    provisioning_calls: int = 0
    credential_reads: int = 0
    user_configuration_writes: int = 0
    model_downloads: int = 0
    simulated_provisioning_calls: int = 0

    def forbidden_counts(self) -> dict[str, int]:
        """Return the external operations that must remain unused."""

        return {
            "network_calls": self.network_calls,
            "subprocesses": self.subprocess_calls,
            "provisioning_calls": self.provisioning_calls,
            "credential_reads": self.credential_reads,
            "user_configuration_writes": self.user_configuration_writes,
            "model_downloads": self.model_downloads,
        }


class CapturedErrorPresenter:
    """Capture structured reports without opening a modal during qualification."""

    def __init__(self) -> None:
        """Initialize an empty report ledger."""

        self.reports: list[ErrorReport] = []

    def show_error_report(self, report: ErrorReport) -> None:
        """Retain one prepared report for semantic assertions."""

        self.reports.append(report)

    def show_exception_report(
        self,
        *,
        title: ApplicationText,
        message: ApplicationText,
        stage: str,
        error: BaseException,
        context: SubstituteOperationContext,
    ) -> None:
        """Reject an unexpected generic exception report route."""

        _ = (title, message, stage, error, context)
        raise AssertionError("Qualification expected a prepared setup error report.")

    def show_comfy_connection_report(
        self,
        *,
        title: ApplicationText,
        message: ApplicationText,
        stage: str,
        context: SubstituteOperationContext,
        error: BaseException | None = None,
    ) -> None:
        """Reject an unexpected Comfy connection report route."""

        _ = (title, message, stage, context, error)
        raise AssertionError("Qualification expected a prepared setup error report.")


class SyntheticComfyEnvironmentCoordinator(QObject):
    """Provide deterministic process and Python observations without probing."""

    preflight_changed = Signal(object)
    discovery_finished = Signal(object)
    recovery_changed = Signal(object)
    browse_finished = Signal(object)
    termination_finished = Signal(object)
    task_failed = Signal(str)

    def __init__(self, *, install_root: Path, parent: QObject | None = None) -> None:
        """Prepare one inert verified Python binding for attached setup."""

        super().__init__(parent)
        executable = install_root / "synthetic-python" / "python.exe"
        self._binding = ComfyPythonBinding(
            executable=executable,
            version="3.13.0",
            architecture="AMD64",
            prefix=executable.parent,
            base_prefix=executable.parent,
            source=ComfyPythonSelectionSource.DISCOVERED,
        )

    def start_preflight(self) -> None:
        """Report that no running ComfyUI process blocks setup."""

        from substitute.application.onboarding.comfy_environment_service import (
            ComfyPreflightSnapshot,
        )

        self.preflight_changed.emit(ComfyPreflightSnapshot(processes=()))

    def discover_attached_python(self, _workspace: Path) -> None:
        """Return a verified synthetic binding without reading the filesystem."""

        self.discovery_finished.emit(
            ComfyPythonDiscoveryResult(binding=self._binding, probes=())
        )

    def start_attached_recovery(
        self,
        *,
        workspace: Path,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Reject recovery because deterministic discovery always succeeds."""

        _ = (workspace, binding)
        self.task_failed.emit("Synthetic discovery unexpectedly entered recovery.")

    def validate_browsed_python(self, *, workspace: Path, executable: Path) -> None:
        """Reject browsing because the no-install route never opens native dialogs."""

        _ = (workspace, executable)
        self.task_failed.emit("Synthetic setup cannot browse for Python.")

    def close_observed_processes(self) -> None:
        """Report an inert completion for an impossible synthetic shutdown."""

        self.termination_finished.emit(None)

    def stop_monitoring(self) -> None:
        """Keep the synchronous synthetic coordinator idle."""

    def shutdown(self) -> None:
        """Release no resources because this coordinator owns none."""


class SyntheticOnboardingFlowService:
    """Complete production onboarding from deterministic in-memory state."""

    def __init__(
        self,
        *,
        install_root: Path,
        audit: SetupSideEffectAudit,
        provisioning_failures: int = 0,
    ) -> None:
        """Store the qualification root and side-effect evidence owner."""

        self._install_root = install_root
        self._audit = audit
        self._provisioning_failures = provisioning_failures

    def load_draft(self, installation_root: Path) -> OnboardingDraftState:
        """Return a complete managed-local draft without reading preferences."""

        root = installation_root.resolve()
        return OnboardingDraftState(
            installation_root=root,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=root / "comfyui",
            attached_workspace_path=root / "attached-comfyui",
            detected_platform="windows",
            detected_accelerator="nvidia",
            selected_install_target="windows_nvidia",
            selected_python_version="3.13",
            selected_comfy_channel="latest",
            selected_backend_policy="cuda_nightly_cu130",
            selected_torch_channel="nightly",
            selected_torch_reason="Synthetic no-install qualification.",
            selected_stability="experimental",
        )

    def provision(
        self,
        *,
        draft: OnboardingDraftState,
        credential_draft: OnboardingCredentialDraft | None = None,
        restart_required: bool,
        on_status: Callable[[ApplicationText], None],
        on_log: Callable[[ApplicationText], None],
        model_install_plan: ModelInstallPlan | None = None,
        setup_generation: int = 1,
        on_setup_progress: Callable[[SetupProgressEvent], None] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> OnboardingCompletionResult:
        """Emit representative progress and return a purely synthetic completion."""

        _ = credential_draft, cancellation
        self._audit.simulated_provisioning_calls += 1
        publish = on_setup_progress or (lambda _event: None)
        for task_id in (
            SetupTaskId.CONFIGURATION,
            SetupTaskId.RUNTIME,
            SetupTaskId.COMFY_WORKSPACE,
        ):
            _publish_completed_task(publish, setup_generation, task_id)
        if self._provisioning_failures > 0:
            self._provisioning_failures -= 1
            _publish_failed_model_transfer(
                publish=publish,
                setup_generation=setup_generation,
                model_install_plan=model_install_plan,
            )
            raise OnboardingProvisioningFailure(
                headline=app_text("The model download was interrupted"),
                user_message=app_text(
                    "Your reviewed choices are still selected. Try the download again."
                ),
                technical_detail="Synthetic qualification transfer failure.",
                remediation_steps=(app_text("Choose Try again to resume setup."),),
                transaction_id=f"qualification-{setup_generation}",
                failed_task=SetupTaskId.MODEL_DOWNLOAD.value,
            )
        _publish_model_transfer(
            publish=publish,
            setup_generation=setup_generation,
            model_install_plan=model_install_plan,
        )
        for task_id in (SetupTaskId.VALIDATION, SetupTaskId.COMMIT):
            _publish_completed_task(publish, setup_generation, task_id)
        on_status(app_text("Starting setup."))
        on_log(app_text("Starting setup."))
        on_status(app_text("Installing ComfyUI and finishing setup."))
        on_log(app_text("Installing ComfyUI and finishing setup."))
        on_status(app_text("Saving your setup choices."))
        target_mode = ComfyTargetMode(draft.target_mode)
        installation = InstallationConfiguration.create_default(self._install_root)
        runtime = RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=installation.runtime_dir
            / ".venv"
            / "Scripts"
            / "python.exe",
            bootstrap_status=RuntimeBootstrapStatus.READY,
        )
        return OnboardingCompletionResult(
            context=InstallationContext(
                installation=installation,
                runtime=runtime,
                comfy_target=ComfyTargetConfiguration(
                    mode=target_mode,
                    endpoint=ComfyEndpoint(
                        host=draft.endpoint_host,
                        port=draft.endpoint_port,
                    ),
                    workspace_path=_workspace_for(draft, target_mode),
                    install_owned=target_mode is ComfyTargetMode.MANAGED_LOCAL,
                    launch_owned=target_mode is ComfyTargetMode.MANAGED_LOCAL,
                ),
            ),
            restart_required=restart_required,
            launch_command=("synthetic-python", "main.py"),
        )


def _publish_model_transfer(
    *,
    publish: Callable[[SetupProgressEvent], None],
    setup_generation: int,
    model_install_plan: ModelInstallPlan | None,
) -> None:
    """Publish exact synthetic model-byte progress for the reviewed plan."""

    if model_install_plan is None or not model_install_plan.files:
        publish(
            SetupProgressEvent(
                setup_generation,
                SetupTaskId.MODEL_DOWNLOAD,
                SetupTaskState.SKIPPED,
                app_text("No simulated model transfer was required."),
            )
        )
        return
    expected = model_install_plan.total_bytes
    current = model_install_plan.files[0].display_name
    publish(
        SetupProgressEvent(
            setup_generation,
            SetupTaskId.MODEL_DOWNLOAD,
            SetupTaskState.RUNNING,
            app_text("Simulating the reviewed model transfer."),
            SetupProgressUnit.BYTES,
            expected // 2,
            expected,
            current,
        )
    )
    publish(
        SetupProgressEvent(
            setup_generation,
            SetupTaskId.MODEL_DOWNLOAD,
            SetupTaskState.COMPLETED,
            app_text("The simulated model transfer is complete."),
            SetupProgressUnit.BYTES,
            expected,
            expected,
            current,
        )
    )


def _publish_failed_model_transfer(
    *,
    publish: Callable[[SetupProgressEvent], None],
    setup_generation: int,
    model_install_plan: ModelInstallPlan | None,
) -> None:
    """Publish one deterministic partial transfer and terminal failure."""

    expected = model_install_plan.total_bytes if model_install_plan else 1024
    current = (
        model_install_plan.files[0].display_name
        if model_install_plan and model_install_plan.files
        else "starter model"
    )
    for state in (SetupTaskState.RUNNING, SetupTaskState.FAILED):
        publish(
            SetupProgressEvent(
                setup_generation,
                SetupTaskId.MODEL_DOWNLOAD,
                state,
                app_text("The simulated model transfer was interrupted."),
                SetupProgressUnit.BYTES,
                expected // 2,
                expected,
                current,
            )
        )


def _publish_completed_task(
    publish: Callable[[SetupProgressEvent], None],
    setup_generation: int,
    task_id: SetupTaskId,
) -> None:
    """Publish one deterministic running-to-complete setup task."""

    publish(
        SetupProgressEvent(
            setup_generation,
            task_id,
            SetupTaskState.RUNNING,
            app_text("Completing simulated %1 work.", task_id.value),
        )
    )
    publish(
        SetupProgressEvent(
            setup_generation,
            task_id,
            SetupTaskState.COMPLETED,
            app_text("Simulated %1 work is complete.", task_id.value),
        )
    )


def _workspace_for(
    draft: OnboardingDraftState,
    target_mode: ComfyTargetMode,
) -> Path | None:
    """Return the workspace selected by one synthetic target route."""

    if target_mode is ComfyTargetMode.MANAGED_LOCAL:
        return draft.managed_workspace_path
    if target_mode is ComfyTargetMode.ATTACHED_LOCAL:
        return draft.attached_workspace_path
    return None


__all__ = [
    "CapturedErrorPresenter",
    "SetupSideEffectAudit",
    "SyntheticComfyEnvironmentCoordinator",
    "SyntheticOnboardingFlowService",
]
