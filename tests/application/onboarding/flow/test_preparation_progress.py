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

"""Verify background preparation preserves semantic workspace progress."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from sugarsubstitute_shared.localization import ApplicationText, app_text
from substitute.application.onboarding import OnboardingDraftState
from substitute.application.onboarding.preparation_service import (
    OnboardingPreparationService,
)
from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupTaskId,
    SetupTaskState,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyPythonBinding,
    ComfyTargetMode,
    ManagedComfySetupResult,
    ReadinessAssessment,
)
from .preference_support import _Bundle
from .runtime_support import (
    _FakeRuntimeLaunchService,
    _FakeSetupTransactionService,
    _StaticManagedRuntimeService,
    _StaticOnboardingService,
    _StaticReadinessService,
    _build_context,
    _managed_setup_result,
    _python_binding,
)


@pytest.mark.parametrize(
    "mode", [ComfyTargetMode.MANAGED_LOCAL, ComfyTargetMode.ATTACHED_LOCAL]
)
def test_preparation_publishes_workspace_status_before_work_continues(
    tmp_path: Path, mode: ComfyTargetMode
) -> None:
    """Expose real phase messages without turning diagnostic output into progress."""
    context = _build_context(tmp_path, mode)
    events: list[SetupProgressEvent] = []
    logs: list[ApplicationText] = []
    messages = [
        app_text("Provisioning ComfyUI-Manager."),
        app_text("Installing Substitute Comfy nodepacks."),
    ]

    def run_workspace(
        on_status: Callable[[str], None] | None, on_log: Callable[[str], None] | None
    ) -> None:
        """Exercise the provisioner's status and diagnostic boundaries in order."""
        assert on_status is not None and on_log is not None
        for message in messages:
            on_status(message)
            assert events[-1].task_id is SetupTaskId.COMFY_WORKSPACE
            assert events[-1].state is SetupTaskState.RUNNING
            assert events[-1].message == message
            assert events[-1].generation == 7
            assert events[-1].completed_units is None
            previous = len(events)
            on_log("synthetic diagnostic output")
            assert len(events) == previous

    def managed(
        *,
        on_status: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        **unused: object,
    ) -> ManagedComfySetupResult:
        """Publish managed preparation messages through the external boundary."""
        run_workspace(on_status, on_log)
        return _managed_setup_result(tmp_path / "comfyui")

    def attached(
        *,
        workspace: Path,
        python_binding: ComfyPythonBinding,
        model_root: Path | None = None,
        configure_model_root: bool = False,
        on_status: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        **unused: object,
    ) -> ComfyPythonBinding:
        """Publish attached preparation messages through the external boundary."""
        run_workspace(on_status, on_log)
        return python_binding

    service = OnboardingPreparationService(
        service_bundle_factory=lambda _root: _Bundle(
            onboarding_service=_StaticOnboardingService(context),
            runtime_service=_FakeRuntimeLaunchService(),
            readiness_service=_StaticReadinessService(
                ReadinessAssessment(route=BootstrapRoute.READY, issues=())
            ),
            managed_runtime_service=_StaticManagedRuntimeService(),
            setup_transaction_service=_FakeSetupTransactionService(context),
        ),
        managed_workspace_provisioner=managed,
        attached_workspace_provisioner=attached,
    )
    service.prepare(
        draft=OnboardingDraftState(
            installation_root=tmp_path,
            target_mode=mode.value,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            managed_workspace_path=tmp_path / "comfyui",
            attached_workspace_path=tmp_path / "attached",
            attached_python_binding=_python_binding(tmp_path / "attached"),
        ),
        generation=7,
        on_progress=events.append,
        on_log=logs.append,
    )
    assert all(message in logs for message in messages)
    assert events[-1].state is SetupTaskState.COMPLETED
