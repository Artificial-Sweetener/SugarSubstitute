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

"""Define immutable generation result replay snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.generation.job_queue import GenerationQueueJob
from substitute.domain.workspace_snapshot import WorkspaceSnapshot

GENERATION_RESULT_SNAPSHOT_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class GenerationResultSnapshot:
    """Describe immutable workflow and output state produced by one job."""

    schema_version: str
    job_id: str
    job: GenerationQueueJob
    workspace: WorkspaceSnapshot


__all__ = [
    "GENERATION_RESULT_SNAPSHOT_SCHEMA_VERSION",
    "GenerationResultSnapshot",
]
