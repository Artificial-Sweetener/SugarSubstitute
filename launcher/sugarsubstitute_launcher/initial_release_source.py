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

"""Select the immutable release source used by initial installation."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher import __version__ as LAUNCHER_VERSION
from launcher.sugarsubstitute_launcher.release_discovery import (
    discover_local_release_root,
    discover_packaged_release_root,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    LocalFolderReleaseSource,
    ReleaseSource,
    production_installer_release_source,
)


def resolve_initial_install_release_source(
    *,
    frozen_setup: bool,
    release_version: str = LAUNCHER_VERSION,
) -> ReleaseSource:
    """Choose an embedded, version-bound production, or source-run channel."""

    packaged_release_root = discover_packaged_release_root()
    if packaged_release_root is not None:
        return LocalFolderReleaseSource(packaged_release_root)
    if frozen_setup:
        return production_installer_release_source(release_version)
    return LocalFolderReleaseSource(discover_local_release_root())


__all__ = ["resolve_initial_install_release_source"]
