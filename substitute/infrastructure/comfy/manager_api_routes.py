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

"""Select HTTP routes owned by each supported Manager runtime family."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.comfy_manager import ComfyManagerKind


@dataclass(frozen=True, slots=True)
class ComfyManagerApiRoutes:
    """Describe installed and optional catalog endpoints for one runtime."""

    installed: str
    catalog: str | None

    @classmethod
    def for_kind(cls, kind: ComfyManagerKind) -> ComfyManagerApiRoutes:
        """Return routes registered by the selected Manager server."""

        if kind is ComfyManagerKind.INTEGRATED:
            return cls(installed="/v2/customnode/installed", catalog=None)
        return cls(
            installed="/customnode/installed",
            catalog="/customnode/getlist?mode=cache&skip_update=true",
        )


__all__ = ["ComfyManagerApiRoutes"]
