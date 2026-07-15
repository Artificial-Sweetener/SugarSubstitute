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

"""Handle validated Comfy cube-output image artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from substitute.application.ports.comfy_gateway import OutputImageUpdate
from substitute.infrastructure.comfy.comfy_payload_fields import positive_int_or_none
from substitute.infrastructure.comfy.cube_output_event import (
    CubeOutputArtifact,
    SubstituteVisualIdentity,
)
from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputDiagnostic,
    CubeOutputRouteContext,
    route_cube_output_event,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)


class CubeOutputArtifactFetcher(Protocol):
    """Describe artifact bytes retrieval for cube-output handling."""

    def fetch(self, artifact: CubeOutputArtifact) -> bytes:
        """Return bytes for one Comfy artifact."""


@dataclass(frozen=True)
class DelegatingCubeOutputArtifactFetcher:
    """Resolve the current artifact fetcher when an artifact is handled."""

    artifact_fetcher_provider: Callable[[], CubeOutputArtifactFetcher]

    def fetch(self, artifact: CubeOutputArtifact) -> bytes:
        """Fetch through the currently configured artifact fetcher."""

        return self.artifact_fetcher_provider().fetch(artifact)


class CubeOutputPersistence(Protocol):
    """Describe final image persistence required by cube-output handling."""

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> "PersistedCubeOutputImage":
        """Persist final image bytes for one output source."""


class PersistedCubeOutputImage(Protocol):
    """Describe persisted image facts needed for output callbacks."""

    @property
    def file_path(self) -> Path:
        """Return the saved image path."""

    @property
    def width(self) -> int:
        """Return the decoded image width."""

    @property
    def height(self) -> int:
        """Return the decoded image height."""


@dataclass(frozen=True)
class CubeOutputEventHandler:
    """Own cube-output artifact fetch, persistence, and callback DTO creation."""

    context: CubeOutputRouteContext
    workflow_payload: dict[str, object]
    artifact_fetcher: CubeOutputArtifactFetcher
    output_persistence: CubeOutputPersistence
    identity_acceptor: Callable[
        [SubstituteVisualIdentity | None, str | None, str | None], bool
    ]
    on_output_image: Callable[[OutputImageUpdate], None]
    on_diagnostic: Callable[[CubeOutputDiagnostic], None]

    def handle(self, data: Mapping[str, object]) -> None:
        """Handle one cube-output websocket payload."""

        route_result = route_cube_output_event(
            data,
            context=self.context,
            identity_acceptor=self.identity_acceptor,
        )
        if route_result.diagnostic is not None:
            self.on_diagnostic(route_result.diagnostic)
            return
        if route_result.cube_output is None or route_result.source_identity is None:
            return
        cube_output = route_result.cube_output
        if cube_output.node_id is None or cube_output.substitute is None:
            return

        visual_identity = cube_output.substitute
        source_identity = OutputSourceIdentity(
            node_id=route_result.source_identity.node_id,
            source_key=route_result.source_identity.source_key,
            source_label=route_result.source_identity.source_label,
            cube_alias=route_result.source_identity.cube_alias,
        )
        for artifact in cube_output.artifacts:
            if artifact.media_kind != "image":
                continue
            image_bytes = self.artifact_fetcher.fetch(artifact)
            persisted = self.output_persistence.persist_output_image(
                image_bytes=image_bytes,
                source_identity=source_identity,
            )
            artifact_width = positive_int_or_none(artifact.width) or persisted.width
            artifact_height = positive_int_or_none(artifact.height) or persisted.height
            self.on_output_image(
                OutputImageUpdate(
                    workflow_id=visual_identity.workflow_id,
                    workflow_payload=self.workflow_payload,
                    file_path=persisted.file_path,
                    node_id=cube_output.node_id,
                    generation_run_id=visual_identity.generation_run_id,
                    prompt_id=self.context.prompt_id,
                    client_id=visual_identity.client_id,
                    source_key=visual_identity.source_key,
                    source_label=visual_identity.source_label,
                    list_index=cube_output.list_index,
                    artifact_width=artifact_width,
                    artifact_height=artifact_height,
                    scene_run_id=visual_identity.scene_run_id,
                    scene_key=visual_identity.scene_key,
                    scene_title=visual_identity.scene_title,
                    scene_order=visual_identity.scene_order,
                    scene_count=visual_identity.scene_count,
                )
            )


__all__ = [
    "CubeOutputArtifactFetcher",
    "CubeOutputEventHandler",
    "CubeOutputPersistence",
    "DelegatingCubeOutputArtifactFetcher",
    "PersistedCubeOutputImage",
]
