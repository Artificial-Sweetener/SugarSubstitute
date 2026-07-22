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

"""Resolve the Manager contract declared by one ComfyUI checkout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ComfyManagerContract:
    """Expose Manager paths and launch capabilities owned by ComfyUI."""

    workspace: Path

    @property
    def legacy_directory(self) -> Path:
        """Return the legacy ComfyUI-Manager custom-node directory."""

        return self.workspace / "custom_nodes" / "ComfyUI-Manager"

    @property
    def legacy_cli_path(self) -> Path:
        """Return the legacy Manager CLI script path."""

        return self.legacy_directory / "cm-cli.py"

    @property
    def integrated_requirements_path(self) -> Path:
        """Return the Manager requirements file shipped by ComfyUI."""

        return self.workspace / "manager_requirements.txt"

    @property
    def supports_integrated_manager(self) -> bool:
        """Return whether ComfyUI declares the integrated Manager contract."""

        cli_args_path = self.workspace / "comfy" / "cli_args.py"
        if (
            not self.integrated_requirements_path.is_file()
            or not cli_args_path.is_file()
        ):
            return False
        try:
            return "--enable-manager" in cli_args_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return False


__all__ = ["ComfyManagerContract"]
