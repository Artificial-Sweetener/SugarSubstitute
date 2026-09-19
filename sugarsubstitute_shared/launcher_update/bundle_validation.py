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

"""Validate launcher payload completeness independently of staging and activation."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget


class LauncherBundleValidationError(RuntimeError):
    """Report a launcher bundle that does not match its target contract."""


def validate_launcher_bundle(
    *,
    bundle_dir: Path,
    target: LauncherBundleTarget,
    allow_installation_content: bool = False,
) -> None:
    """Validate required paths and reject unexpected top-level content."""

    if not (bundle_dir / target.executable_relative_path).is_file():
        raise LauncherBundleValidationError(
            "Launcher bundle is missing its target executable."
        )
    if not (bundle_dir / target.support_relative_path).is_dir():
        raise LauncherBundleValidationError(
            "Launcher bundle is missing its runtime support directory."
        )
    missing_files = [
        str(path)
        for path in target.required_file_relative_paths
        if not (bundle_dir / path).is_file()
    ]
    if missing_files:
        raise LauncherBundleValidationError(
            "Launcher bundle is missing required files: " + ", ".join(missing_files)
        )
    missing_roots = [
        str(path)
        for path in target.replacement_roots
        if not (bundle_dir / path).exists()
    ]
    if missing_roots:
        raise LauncherBundleValidationError(
            "Launcher bundle is missing replacement roots: " + ", ".join(missing_roots)
        )
    if allow_installation_content:
        return
    allowed_roots = {path.parts[0] for path in target.replacement_roots}
    unexpected = sorted(
        child.name for child in bundle_dir.iterdir() if child.name not in allowed_roots
    )
    if unexpected:
        raise LauncherBundleValidationError(
            f"Launcher bundle contains unexpected roots: {', '.join(unexpected)}"
        )
