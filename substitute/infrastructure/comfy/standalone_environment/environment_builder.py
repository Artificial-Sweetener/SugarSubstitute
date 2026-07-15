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
        """Create the active venv and copy the verified package set into it."""

        layout.validate_master()
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
            )
            if result.returncode != 0:
                raise StandaloneArtifactError(
                    "Bundled uv could not create the managed virtual environment: "
                    f"{result.stderr.strip()}"
                )
            self._directory_copier.copy(
                layout.master_site_packages(),
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
        return layout.virtual_python
