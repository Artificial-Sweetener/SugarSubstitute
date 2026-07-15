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

"""Create the initial launcher-owned install layout."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstallPreparationResult:
    """Describe the layout and config created by installer preparation."""

    layout: InstallLayout
    config: LauncherConfig


class LayoutInstaller:
    """Prepare the local install root before payload/runtime milestones run."""

    def prepare(self, install_root: Path) -> InstallPreparationResult:
        """Create base directories and persist the first launcher config."""

        layout = InstallLayout.from_root(install_root)
        layout.create_base_directories()
        config = LauncherConfig.from_layout(layout=layout)
        config.save(layout.config_path)
        _LOGGER.info(
            "Prepared launcher install layout.",
            extra={"install_root": str(layout.root)},
        )
        return InstallPreparationResult(layout=layout, config=config)
