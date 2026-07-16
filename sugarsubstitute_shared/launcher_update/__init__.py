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

from sugarsubstitute_shared.launcher_update.models import (
    LauncherBundleAsset,
    LauncherInstallationRecord,
    LauncherRelease,
    LauncherUpdateRequest,
)
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    detect_launcher_bundle_target,
    launcher_bundle_target_for_key,
)

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
