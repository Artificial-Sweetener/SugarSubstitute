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

"""Reset, provision, and launch the external Comfy fixture used by attach tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_launcher import (
    start_managed_comfy_subprocess,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_readiness import wait_for_ready
from tests.onboarding_automation.fixture_paths import ScenarioPaths
from tools.ci.loopback_port_lease import LoopbackPortLease

_DEFAULT_EXTERNAL_HOST = "127.0.0.1"


@dataclass
class ExternalComfyFixture:
    """Describe the deterministic external Comfy fixture used by attach scenarios."""

    workspace_root: Path
    endpoint: ComfyEndpoint
    _endpoint_lease: LoopbackPortLease | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def reserve_endpoint(self) -> None:
        """Retain the configured endpoint across fixture preparation."""

        if self._endpoint_lease is None:
            self._endpoint_lease = LoopbackPortLease.acquire(
                candidate_ports=(self.endpoint.port,),
            )

    def release_endpoint_for_launch(self) -> None:
        """Release the retained endpoint immediately before Comfy starts."""

        self.reserve_endpoint()
        assert self._endpoint_lease is not None
        self._endpoint_lease.release_for_handoff()
        self._endpoint_lease = None

    def close(self) -> None:
        """Release an endpoint reservation that never reached process handoff."""

        if self._endpoint_lease is not None:
            self._endpoint_lease.close()
            self._endpoint_lease = None


def build_external_fixture(
    paths: ScenarioPaths,
    *,
    port_factory: Callable[[], int] | None = None,
) -> ExternalComfyFixture:
    """Create one run-owned external-Comfy fixture with an allocated endpoint."""

    if port_factory is None:
        endpoint_lease = LoopbackPortLease.acquire()
        endpoint_port = endpoint_lease.port
    else:
        endpoint_lease = None
        endpoint_port = port_factory()
    return ExternalComfyFixture(
        workspace_root=paths.external_comfy_root,
        endpoint=ComfyEndpoint(
            host=_DEFAULT_EXTERNAL_HOST,
            port=endpoint_port,
        ),
        _endpoint_lease=endpoint_lease,
    )


def reset_external_comfy_root(fixture: ExternalComfyFixture) -> Path:
    """Delete and recreate one externally owned Comfy workspace."""

    fixture.reserve_endpoint()
    if fixture.workspace_root.exists():
        shutil.rmtree(fixture.workspace_root, onexc=_clear_readonly_and_retry)
    fixture.workspace_root.mkdir(parents=True, exist_ok=True)
    return fixture.workspace_root


def _clear_readonly_and_retry(
    func: Callable[..., object],
    path: str,
    exc_info: BaseException,
) -> None:
    """Clear the readonly bit for fixture cleanup and retry the failed removal."""

    _ = exc_info
    os.chmod(path, 0o666)
    func(path)


def provision_external_comfy_workspace(fixture: ExternalComfyFixture) -> Path:
    """Provision one run-owned external Comfy workspace."""

    fixture.reserve_endpoint()
    fixture.workspace_root.parent.mkdir(parents=True, exist_ok=True)
    return ensure_managed_comfy_setup(
        workspace=fixture.workspace_root,
    )


def launch_external_comfy_fixture(
    fixture: ExternalComfyFixture,
) -> ManagedProcessHandle:
    """Launch one run-owned fixture and wait for its allocated endpoint."""

    fixture.release_endpoint_for_launch()
    process = start_managed_comfy_subprocess(
        endpoint=fixture.endpoint,
        workspace=fixture.workspace_root,
        runtime_state_dir=fixture.workspace_root / "appdata" / "runtime_state",
    )
    if not wait_for_ready(fixture.endpoint.host, fixture.endpoint.port, timeout=120.0):
        raise RuntimeError(
            "External Comfy fixture did not become ready before the timeout."
        )
    return process
