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

"""Identify workspace admission failures without classifying diagnostic strings."""

from __future__ import annotations

from enum import Enum


class ManagedWorkspaceConflict(str, Enum):
    """Distinguish reusable Comfy installations from other occupied folders."""

    EXISTING_INSTALLATION = "existing_installation"
    OCCUPIED_FOLDER = "occupied_folder"


class ManagedWorkspaceConflictError(RuntimeError):
    """Preserve the recovery category of a rejected managed workspace."""

    def __init__(self, reason: ManagedWorkspaceConflict, detail: str) -> None:
        """Retain typed recovery intent independently of diagnostic wording."""
        self.reason = reason
        super().__init__(detail)
