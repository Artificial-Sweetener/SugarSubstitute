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

"""Expose focused release-asset construction services."""

from tools.release_assets.assembly import build_local_release_channel
from tools.release_assets.launcher_archive import build_installed_launcher_zip
from tools.release_assets.models import (
    LocalReleaseBuildResult,
    NativeInstallerInput,
    PlatformReleaseInput,
    ReleaseAsset,
)
from tools.release_assets.payload import (
    RUNTIME_REQUIRED_ROOTS,
    build_app_payload_zip,
    inspect_payload_zip,
)
from tools.release_assets.release_metadata import sha256_file

__all__ = [
    "LocalReleaseBuildResult",
    "NativeInstallerInput",
    "PlatformReleaseInput",
    "RUNTIME_REQUIRED_ROOTS",
    "ReleaseAsset",
    "build_app_payload_zip",
    "build_installed_launcher_zip",
    "build_local_release_channel",
    "inspect_payload_zip",
    "sha256_file",
]
