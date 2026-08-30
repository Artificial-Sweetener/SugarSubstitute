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

"""Resolve portable managed-Comfy paths used by explicit real harnesses."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from substitute.infrastructure.comfy.workspace_python_resolver import (
    attached_comfy_python_candidates,
)

_IMAGE_TEMPLATE_PACKAGE = "comfyui_workflow_templates_media_image"


@dataclass(frozen=True, slots=True)
class ManagedComfyHarnessLayout:
    """Describe one repository-local managed Comfy runtime for real harnesses."""

    comfy_root: Path
    python_executable: Path
    environment_root: Path
    platform_name: str

    @classmethod
    def resolve(
        cls,
        repository_root: Path,
        *,
        platform_name: str | None = None,
    ) -> ManagedComfyHarnessLayout:
        """Resolve a complete managed runtime without assuming venv layout."""

        active_platform = platform_name or os.name
        comfy_root = repository_root.resolve() / "comfyui"
        if not (comfy_root / "main.py").is_file():
            raise RuntimeError(
                f"Managed Comfy entrypoint is unavailable: {comfy_root / 'main.py'}"
            )
        candidates = attached_comfy_python_candidates(
            comfy_root,
            environment={},
            platform_name=active_platform,
        )
        python_executable = next(
            (
                candidate.executable
                for candidate in candidates
                if candidate.executable.is_file()
            ),
            None,
        )
        if python_executable is None:
            raise RuntimeError(
                f"Managed Comfy Python is unavailable beneath: {comfy_root}"
            )
        resolved_python = python_executable.resolve()
        return cls(
            comfy_root=comfy_root,
            python_executable=resolved_python,
            environment_root=resolved_python.parent.parent,
            platform_name=active_platform,
        )

    def image_template_root(self) -> Path:
        """Return the installed image-workflow template directory."""

        matches = tuple(
            sorted(
                path
                for path in self.environment_root.rglob("templates")
                if path.is_dir() and path.parent.name == _IMAGE_TEMPLATE_PACKAGE
            )
        )
        if len(matches) != 1:
            raise RuntimeError(
                "Managed Comfy image template package must resolve exactly once "
                f"beneath {self.environment_root}; found {len(matches)}."
            )
        return matches[0]

    def process_creation_flags(self) -> int:
        """Return background-process flags supported by the active platform."""

        if self.platform_name != "nt":
            return 0
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


__all__ = ["ManagedComfyHarnessLayout"]
