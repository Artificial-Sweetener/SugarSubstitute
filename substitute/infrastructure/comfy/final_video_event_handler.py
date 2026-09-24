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

"""Stream, validate, persist, and publish final generated videos."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from substitute.application.ports.comfy_gateway import OutputVideoUpdate
from substitute.infrastructure.comfy.final_image_event import FinalImageEvent
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.application.ports.video import VideoProbeResult
from substitute.infrastructure.comfy.output_video_persistence import (
    OutputVideoPersistence,
)

_VIDEO_SUFFIXES = frozenset({".avi", ".gif", ".mkv", ".mov", ".mp4", ".webm"})


class VideoArtifactStreamer(Protocol):
    """Describe bounded Comfy artifact streaming."""

    def stream_to(self, artifact: ComfyImageArtifact, destination: Path) -> int:
        """Stream one artifact into a new partial path."""


class VideoArtifactProbe(Protocol):
    """Describe decode validation and poster extraction."""

    def probe(
        self,
        path: Path,
        *,
        artifact: ComfyImageArtifact,
    ) -> VideoProbeResult:
        """Validate one local video and return normalized facts."""


@dataclass(frozen=True, slots=True)
class FinalVideoEventHandler:
    """Own video artifact delivery and typed callback construction."""

    artifact_streamer: VideoArtifactStreamer
    output_persistence: OutputVideoPersistence
    video_probe: VideoArtifactProbe
    on_output_video: Callable[[OutputVideoUpdate], None]
    _delivered_artifacts: set[tuple[str, str, int, int, str, str, str]] = field(
        default_factory=set,
        init=False,
        repr=False,
        compare=False,
    )

    def handle(self, event: FinalImageEvent) -> None:
        """Publish every non-duplicate video artifact from one output event."""

        source_identity = OutputSourceIdentity(
            node_id=event.source.node_id,
            source_key=event.source.source_key,
            source_label=event.source.source_label,
            cube_alias=event.source.cube_alias,
        )
        video_artifacts = tuple(
            artifact for artifact in event.artifacts if artifact.media_kind == "video"
        )
        for batch_index, artifact in enumerate(video_artifacts):
            delivery_key = (
                event.prompt_id,
                event.source.node_id,
                event.list_index,
                batch_index,
                artifact.filename,
                artifact.subfolder,
                artifact.type,
            )
            if delivery_key in self._delivered_artifacts:
                continue
            suffix = _video_suffix(artifact.filename)
            persisted = self.output_persistence.materialize(
                source_identity=source_identity,
                suffix=suffix,
                stream=lambda path: self.artifact_streamer.stream_to(artifact, path),
                probe=lambda path: self.video_probe.probe(path, artifact=artifact),
            )
            self._delivered_artifacts.add(delivery_key)
            self.on_output_video(
                OutputVideoUpdate(
                    workflow_id=event.workflow_id,
                    workflow_payload=event.workflow_payload,
                    file_path=persisted.file_path,
                    node_id=event.source.node_id,
                    poster_bytes=persisted.probe.poster_bytes,
                    temporary=persisted.temporary,
                    generation_run_id=event.generation_run_id,
                    prompt_id=event.prompt_id,
                    client_id=event.client_id,
                    source_key=event.source.source_key,
                    source_label=event.source.source_label,
                    list_index=event.list_index,
                    batch_index=batch_index,
                    artifact_width=persisted.probe.width,
                    artifact_height=persisted.probe.height,
                    duration_seconds=persisted.probe.duration_seconds,
                    mime_type=persisted.probe.mime_type,
                    output_session_id=event.output_session_id,
                    scene_run_id=event.scene.run_id,
                    scene_key=event.scene.key,
                    scene_title=event.scene.title,
                    scene_order=event.scene.order,
                    scene_count=event.scene.count,
                )
            )


def _video_suffix(filename: str) -> str:
    """Return a supported normalized container suffix."""

    suffix = Path(filename).suffix.lower()
    if suffix not in _VIDEO_SUFFIXES:
        raise ValueError(f"Unsupported generated video container: {suffix or '<none>'}")
    return suffix


__all__ = ["FinalVideoEventHandler", "VideoArtifactProbe", "VideoArtifactStreamer"]
