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

"""Expose host appearance and native-material infrastructure adapters."""

from substitute.infrastructure.appearance.system_appearance_factory import (
    build_system_appearance_provider,
)
from substitute.infrastructure.appearance.window_material_probe import (
    probe_window_material_capabilities,
)

__all__ = [
    "build_system_appearance_provider",
    "probe_window_material_capabilities",
]
