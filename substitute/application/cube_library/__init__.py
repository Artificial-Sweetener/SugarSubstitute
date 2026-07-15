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

"""Application services for active-target Cube Library management."""

from substitute.application.cube_library.service import (
    CubeDependencyRepairProposal,
    CubeLibraryManagementService,
    CubeLibrarySnapshot,
)
from substitute.application.cube_library.update_coordinator import (
    CubeLibraryUpdateCoordinator,
)
from substitute.application.cube_library.update_detection import (
    CubeLibraryUpdateDetectionService,
    CubeLibraryUpdateReason,
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateGroup,
    LoadedCubeUpdateSelection,
    group_loaded_cube_update_candidates_by_current_version,
)
from substitute.domain.cube_library import (
    CubePackPreflight,
    CubePackRecord,
    CubeUpdatePolicy,
    CubeVersionIdentity,
)

__all__ = [
    "CubeLibraryManagementService",
    "CubeLibrarySnapshot",
    "CubeDependencyRepairProposal",
    "CubeLibraryUpdateCoordinator",
    "CubeLibraryUpdateDetectionService",
    "CubeLibraryUpdateReason",
    "CubeUpdatePolicy",
    "CubeVersionIdentity",
    "LoadedCubeUpdateAction",
    "CubePackPreflight",
    "CubePackRecord",
    "LoadedCubeUpdateCandidate",
    "LoadedCubeUpdateGroup",
    "LoadedCubeUpdateSelection",
    "group_loaded_cube_update_candidates_by_current_version",
]
