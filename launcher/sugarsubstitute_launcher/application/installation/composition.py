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

"""Compose concrete adapters for the launcher installation workflow."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.process import start_detached_handoff
from launcher.sugarsubstitute_launcher.runtime import UvManagedRuntimeInstaller
from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.runtime_resources import launcher_uv_path
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider


def build_installation_workflow(
    *,
    output_callback: Callable[[str], None] | None = None,
    process_starter: Callable[[Sequence[str]], None] = start_detached_handoff,
) -> InstallationWorkflow:
    """Build the production installation workflow and its concrete adapters."""

    return InstallationWorkflow(
        layout_preparer=LayoutInstaller(),
        artifact_installer=FirstRunInstaller(),
        runtime_provisioner=UvManagedRuntimeInstaller(
            uv_provider=VerifiedUvExecutableProvider(
                bundled_uv_path=launcher_uv_path()
            ),
            runner=SubprocessRuntimeCommandRunner(output_callback),
        ),
        process_starter=process_starter,
    )
