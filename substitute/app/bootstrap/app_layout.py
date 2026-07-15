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

"""Resolve source-payload paths for source and installed app layouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class AppLayout:
    """Describe the executable source payload used by app bootstrap."""

    app_dir: Path
    entrypoint_path: Path
    requirements_path: Path
    installed_payload: bool

    @classmethod
    def installed(cls, install_root: Path) -> Self:
        """Build an installed source-payload layout."""

        app_dir = install_root / "app"
        return cls(
            app_dir=app_dir,
            entrypoint_path=app_dir / "main.py",
            requirements_path=app_dir / "requirements.txt",
            installed_payload=True,
        )

    @classmethod
    def source_checkout(cls, repo_root: Path) -> Self:
        """Build a developer source-checkout layout."""

        return cls(
            app_dir=repo_root,
            entrypoint_path=repo_root / "main.py",
            requirements_path=repo_root / "requirements.txt",
            installed_payload=False,
        )


def resolve_app_layout(install_root: Path) -> AppLayout:
    """Resolve installed app payload paths, falling back to the source checkout."""

    resolved_root = install_root.resolve()
    installed_layout = AppLayout.installed(resolved_root)
    if (
        installed_layout.entrypoint_path.is_file()
        and installed_layout.requirements_path.is_file()
    ):
        return installed_layout
    return AppLayout.source_checkout(_repo_root())


def _repo_root() -> Path:
    """Return the repository root for source-checkout execution."""

    return Path(__file__).resolve().parents[3]
