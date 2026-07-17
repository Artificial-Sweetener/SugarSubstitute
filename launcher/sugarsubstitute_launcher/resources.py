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

"""Resolve launcher-owned visual resources without importing the app payload."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from launcher.sugarsubstitute_launcher.platforms import (
    LauncherTarget,
    detect_launcher_target,
)


def launcher_icon_path() -> Path:
    """Return the best available app icon path for launcher UI and packaging."""

    target = detect_launcher_target()
    icon_name = target.icon_asset_name
    packaged_root = Path(getattr(sys, "_MEIPASS", ""))
    packaged_icon = packaged_root / "launcher_assets" / icon_name
    if packaged_icon.is_file():
        return packaged_icon

    source_icon = launcher_icon_source_path(target=target)
    if source_icon.is_file():
        return source_icon
    raise FileNotFoundError(f"Launcher app icon is missing: {source_icon}")


def launcher_icon() -> QIcon:
    """Return the launcher window icon."""

    return QIcon(str(launcher_icon_path()))


def launcher_icon_source_path(*, target: LauncherTarget | None = None) -> Path:
    """Return the source icon best suited to the target packaging format."""

    resolved_target = target or detect_launcher_target()
    icon_name = resolved_target.icon_asset_name
    icon_path = (
        Path(__file__).resolve().parents[2]
        / "substitute"
        / "presentation"
        / "resources"
        / "app_icons"
        / icon_name
    )
    if not icon_path.is_file():
        raise FileNotFoundError(f"Launcher app icon is missing: {icon_path}")
    return icon_path
