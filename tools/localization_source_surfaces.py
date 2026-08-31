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

"""Own source-surface configuration for localization extraction."""

from __future__ import annotations

from pathlib import Path


def application_source_roots(project_root: Path) -> tuple[Path, ...]:
    """Return source roots that can own application-visible messages."""

    return (
        project_root / "substitute" / "presentation",
        project_root / "substitute" / "application",
        project_root / "substitute" / "domain",
        project_root / "substitute" / "app" / "bootstrap",
    )


def application_catalog_source_roots(project_root: Path) -> tuple[Path, ...]:
    """Return roots whose explicit markers feed the AppText catalog."""

    return (
        *application_source_roots(project_root),
        project_root / "substitute" / "infrastructure",
    )


def shared_application_catalog_source_roots(
    project_root: Path,
) -> tuple[Path, ...]:
    """Return shared AppText roots packaged by both executables."""

    return (
        project_root / "sugarsubstitute_shared" / "presentation",
        project_root / "sugarsubstitute_shared" / "crash_reporting",
    )


def visible_source_roots(project_root: Path) -> tuple[Path, ...]:
    """Return roots whose explicit presentation calls can expose app copy."""

    return (
        *application_catalog_source_roots(project_root),
        project_root / "launcher" / "sugarsubstitute_launcher",
        project_root / "sugarsubstitute_shared" / "presentation",
    )


__all__ = [
    "application_catalog_source_roots",
    "application_source_roots",
    "shared_application_catalog_source_roots",
    "visible_source_roots",
]
