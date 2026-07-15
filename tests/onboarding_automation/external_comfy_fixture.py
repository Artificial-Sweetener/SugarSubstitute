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

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_launcher import (
    start_managed_comfy_subprocess,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_readiness import wait_for_ready
from tests.onboarding_automation.fixture_paths import resolve_scenario_paths

_DEFAULT_EXTERNAL_HOST = "127.0.0.1"
_DEFAULT_EXTERNAL_PORT = 8190


@dataclass(frozen=True)
class ExternalComfyFixture:
    """Describe the deterministic external Comfy fixture used by attach scenarios."""

    workspace_root: Path
    endpoint: ComfyEndpoint


def build_external_fixture() -> ExternalComfyFixture:
    """Return the deterministic external Comfy fixture configuration."""

    paths = resolve_scenario_paths()
    return ExternalComfyFixture(
        workspace_root=paths.external_comfy_root,
        endpoint=ComfyEndpoint(
            host=_DEFAULT_EXTERNAL_HOST,
            port=_DEFAULT_EXTERNAL_PORT,
        ),
    )


def reset_external_comfy_root() -> Path:
    """Delete and recreate the external Comfy test root."""

    fixture = build_external_fixture()
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


def provision_external_comfy_workspace() -> Path:
    """Provision the deterministic external Comfy workspace contents."""

    fixture = build_external_fixture()
    fixture.workspace_root.parent.mkdir(parents=True, exist_ok=True)
    return ensure_managed_comfy_setup(
        workspace=fixture.workspace_root,
    )


def launch_external_comfy_fixture() -> ManagedProcessHandle:
    """Launch the deterministic external Comfy fixture and wait for readiness."""

    fixture = build_external_fixture()
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


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for external Comfy fixture tasks."""

    parser = argparse.ArgumentParser(
        description="Manage the external Comfy fixture used by attach-local tests.",
    )
    parser.add_argument(
        "command",
        choices=("reset", "provision", "launch"),
        help="Fixture command to run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one external Comfy fixture command."""

    args = build_argument_parser().parse_args(argv)
    if args.command == "reset":
        print(reset_external_comfy_root())
        return 0
    if args.command == "provision":
        print(provision_external_comfy_workspace())
        return 0
    process = launch_external_comfy_fixture()
    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
