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

"""Adapt standard Comfy executed-image payloads into final image events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.ports.comfy_gateway import ListenerOutputSource
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageScene,
    FinalImageSource,
)
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.standard_executed_image_handler")


@dataclass(frozen=True, slots=True)
class StandardExecutedImageContext:
    """Carry listener identity used to validate standard image events."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    workflow_payload: dict[str, object]
    scene: FinalImageScene


@dataclass(frozen=True, slots=True)
class StandardExecutedImageHandler:
    """Recognize recovery-node images and delegate final-image processing."""

    context: StandardExecutedImageContext
    sources_by_node: Mapping[str, ListenerOutputSource]
    final_image_handler: FinalImageEventHandler

    def handle(self, data: Mapping[str, object]) -> bool:
        """Handle a standard executed image event owned by a recovery source."""

        node_id = _optional_node_id(data.get("node"))
        if node_id is None or node_id not in self.sources_by_node:
            return False
        if data.get("prompt_id") != self.context.prompt_id:
            return False
        source = self.sources_by_node[node_id]
        artifacts = _parse_image_artifacts(data.get("output"))
        if artifacts is None:
            log_warning(
                _LOGGER,
                "Ignored malformed executed image output",
                workflow_id=self.context.workflow_id,
                generation_run_id=self.context.generation_run_id,
                prompt_id=self.context.prompt_id,
                node_id=node_id,
            )
            return True
        if not artifacts:
            return True
        self.final_image_handler.handle(
            FinalImageEvent(
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
                scene=self.context.scene,
            )
        )
        return True


def _parse_image_artifacts(output: object) -> tuple[ComfyImageArtifact, ...] | None:
    """Parse canonical ``executed.output.images`` artifact references."""

    if output is None:
        return ()
    if not isinstance(output, Mapping):
        return None
    raw_images = output.get("images")
    if raw_images is None:
        return ()
    if not isinstance(raw_images, list):
        return None
    artifacts: list[ComfyImageArtifact] = []
    for raw_image in raw_images:
        if not isinstance(raw_image, Mapping):
            return None
        filename = raw_image.get("filename")
        artifact_type = raw_image.get("type")
        subfolder = raw_image.get("subfolder", "")
        if (
            not isinstance(filename, str)
            or not filename
            or not isinstance(artifact_type, str)
            or not artifact_type
            or not isinstance(subfolder, str)
        ):
            return None
        artifacts.append(
            ComfyImageArtifact(
                filename=filename,
                subfolder=subfolder,
                type=artifact_type,
            )
        )
    return tuple(artifacts)


def _optional_node_id(value: object) -> str | None:
    """Return a canonical string node ID from an executed event."""

    if isinstance(value, str | int):
        return str(value)
    return None


__all__ = ["StandardExecutedImageContext", "StandardExecutedImageHandler"]
