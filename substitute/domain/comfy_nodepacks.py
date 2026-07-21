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

"""Define core Comfy custom nodepack identifiers managed by Substitute."""

from __future__ import annotations

from enum import Enum

SUBSTITUTE_BACKEND_REQUIRED_VERSION = "1.8.0"
SUGARCUBES_REQUIRED_VERSION = "0.11.0"


class CoreNodepackId(str, Enum):
    """Identify core Comfy nodepacks that Substitute can install or refresh."""

    SUBSTITUTE_BACKEND = "substitute-backend"
    SUGARCUBES = "SugarCubes"
