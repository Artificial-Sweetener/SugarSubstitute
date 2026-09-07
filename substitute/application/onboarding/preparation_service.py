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

"""Prepare choice-independent local ComfyUI work before setup confirmation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.onboarding.flow_contracts import (
    AttachedWorkspaceProvisioner,
    OnboardingBundleFactory,
    OnboardingDraftState,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupTaskId,
    SetupTaskState,
    require_setup_current,
)
from substitute.application.execution import CancellationToken
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import ComfyEndpoint, ComfyTargetMode


@dataclass(frozen=True, slots=True)
class OnboardingPreparationKey:
    """Identify every draft input that affects choice-independent preparation."""

    installation_root: Path
    target_mode: str
    endpoint_host: str
    endpoint_port: int
    workspace_path: Path | None
    attached_python_executable: Path | None
    force_cpu_mode: bool
    prefer_edge_torch: bool
    prefer_edge_comfy_channel: bool

    @classmethod
    def from_draft(cls, draft: OnboardingDraftState) -> OnboardingPreparationKey:
        """Capture the preparation-relevant identity of one draft."""

        mode = ComfyTargetMode(draft.target_mode)
        workspace = (
            draft.managed_workspace_path
            if mode is ComfyTargetMode.MANAGED_LOCAL
            else draft.attached_workspace_path
        )
        binding = draft.attached_python_binding
        return cls(
            installation_root=draft.installation_root,
            target_mode=draft.target_mode,
            endpoint_host=draft.endpoint_host.strip(),
            endpoint_port=draft.endpoint_port,
            workspace_path=workspace,
            attached_python_executable=(
                binding.executable if binding is not None else None
            ),
            force_cpu_mode=draft.force_cpu_mode,
            prefer_edge_torch=draft.prefer_edge_torch,
            prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
        )


@dataclass(frozen=True, slots=True)
class OnboardingPreparationResult:
    """Record a completed preparation generation and its exact input identity."""

    generation: int
    key: OnboardingPreparationKey


class OnboardingPreparationService:
    """Run idempotent runtime and workspace preparation without committing setup."""

    def __init__(
        self,
        *,
        service_bundle_factory: OnboardingBundleFactory,
        managed_workspace_provisioner: Callable[..., Path],
        attached_workspace_provisioner: AttachedWorkspaceProvisioner | None,
    ) -> None:
        """Store the preparation-only infrastructure boundaries."""

        self._service_bundle_factory = service_bundle_factory
        self._managed_workspace_provisioner = managed_workspace_provisioner
        self._attached_workspace_provisioner = attached_workspace_provisioner

    def prepare(
        self,
        *,
        draft: OnboardingDraftState,
        generation: int,
        on_progress: Callable[[SetupProgressEvent], None],
        on_log: Callable[[ApplicationText], None],
        cancellation: CancellationToken | None = None,
    ) -> OnboardingPreparationResult:
        """Prepare local runtime/workspace files while leaving active state untouched."""

        key = OnboardingPreparationKey.from_draft(draft)
        require_setup_current(cancellation)
        mode = ComfyTargetMode(draft.target_mode)
        if mode is ComfyTargetMode.REMOTE:
            self._emit(
                on_progress,
                generation,
                SetupTaskId.COMFY_WORKSPACE,
                SetupTaskState.SKIPPED,
                app_text("Remote ComfyUI does not need local workspace preparation."),
            )
            return OnboardingPreparationResult(generation, key)

        bundle = self._service_bundle_factory(draft.installation_root)
        require_setup_current(cancellation)
        endpoint = ComfyEndpoint(draft.endpoint_host.strip(), draft.endpoint_port)
        self._emit(
            on_progress,
            generation,
            SetupTaskId.RUNTIME,
            SetupTaskState.RUNNING,
            app_text("Preparing Substitute's local runtime."),
        )
        if mode is ComfyTargetMode.MANAGED_LOCAL:
            context = bundle.onboarding_service.build_managed_local_context(
                endpoint=endpoint,
                workspace_path=draft.managed_workspace_path,
            )
        else:
            attached_workspace = draft.attached_workspace_path
            attached_binding = draft.attached_python_binding
            if attached_workspace is None or attached_binding is None:
                raise ValueError(
                    "Attached ComfyUI preparation requires a verified workspace and Python."
                )
            context = bundle.onboarding_service.build_attached_local_context(
                endpoint=endpoint,
                workspace_path=attached_workspace,
                python_binding=attached_binding,
            )
        bundle.runtime_service.provision_draft(context.runtime)
        require_setup_current(cancellation)
        self._emit(
            on_progress,
            generation,
            SetupTaskId.RUNTIME,
            SetupTaskState.COMPLETED,
            app_text("Substitute's local runtime is ready."),
        )
        self._emit(
            on_progress,
            generation,
            SetupTaskId.COMFY_WORKSPACE,
            SetupTaskState.RUNNING,
            app_text("Preparing ComfyUI in the background."),
        )
        if mode is ComfyTargetMode.MANAGED_LOCAL:
            self._managed_workspace_provisioner(
                workspace=draft.managed_workspace_path,
                configure_model_root=False,
                force_cpu_mode=draft.force_cpu_mode,
                prefer_edge_torch=draft.prefer_edge_torch,
                prefer_edge_comfy_channel=draft.prefer_edge_comfy_channel,
                repair_existing_runtime=False,
                refresh_core_nodepacks=frozenset(CoreNodepackId),
                on_status=lambda message: on_log(app_text("%1", message)),
                on_log=lambda message: on_log(app_text("%1", message)),
            )
        else:
            provisioner = self._attached_workspace_provisioner
            assert provisioner is not None
            assert attached_workspace is not None
            assert attached_binding is not None
            provisioner(
                workspace=attached_workspace,
                python_binding=attached_binding,
                configure_model_root=False,
                on_status=lambda message: on_log(app_text("%1", message)),
                on_log=lambda message: on_log(app_text("%1", message)),
            )
        require_setup_current(cancellation)
        self._emit(
            on_progress,
            generation,
            SetupTaskId.COMFY_WORKSPACE,
            SetupTaskState.COMPLETED,
            app_text("ComfyUI preparation is ready for final setup."),
        )
        return OnboardingPreparationResult(generation, key)

    @staticmethod
    def _emit(
        callback: Callable[[SetupProgressEvent], None],
        generation: int,
        task_id: SetupTaskId,
        state: SetupTaskState,
        message: ApplicationText,
    ) -> None:
        """Emit one typed indeterminate phase transition."""

        callback(SetupProgressEvent(generation, task_id, state, message))


__all__ = [
    "OnboardingPreparationKey",
    "OnboardingPreparationResult",
    "OnboardingPreparationService",
]
