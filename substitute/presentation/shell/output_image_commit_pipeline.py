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

"""Define immutable DTOs for asynchronous output image commits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage

from substitute.application.workflows.output_visual_events import LiveFinalOutputEvent
from substitute.domain.generation import OutputResultPosition


@dataclass(frozen=True, slots=True)
class OutputImageCommitRequest:
    """Capture narrow final-output metadata before preparation starts."""

    workflow_id: str
    file_path: Path | None
    node_id: str
    node_meta_title: str
    workflow_name: str
    source_key: str
    source_label: str
    image_bytes: bytes = b""
    generation_run_id: str | None = None
    prompt_id: str | None = None
    client_id: str | None = None
    position: OutputResultPosition | None = None
    artifact_width: int | None = None
    artifact_height: int | None = None
    live_event: LiveFinalOutputEvent | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None
    cube_execution_duration_ms: float | None = None


@dataclass(frozen=True, slots=True)
class PreparedOutputImage:
    """Carry a decoded final output image back to the GUI thread."""

    request: OutputImageCommitRequest
    image: QImage


@dataclass(frozen=True, slots=True)
class FailedOutputImagePreparation:
    """Carry final-output decode failures back to GUI-thread presentation."""

    request: OutputImageCommitRequest
    message: str
    detail: str | None = None


__all__ = [
    "FailedOutputImagePreparation",
    "OutputImageCommitRequest",
    "PreparedOutputImage",
]
