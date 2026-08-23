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
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from socket import AF_INET, SOCK_STREAM, socket

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

_DEFAULT_EXTERNAL_HOST = "127.0.0.1"


@dataclass(frozen=True)
class ExternalComfyFixture:
    """Describe the deterministic external Comfy fixture used by attach scenarios."""

    workspace_root: Path
    endpoint: ComfyEndpoint


def _allocate_loopback_port() -> int:
    """Ask the operating system for one available loopback port."""

    with socket(AF_INET, SOCK_STREAM) as probe:
        probe.bind((_DEFAULT_EXTERNAL_HOST, 0))
        return int(probe.getsockname()[1])


def build_external_fixture(
    paths: ScenarioPaths,
    *,
    port_factory: Callable[[], int] = _allocate_loopback_port,
) -> ExternalComfyFixture:
    """Create one run-owned external-Comfy fixture with an allocated endpoint."""

    return ExternalComfyFixture(
        workspace_root=paths.external_comfy_root,
        endpoint=ComfyEndpoint(
            host=_DEFAULT_EXTERNAL_HOST,
            port=port_factory(),
        ),
    )


def reset_external_comfy_root(fixture: ExternalComfyFixture) -> Path:
    """Delete and recreate one externally owned Comfy workspace."""

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

    fixture.workspace_root.parent.mkdir(parents=True, exist_ok=True)
    return ensure_managed_comfy_setup(
        workspace=fixture.workspace_root,
    )


def launch_external_comfy_fixture(
    fixture: ExternalComfyFixture,
) -> ManagedProcessHandle:
    """Launch one run-owned fixture and wait for its allocated endpoint."""

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
