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

"""Hydrate an active Comfy virtual environment from a relocatable master."""

from __future__ import annotations

from collections.abc import Callable
import os
import shutil
import subprocess
from pathlib import Path

from substitute.infrastructure.comfy.standalone_environment.directory_copy import (
    ConcurrentDirectoryCopier,
    DirectoryCopyProgress,
)
from substitute.infrastructure.comfy.standalone_environment.layout import (
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
)
from substitute.infrastructure.comfy.standalone_environment.hydration_state import (
    StandaloneHydrationState,
)


class StandaloneVirtualEnvironmentBuilder:
    """Create and hydrate the active venv through bundled runtime tools."""

    def __init__(
        self,
        *,
        directory_copier: ConcurrentDirectoryCopier | None = None,
    ) -> None:
        """Store the package-tree copy owner."""

        self._directory_copier = directory_copier or ConcurrentDirectoryCopier()

    def build(
        self,
        layout: ManagedStandaloneLayout,
        *,
        on_progress: Callable[[DirectoryCopyProgress], None] | None = None,
    ) -> Path:
        """Publish runtime readiness only after its complete package copy succeeds."""

        layout.validate_master()
        source_packages = layout.master_site_packages()
        if layout.virtual_environment.resolve() != layout.workspace.resolve() / ".venv":
            raise StandaloneArtifactError(
                "Managed Python environment redirects outside its owned directory."
            )
        state = StandaloneHydrationState(layout.workspace)
        state.begin()
        if layout.virtual_environment.exists():
            shutil.rmtree(layout.virtual_environment)
        try:
            result = subprocess.run(
                [
                    str(layout.uv_executable),
                    "venv",
                    "--python",
                    str(layout.master_python),
                    str(layout.virtual_environment),
                ],
                cwd=layout.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            )
            if result.returncode != 0:
                raise StandaloneArtifactError(
                    "Bundled uv could not create the managed virtual environment: "
                    f"{result.stderr.strip()}"
                )
            self._directory_copier.copy(
                source_packages,
                layout.virtual_site_packages(),
                on_progress=on_progress,
            )
        except (OSError, subprocess.SubprocessError) as error:
            shutil.rmtree(layout.virtual_environment, ignore_errors=True)
            raise StandaloneArtifactError(
                f"Could not hydrate the managed virtual environment: {error}"
            ) from error
        if not layout.virtual_python.is_file():
            raise StandaloneArtifactError(
                f"Managed virtual environment has no Python: {layout.virtual_python}"
            )
        state.complete()
        return layout.virtual_python
