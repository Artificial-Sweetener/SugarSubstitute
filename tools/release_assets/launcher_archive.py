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

"""Build and validate installed-launcher update archives."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from launcher.sugarsubstitute_launcher.platforms import LauncherTarget
from launcher.sugarsubstitute_launcher.platforms import LauncherOperatingSystem
from tools.release_assets.zip_support import iter_directory_files, write_file_to_zip


def build_installed_launcher_zip(
    *,
    launcher_bundle_dir: Path,
    output_path: Path,
    target: LauncherTarget,
) -> Path:
    """Write one validated permanent-launcher bundle ZIP."""

    resolved_bundle_dir = launcher_bundle_dir.resolve()
    resolved_output_path = output_path.resolve()
    validate_installed_launcher_bundle(resolved_bundle_dir, target=target)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        resolved_output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source_path in iter_directory_files(resolved_bundle_dir):
            relative_path = source_path.relative_to(resolved_bundle_dir)
            executable_permissions = (
                0o755
                if relative_path == target.executable_relative_path
                and target.operating_system is not LauncherOperatingSystem.WINDOWS
                else None
            )
            write_file_to_zip(
                archive=archive,
                source_path=source_path,
                archive_name=relative_path.as_posix(),
                permissions=executable_permissions,
            )
    return resolved_output_path


def prepare_installed_launcher_archive(
    *,
    launcher_source: Path,
    output_path: Path,
    target: LauncherTarget,
) -> Path:
    """Build or copy one validated target launcher archive."""

    if launcher_source.is_dir():
        return build_installed_launcher_zip(
            launcher_bundle_dir=launcher_source,
            output_path=output_path,
            target=target,
        )
    if not launcher_source.is_file():
        raise FileNotFoundError(f"Launcher source does not exist: {launcher_source}")
    validate_installed_launcher_archive(launcher_source, target=target)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(launcher_source, output_path)
    return output_path


def validate_installed_launcher_bundle(
    launcher_bundle_dir: Path,
    *,
    target: LauncherTarget,
) -> None:
    """Reject launcher bundle directories missing required target paths."""

    if not launcher_bundle_dir.is_dir():
        raise ValueError(
            f"Launcher bundle directory does not exist: {launcher_bundle_dir}"
        )
    executable_path = launcher_bundle_dir / target.executable_relative_path
    support_dir = launcher_bundle_dir / target.support_relative_path
    if not executable_path.is_file():
        raise FileNotFoundError(
            "Installed launcher bundle is missing "
            f"{target.executable_relative_path}: {launcher_bundle_dir}"
        )
    if not support_dir.is_dir():
        raise FileNotFoundError(
            "Installed launcher bundle must include "
            f"{target.support_relative_path}: {launcher_bundle_dir}"
        )


def validate_installed_launcher_archive(
    archive_path: Path,
    *,
    target: LauncherTarget,
) -> None:
    """Reject launcher archives missing required target bundle entries."""

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    executable_name = target.executable_relative_path.as_posix()
    support_prefix = target.support_relative_path.as_posix().rstrip("/") + "/"
    if executable_name not in names:
        raise FileNotFoundError(
            f"Launcher archive is missing {executable_name}: {archive_path}"
        )
    if not any(name.startswith(support_prefix) for name in names):
        raise FileNotFoundError(
            f"Launcher archive is missing {support_prefix}: {archive_path}"
        )
