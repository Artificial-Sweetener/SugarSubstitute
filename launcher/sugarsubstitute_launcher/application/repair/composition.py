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

"""Compose repair adapters from the detached helper's verified runtime resources."""

from __future__ import annotations

from collections.abc import Callable

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.platforms import LauncherTarget
from launcher.sugarsubstitute_launcher.runtime import UvManagedRuntimeInstaller
from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgressObserver,
)
from launcher.sugarsubstitute_launcher.runtime_resources import launcher_uv_path
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider


def build_repair_execution_service(
    *,
    target: LauncherTarget,
    progress_observer: RepairProgressObserver | None = None,
    output_callback: Callable[[str], None] | None = None,
) -> RepairExecutionService:
    """Bind independent tooling and real work feedback to the repair executor."""
    return RepairExecutionService(
        runtime_provisioner=UvManagedRuntimeInstaller(
            uv_provider=VerifiedUvExecutableProvider(
                bundled_uv_path=launcher_uv_path(target=target)
            ),
            runner=SubprocessRuntimeCommandRunner(output_callback=output_callback),
        ),
        progress_observer=progress_observer,
    )
