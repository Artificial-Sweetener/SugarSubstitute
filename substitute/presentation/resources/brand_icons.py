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

"""Expose third-party brand icon assets used by presentation widgets."""

from __future__ import annotations

from pathlib import Path

QT_LOGO_ICON_PATH = Path(__file__).resolve().parent / "icons" / "QtLogoNeon.png"


def qt_logo_icon_path() -> Path:
    """Return the vendored Qt logo asset path for factual Qt dependency links."""

    if not QT_LOGO_ICON_PATH.is_file():
        raise FileNotFoundError(f"Missing Qt logo asset: {QT_LOGO_ICON_PATH}")
    return QT_LOGO_ICON_PATH


__all__ = ["QT_LOGO_ICON_PATH", "qt_logo_icon_path"]
