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

"""Share launcher bundle update contracts between the app and launcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sugarsubstitute_shared.launcher_update.models import (
    LauncherBundleAsset,
    LauncherInstallationRecord,
    LauncherRelease,
    LauncherUpdateRequest,
)
from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    detect_launcher_bundle_target,
    launcher_bundle_target_for_key,
)

if TYPE_CHECKING:
    from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager


def __getattr__(name: str) -> object:
    """Load network-backed update services only when explicitly requested."""

    if name == "LauncherBundleStager":
        from sugarsubstitute_shared.launcher_update.staging import (
            LauncherBundleStager as launcher_bundle_stager,
        )

        return launcher_bundle_stager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LauncherBundleAsset",
    "LauncherBundleStager",
    "LauncherBundleTarget",
    "LauncherInstallationRecord",
    "LauncherRelease",
    "LauncherUpdateRequest",
    "detect_launcher_bundle_target",
    "launcher_bundle_target_for_key",
    "schedule_launcher_update",
]
