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

"""Define complete runnable model installation plans and progress."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from substitute.domain.model_recommendations.models import ModelFamilyId


@dataclass(frozen=True, slots=True)
class ModelInstallFile:
    """Describe one exact size/hash-verified file and safe destination."""

    family_id: ModelFamilyId
    artifact_kind: ModelArtifactKind
    model_id: int
    version_id: int
    display_name: str
    file_name: str
    source_url: str
    sha256: str
    size_bytes: int
    destination_dir: Path


@dataclass(frozen=True, slots=True)
class ModelInstallPlan:
    """Review complete selected recipes before any destination is reserved."""

    model_root: Path
    files: tuple[ModelInstallFile, ...]
    available_bytes: int

    @property
    def total_bytes(self) -> int:
        """Return aggregate declared transfer bytes."""

        return sum(item.size_bytes for item in self.files)

    @property
    def has_sufficient_space(self) -> bool:
        """Return whether current free space covers declared transfer bytes."""

        return self.available_bytes >= self.total_bytes


@dataclass(frozen=True, slots=True)
class ModelInstallProgress:
    """Report exact per-file and aggregate byte progress."""

    file: ModelInstallFile
    file_received_bytes: int
    file_expected_bytes: int
    aggregate_received_bytes: int
    aggregate_expected_bytes: int
    completed_files: int
    total_files: int


__all__ = [
    "ModelInstallFile",
    "ModelInstallPlan",
    "ModelInstallProgress",
]
