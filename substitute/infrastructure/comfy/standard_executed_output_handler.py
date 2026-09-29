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

"""Adapt standard Comfy executed payloads into typed final-output events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.ports.comfy_gateway import ListenerOutputSource
from substitute.domain.output_media import OutputMediaKind
from substitute.infrastructure.comfy.comfy_image_artifact_parser import (
    parse_comfy_image_artifacts,
)
from substitute.infrastructure.comfy.comfy_video_artifact_parser import (
    parse_comfy_video_artifacts,
)
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageScene,
    FinalImageSource,
)
from substitute.infrastructure.comfy.final_output_event_sink import (
    FinalOutputEventSink,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.standard_executed_output_handler")


@dataclass(frozen=True, slots=True)
class StandardExecutedOutputContext:
    """Carry listener identity used to validate standard output events."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    workflow_payload: dict[str, object]
    scene: FinalImageScene
    output_session_id: str | None = None


@dataclass(frozen=True, slots=True)
class StandardExecutedOutputHandler:
    """Recognize declared image and video sources and dispatch their artifacts."""

    context: StandardExecutedOutputContext
    sources_by_node: Mapping[str, ListenerOutputSource]
    final_image_handler: FinalOutputEventSink
    final_video_handler: FinalOutputEventSink

    def handle(self, data: Mapping[str, object]) -> bool:
        """Handle one standard executed event owned by a declared source."""

        node_id = _optional_node_id(data.get("node"))
        if node_id is None or node_id not in self.sources_by_node:
            return False
        if data.get("prompt_id") != self.context.prompt_id:
            return False
        source = self.sources_by_node[node_id]
        artifacts = _parse_artifacts(source.media_kind, data.get("output"))
        if artifacts is None:
            log_warning(
                _LOGGER,
                "Ignored malformed executed output",
                workflow_id=self.context.workflow_id,
                generation_run_id=self.context.generation_run_id,
                prompt_id=self.context.prompt_id,
                node_id=node_id,
                media_kind=source.media_kind.value,
            )
            return True
        if not artifacts:
            return True
        event = FinalImageEvent(
            workflow_id=self.context.workflow_id,
            generation_run_id=self.context.generation_run_id,
            prompt_id=self.context.prompt_id,
            client_id=self.context.client_id,
            workflow_payload=self.context.workflow_payload,
            source=FinalImageSource(
                node_id=node_id,
                source_key=source.source_key,
                source_label=source.source_label,
                cube_alias=source.source_label,
            ),
            artifacts=artifacts,
            list_index=0,
            output_session_id=self.context.output_session_id,
            scene=self.context.scene,
        )
        if source.media_kind is OutputMediaKind.VIDEO:
            self.final_video_handler.handle(event)
        else:
            self.final_image_handler.handle(event)
        return True


def _parse_artifacts(
    media_kind: OutputMediaKind,
    output: object,
) -> tuple[ComfyImageArtifact, ...] | None:
    """Parse only the artifact envelope declared by the source owner."""

    if media_kind is OutputMediaKind.VIDEO:
        return parse_comfy_video_artifacts(output)
    return parse_comfy_image_artifacts(output)


def _optional_node_id(value: object) -> str | None:
    """Return a canonical string node ID from an executed event."""

    if isinstance(value, str | int):
        return str(value)
    return None


__all__ = ["StandardExecutedOutputContext", "StandardExecutedOutputHandler"]
