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

"""Retain current-session generated media records for queue result replay."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from substitute.application.ports.comfy_gateway import (
    OutputImageUpdate,
    OutputVideoUpdate,
)
from substitute.domain.generation import GenerationJobOutputRecord

GenerationOutputUpdate = OutputImageUpdate | OutputVideoUpdate


class GenerationJobOutputStore:
    """Own live output-record retention independently from queue orchestration."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        """Store the clock used to timestamp newly retained output records."""

        self._clock = clock
        self._records_by_job_id: dict[str, list[GenerationJobOutputRecord]] = {}

    def prepare_job(self, job_id: str) -> None:
        """Initialize an empty replay collection for one admitted job."""

        self._records_by_job_id[job_id] = []

    def remove_job(self, job_id: str) -> None:
        """Discard replay records when their owning queue job is removed."""

        self._records_by_job_id.pop(job_id, None)

    def records_for_job(self, job_id: str) -> tuple[GenerationJobOutputRecord, ...]:
        """Return an immutable replay snapshot for one queue job."""

        return tuple(self._records_by_job_id.get(job_id, ()))

    def append(
        self,
        *,
        job_id: str,
        event: GenerationOutputUpdate,
        sequence: int,
    ) -> None:
        """Retain one durable image or video output for current-session replay."""

        if event.file_path is None:
            return
        metadata: dict[str, object] = {
            "list_index": event.list_index,
            "batch_index": event.batch_index,
            "width": event.artifact_width,
            "height": event.artifact_height,
            "media_kind": "video" if isinstance(event, OutputVideoUpdate) else "image",
        }
        if isinstance(event, OutputVideoUpdate):
            metadata.update(
                duration_seconds=event.duration_seconds,
                mime_type=event.mime_type,
                temporary=event.temporary,
            )
        self._records_by_job_id.setdefault(job_id, []).append(
            GenerationJobOutputRecord(
                job_id=job_id,
                output_path=event.file_path,
                node_id=event.node_id,
                created_at=self._clock(),
                sequence=sequence,
                source_key=event.source_key,
                source_label=event.source_label,
                scene_run_id=event.scene_run_id,
                scene_key=event.scene_key,
                scene_title=event.scene_title,
                scene_order=event.scene_order,
                scene_count=event.scene_count,
                node_title=None,
                metadata=metadata,
            )
        )


__all__ = ["GenerationJobOutputStore", "GenerationOutputUpdate"]
