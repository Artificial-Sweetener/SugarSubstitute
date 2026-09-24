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

"""Model transient SugarCubes classifications for workflow-embedded Cubes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WorkflowCubeLibraryClass(StrEnum):
    """Identify an exact workflow Cube's strongest machine-local relationship."""

    NONE = "none"
    CAPTURED = "captured"
    LOCAL = "local"
    SYNCED = "synced"


class WorkflowCubeAccess(StrEnum):
    """Describe whether a related library source permits definition editing."""

    READ_ONLY = "read_only"
    WRITABLE = "writable"


@dataclass(frozen=True, slots=True)
class WorkflowCubeClassification:
    """Describe machine-local state without replacing embedded workflow truth."""

    definition_id: str
    cube_id: str
    cube_version: str
    semantic_hash: str
    instance_ids: tuple[str, ...]
    primary_class: WorkflowCubeLibraryClass
    access: WorkflowCubeAccess
    source_available: bool
    permitted_operations: frozenset[str]

    @property
    def can_capture(self) -> bool:
        """Return whether SugarCubes permits exact capture of this definition."""

        return "capture" in self.permitted_operations


@dataclass(frozen=True, slots=True)
class WorkflowCubeClassificationReport:
    """Collect transient classifications for one canonical workflow graph."""

    definitions: tuple[WorkflowCubeClassification, ...]

    def for_definition(
        self,
        definition_id: str,
    ) -> WorkflowCubeClassification | None:
        """Return the classification for one embedded definition identifier."""

        return next(
            (
                classification
                for classification in self.definitions
                if classification.definition_id == definition_id
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class WorkflowCubeCaptureResult:
    """Report exact capture persistence and its refreshed classification."""

    cube_id: str
    cube_version: str
    semantic_hash: str
    created: bool
    classification: WorkflowCubeClassification


__all__ = [
    "WorkflowCubeAccess",
    "WorkflowCubeCaptureResult",
    "WorkflowCubeClassification",
    "WorkflowCubeClassificationReport",
    "WorkflowCubeLibraryClass",
]
