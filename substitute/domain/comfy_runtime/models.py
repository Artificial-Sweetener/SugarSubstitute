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

"""Define Comfy runtime facts shared by diagnostics and Settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComfyRuntimeInfo:
    """Describe runtime facts read from Comfy `/system_stats`."""

    comfy_version: str = ""
    os_name: str = ""
    python_version: str = ""
    embedded_python: str = ""
    pytorch_version: str = ""
    devices: tuple[str, ...] = ()
    launch_args: tuple[str, ...] = ()


__all__ = ["ComfyRuntimeInfo"]
