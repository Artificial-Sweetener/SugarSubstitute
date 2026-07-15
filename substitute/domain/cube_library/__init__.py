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

"""Domain models for target-owned Cube Library data."""

from substitute.domain.cube_library.models import (
    CubeCatalog,
    CubeCatalogEntry,
    CubeDependencyInstallPlanItem,
    CubeDependencyRepairRequest,
    CubeDependencyRepairResult,
    CubeDependencySyncAndCheckRequest,
    CubeDependencySyncAndCheckResult,
    CubeDependencyVersionPlanItem,
    CubeIconDescriptor,
    CubeLibraryReadiness,
    CubeLibraryStatus,
    CubeRuntimeReadiness,
    CubePackPreflight,
    CubePackRecord,
    CubeSourceMetadata,
    CubeUpdatePolicy,
    CubeVersionIdentity,
    LoadedCubeArtifact,
)

__all__ = [
    "CubeCatalog",
    "CubeCatalogEntry",
    "CubeDependencyInstallPlanItem",
    "CubeDependencyRepairRequest",
    "CubeDependencyRepairResult",
    "CubeDependencySyncAndCheckRequest",
    "CubeDependencySyncAndCheckResult",
    "CubeDependencyVersionPlanItem",
    "CubeIconDescriptor",
    "CubeLibraryReadiness",
    "CubeLibraryStatus",
    "CubeRuntimeReadiness",
    "CubePackPreflight",
    "CubePackRecord",
    "CubeSourceMetadata",
    "CubeUpdatePolicy",
    "CubeVersionIdentity",
    "LoadedCubeArtifact",
]
