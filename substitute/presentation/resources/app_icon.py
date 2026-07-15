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

"""Expose SugarSubstitute-owned icon resources."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon

    from substitute.presentation.resources.fluent_app_icon import AppIcon

_APP_ICON_DIR = Path(__file__).resolve().parent / "app_icons"

APP_ICON_RESOURCE_PREFIX = ":/substitute/app/icon"
APP_ICON_RESOURCE_SIZES: tuple[int, ...] = (16, 20, 24, 32, 40, 48, 64, 128, 256)
APP_ICON_ICO_PATH = _APP_ICON_DIR / "app_icon.ico"


def app_icon_resource_path(size: int) -> str:
    """Return the Qt resource path for one generated app icon size."""

    if size not in APP_ICON_RESOURCE_SIZES:
        raise ValueError(f"Unsupported app icon resource size: {size}")
    return f"{APP_ICON_RESOURCE_PREFIX}/{size}.png"


def application_icon() -> QIcon:
    """Return the multi-size Qt resource-backed application icon."""

    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from substitute.presentation.resources import app_icons_rc

    _ = app_icons_rc
    icon = QIcon()
    for size in APP_ICON_RESOURCE_SIZES:
        icon.addFile(app_icon_resource_path(size), QSize(size, size))
    return icon


def application_icon_ico_path() -> Path:
    """Return the generated Windows executable icon path."""

    if not APP_ICON_ICO_PATH.is_file():
        raise FileNotFoundError(f"Missing Windows app icon asset: {APP_ICON_ICO_PATH}")
    return APP_ICON_ICO_PATH


def __getattr__(name: str) -> object:
    """Resolve Fluent icon exports without loading qfluentwidgets during startup."""

    if name == "AppIcon":
        from substitute.presentation.resources.fluent_app_icon import AppIcon

        globals()[name] = AppIcon
        return AppIcon
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "APP_ICON_ICO_PATH",
    "APP_ICON_RESOURCE_PREFIX",
    "APP_ICON_RESOURCE_SIZES",
    "AppIcon",
    "app_icon_resource_path",
    "application_icon",
    "application_icon_ico_path",
]
