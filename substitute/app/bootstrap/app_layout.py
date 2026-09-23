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

        return cls.installed_at(install_root / "app")

    @classmethod
    def installed_at(cls, app_dir: Path) -> Self:
        """Build an installed source-payload layout at an exact app directory."""

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


def resolve_app_layout(
    install_root: Path,
    *,
    entrypoint_path: Path | None = None,
) -> AppLayout:
    """Resolve legacy or generation-backed installed app payload paths."""

    resolved_root = install_root.resolve()
    installed_layout = AppLayout.installed(resolved_root)
    if _is_complete_layout(installed_layout):
        return installed_layout

    resolved_entrypoint = (
        entrypoint_path.resolve()
        if entrypoint_path is not None
        else (_repo_root() / "main.py").resolve()
    )
    generation_layout = AppLayout.installed_at(resolved_entrypoint.parent)
    if _is_managed_generation_layout(resolved_root, generation_layout):
        return generation_layout
    return AppLayout.source_checkout(_repo_root())


def _is_complete_layout(layout: AppLayout) -> bool:
    """Return whether an app layout contains its required launch inputs."""

    return layout.entrypoint_path.is_file() and layout.requirements_path.is_file()


def _is_managed_generation_layout(install_root: Path, layout: AppLayout) -> bool:
    """Return whether a complete layout is an immutable launcher generation."""

    try:
        relative_app_dir = layout.app_dir.relative_to(install_root)
    except ValueError:
        return False
    parts = relative_app_dir.parts
    if len(parts) != 5 or parts[:3] != (
        "launcher",
        "releases",
        "generations",
    ):
        return False
    generation = parts[3]
    return (
        len(generation) == 32
        and all(character in "0123456789abcdef" for character in generation)
        and parts[4] == "app"
        and _is_complete_layout(layout)
    )


def _repo_root() -> Path:
    """Return the repository root for source-checkout execution."""

    return Path(__file__).resolve().parents[3]
