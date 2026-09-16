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

"""Exercise restart admission with the production cleanup result contract."""

from dataclasses import replace
from pathlib import Path

import pytest

from substitute.app.bootstrap.managed_comfy_runtime_owner import (
    ManagedComfyRuntimeOwner,
)
from substitute.app.bootstrap.managed_recovery_adapters import (
    cleanup_managed_recovery_state,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationStatus,
)
from substitute.infrastructure.comfy.process_manager import kill_comfyui_state
from tests.support.execution.testing import ImmediateTaskSubmitter


@pytest.mark.parametrize(
    ("resource_present", "status", "admitted"),
    [
        (False, None, True),
        (True, ManagedProcessTerminationStatus.TERMINATED_CONFIRMED, True),
        (True, ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED, False),
        (True, ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED, False),
        (True, ManagedProcessTerminationStatus.NO_ACTION_REQUIRED, False),
    ],
)
def test_restart_admission_uses_production_cleanup_evidence(
    resource_present: bool,
    status: ManagedProcessTerminationStatus | None,
    admitted: bool,
) -> None:
    """Admit replacement only for absent resources or confirmed native termination."""
    confirmed = ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    cleanup = replace(
        kill_comfyui_state(None),
        managed_resource_present=resource_present,
        termination_status=status,
    )
    replacement = object()
    failures: list[str] = []
    owner = ManagedComfyRuntimeOwner(
        target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint("127.0.0.1", 8188),
            workspace_path=Path("ComfyUI"),
            install_owned=True,
            launch_owned=True,
        ),
        submitter=ImmediateTaskSubmitter(),
        request_stop=lambda _state: None,
        cleanup_state=(lambda _state: cleanup)
        if resource_present
        else cleanup_managed_recovery_state,
        confirmed_termination_status=confirmed,
        launch_state=lambda: replacement,
    )
    try:
        owner.request_restart(on_failure=lambda: failures.append("restart failed"))
        assert failures == ([] if admitted else ["restart failed"])
        assert owner.state is (replacement if admitted else None)
    finally:
        owner.close()
