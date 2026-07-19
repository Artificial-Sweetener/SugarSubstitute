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

"""Fetch, persist, and publish transport-neutral final image artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from substitute.application.ports.comfy_gateway import OutputImageUpdate
from substitute.infrastructure.comfy.comfy_payload_fields import positive_int_or_none
from substitute.infrastructure.comfy.final_image_event import FinalImageEvent
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)


class FinalImageArtifactFetcher(Protocol):
    """Describe Comfy artifact retrieval required by final-image handling."""

    def fetch(self, artifact: ComfyImageArtifact) -> bytes:
        """Return bytes for one Comfy image artifact."""


@dataclass(frozen=True, slots=True)
class DelegatingFinalImageArtifactFetcher:
    """Resolve the current artifact fetcher when an artifact is handled."""

    artifact_fetcher_provider: Callable[[], FinalImageArtifactFetcher]

    def fetch(self, artifact: ComfyImageArtifact) -> bytes:
        """Fetch through the currently configured artifact fetcher."""

        return self.artifact_fetcher_provider().fetch(artifact)


class FinalImagePersistence(Protocol):
    """Describe final image persistence required by transport adapters."""

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> "PersistedFinalImage":
        """Persist image bytes for one source and return saved facts."""


class PersistedFinalImage(Protocol):
    """Describe decoded image facts and an optional durable path."""

    @property
    def file_path(self) -> Path | None:
        """Return the canonical PNG path when this source is persisted."""

    @property
    def width(self) -> int:
        """Return the decoded image width."""

    @property
    def height(self) -> int:
        """Return the decoded image height."""


@dataclass(frozen=True, slots=True)
class FinalImageEventHandler:
    """Own shared artifact fetch, persistence, and callback DTO construction."""

    artifact_fetcher: FinalImageArtifactFetcher
    output_persistence: FinalImagePersistence
    on_output_image: Callable[[OutputImageUpdate], None]

    def handle(self, event: FinalImageEvent) -> None:
        """Persist and publish every batch artifact from one validated event."""

        source_identity = OutputSourceIdentity(
            node_id=event.source.node_id,
            source_key=event.source.source_key,
            source_label=event.source.source_label,
            cube_alias=event.source.cube_alias,
        )
        image_artifacts = tuple(
            artifact for artifact in event.artifacts if artifact.media_kind == "image"
        )
        for batch_index, artifact in enumerate(image_artifacts):
            image_bytes = self.artifact_fetcher.fetch(artifact)
            persisted = self.output_persistence.persist_output_image(
                image_bytes=image_bytes,
                source_identity=source_identity,
            )
            self.on_output_image(
                OutputImageUpdate(
                    workflow_id=event.workflow_id,
                    workflow_payload=event.workflow_payload,
                    file_path=persisted.file_path,
                    node_id=event.source.node_id,
                    image_bytes=image_bytes,
                    generation_run_id=event.generation_run_id,
                    prompt_id=event.prompt_id,
                    client_id=event.client_id,
                    source_key=event.source.source_key,
                    source_label=event.source.source_label,
                    list_index=event.list_index,
                    batch_index=batch_index,
                    artifact_width=(
                        positive_int_or_none(artifact.width) or persisted.width
                    ),
                    artifact_height=(
                        positive_int_or_none(artifact.height) or persisted.height
                    ),
                    scene_run_id=event.scene.run_id,
                    scene_key=event.scene.key,
                    scene_title=event.scene.title,
                    scene_order=event.scene.order,
                    scene_count=event.scene.count,
                )
            )


__all__ = [
    "DelegatingFinalImageArtifactFetcher",
    "FinalImageArtifactFetcher",
    "FinalImageEventHandler",
    "FinalImagePersistence",
    "PersistedFinalImage",
]
