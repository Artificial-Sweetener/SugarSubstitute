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

"""Own persisted launcher state produced by a successful repair."""

from __future__ import annotations
from typing import Protocol
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.config import (
    CANARY_RELEASE_CHANNEL,
    DEFAULT_CANARY_RELEASE_MANIFEST_URL,
    DEFAULT_RELEASE_MANIFEST_URL,
    RELEASE_SOURCE_KIND_GITHUB,
    LauncherConfig,
    ReleaseSourceConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from launcher.sugarsubstitute_launcher.application.repair.execution_result import (
    RepairExecutionError,
)


class RepairInstallationStateWriter(Protocol):
    """Recreate and validate launcher state inside the transaction boundary."""

    def write(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Write fresh state for the repaired exact version."""

    def validate(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Raise unless persisted state identifies the repaired version."""


class FreshRepairInstallationStateWriter:
    """Own fresh launcher configuration and exact installed-version records."""

    def write(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Create default channel configuration and exact version records."""

        manifest_url = (
            DEFAULT_CANARY_RELEASE_MANIFEST_URL
            if request.channel == CANARY_RELEASE_CHANNEL
            else DEFAULT_RELEASE_MANIFEST_URL
        )
        LauncherConfig.from_layout(
            layout=layout,
            channel=request.channel,
            release_source=ReleaseSourceConfig(
                kind=RELEASE_SOURCE_KIND_GITHUB,
                manifest_url=manifest_url,
            ),
        ).save(layout.config_path)
        LauncherUpdateState().with_installed_payload(
            version=request.version,
            channel=request.channel,
        ).save(layout.state_path)
        LauncherInstallationRecord(
            version=request.version,
            target_key=request.target_key,
        ).save(layout.launcher_installation_path)

    def validate(
        self,
        *,
        layout: InstallLayout,
        request: PreparedRepairRequest,
    ) -> None:
        """Verify config and both exact installed-version records."""

        config = LauncherConfig.load(layout.config_path)
        state = LauncherUpdateState.load(layout.state_path)
        launcher = LauncherInstallationRecord.load(layout.launcher_installation_path)
        if (
            config.install_root.resolve() != layout.root
            or config.channel != request.channel
            or state.installed_app_version != request.version
            or launcher is None
            or launcher.version != request.version
            or launcher.target_key != request.target_key
        ):
            raise RepairExecutionError(
                "Repaired launcher state does not match the prepared release."
            )
