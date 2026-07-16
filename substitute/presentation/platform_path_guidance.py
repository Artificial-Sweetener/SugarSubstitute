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

"""Provide platform path examples without developer-machine assumptions."""

from __future__ import annotations

import sys


def substitute_install_example() -> str:
    """Return a writable installation example for the current platform."""

    if sys.platform == "win32":
        return r"%USERPROFILE%\SugarSubstitute"
    if sys.platform == "darwin":
        return "~/Applications/SugarSubstitute"
    return "~/.local/share/SugarSubstitute"


def managed_comfy_example() -> str:
    """Return a managed Comfy example beneath the product installation."""

    separator = "\\" if sys.platform == "win32" else "/"
    return f"{substitute_install_example()}{separator}comfyui"


def existing_comfy_example() -> str:
    """Return an existing-Comfy example for the current platform."""

    if sys.platform == "win32":
        return r"%USERPROFILE%\ComfyUI"
    return "~/ComfyUI"


__all__ = [
    "existing_comfy_example",
    "managed_comfy_example",
    "substitute_install_example",
]
