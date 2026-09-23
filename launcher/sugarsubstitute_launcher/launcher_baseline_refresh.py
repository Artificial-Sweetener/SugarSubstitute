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

"""Require the retained root to catch up before a selected launcher runs the app."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime_paths import (
    current_frozen_executable_path,
)
from sugarsubstitute_shared.launcher_update.baseline_refresh_staging import (
    LauncherBaselineRefreshStager,
)
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.process import (
    schedule_required_baseline_refresh,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions


_LOGGER = logging.getLogger(__name__)


class LauncherBaselineRefresh:
    """Gate application startup on a compatible installed launcher root."""

    def __init__(self, *, stager: LauncherBaselineRefreshStager | None = None) -> None:
        """Bind the owned staging adapter without changing installation state."""

        self._stager = stager or LauncherBaselineRefreshStager()

    def start_if_required(
        self,
        *,
        layout: InstallLayout,
        running_executable: Path | None = None,
    ) -> bool:
        """Schedule a root replacement before a newer selected launcher starts the app."""

        image = running_executable or current_frozen_executable_path()
        if image is None:
            return False
        target = launcher_bundle_target_for_key(layout.target.key)
        generation_payload = LauncherBundlePaths(layout.root).payload_for_executable(
            image, target
        )
        if generation_payload is None:
            return False
        selected = LauncherBundleSelection(layout.root, target).resolve()
        if selected.generation is None or selected.version is None:
            raise ValueError("Running launcher generation is no longer selected.")
        if selected.root.resolve() != generation_payload.resolve():
            raise ValueError("Running launcher differs from the selected generation.")
        installed = LauncherInstallationRecord.load(
            layout.root / "launcher" / "installation.json"
        )
        if installed is None or installed.target_key != target.key:
            raise ValueError("Installed launcher root has no matching version record.")
        comparison = compare_release_versions(installed.version, selected.version)
        if comparison > 0:
            raise ValueError("Selected launcher is older than the installed root.")
        if comparison == 0:
            return False
        request_path = self._stager.stage(
            install_root=layout.root,
            selected=selected,
            target=target,
        )
        helper_pid = schedule_required_baseline_refresh(
            request_path=request_path,
            helper_executable=image,
            wait_pid=os.getpid(),
        )
        _LOGGER.info(
            "Scheduled required launcher root refresh | installed_version=%s | "
            "selected_version=%s | helper_pid=%s | generation=%s",
            installed.version,
            selected.version,
            helper_pid,
            selected.generation,
        )
        return True


__all__ = ["LauncherBaselineRefresh"]
