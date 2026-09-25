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

"""Persist final Comfy output images with Substitute metadata and naming."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin

from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.infrastructure.comfy.comfy_payload_fields import positive_int_or_zero
from substitute.infrastructure.comfy.output_destination_allocator import (
    OutputDestinationAllocator,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.infrastructure.comfy.jpeg_companion_encoder import (
    JpegCompanionEncoder,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("infrastructure.comfy.output_image_persistence")


@dataclass(frozen=True)
class PersistedOutputImage:
    """Describe materialized output facts and optional durable PNG path."""

    file_path: Path | None
    width: int
    height: int


class OutputImagePersistence:
    """Own output image file persistence, naming state, and PNG metadata."""

    def __init__(
        self,
        *,
        output_save_plan: OutputSavePlan,
        workflow_payload: Mapping[str, object],
        persistence_sugar_script: str | None,
        cube_numbers_by_alias: Mapping[str, int],
        destination_allocator: OutputDestinationAllocator | None = None,
        jpeg_encoder: JpegCompanionEncoder | None = None,
    ) -> None:
        """Initialize one listener-run persistence owner."""

        self._output_save_plan = output_save_plan
        self._workflow_payload = workflow_payload
        self._persistence_sugar_script = persistence_sugar_script
        self._destination_allocator = (
            destination_allocator
            or OutputDestinationAllocator(
                output_save_plan=output_save_plan,
                cube_numbers_by_alias=cube_numbers_by_alias,
            )
        )
        self._jpeg_encoder = jpeg_encoder or JpegCompanionEncoder()

    def persist_output_image(
        self,
        *,
        image_bytes: bytes,
        source_identity: OutputSourceIdentity,
    ) -> PersistedOutputImage:
        """Materialize optional durable files and always return decoded dimensions."""

        with Image.open(io.BytesIO(image_bytes)) as image:
            width = positive_int_or_zero(getattr(image, "width", 0))
            height = positive_int_or_zero(getattr(image, "height", 0))
            file_path = self._destination_allocator.allocate(
                source_identity=source_identity,
                width=width,
                height=height,
                suffix=".png",
                companion_suffixes=(".jpg",)
                if self._output_save_plan.jpeg.enabled
                else (),
            )
            if file_path is None:
                return PersistedOutputImage(
                    file_path=None,
                    width=width,
                    height=height,
                )
            png_metadata = PngImagePlugin.PngInfo()
            if self._persistence_sugar_script:
                headered_script = (
                    "# Project: "
                    f"{self._output_save_plan.workflow_name}\n\n"
                    f"{self._persistence_sugar_script}"
                )
                png_metadata.add_text("sugar_script", headered_script)
            workflow_metadata = workflow_metadata_json(self._workflow_payload)
            if workflow_metadata is not None:
                png_metadata.add_text("workflow", workflow_metadata)
            image.save(file_path, pnginfo=png_metadata)
            if self._output_save_plan.jpeg.enabled:
                try:
                    jpeg_bytes = self._jpeg_encoder.encode(
                        image, self._output_save_plan.jpeg
                    )
                    file_path.with_suffix(".jpg").write_bytes(jpeg_bytes)
                except Exception as error:
                    log_exception(
                        _LOGGER,
                        "Failed to write optional JPEG companion",
                        png_path=file_path,
                        error=error,
                    )
        return PersistedOutputImage(file_path=file_path, width=width, height=height)


def workflow_metadata_json(workflow_payload: Mapping[str, object]) -> str | None:
    """Return Comfy UI workflow metadata from wrapped or canonical graph payloads."""

    workflow = workflow_payload.get("workflow")
    if not isinstance(workflow, Mapping) and _is_canonical_workflow(workflow_payload):
        workflow = workflow_payload
    if not isinstance(workflow, Mapping):
        return None
    return json.dumps(workflow, separators=(",", ":"))


def _is_canonical_workflow(value: Mapping[str, object]) -> bool:
    """Recognize a serialized Comfy workflow without confusing execution prompts."""

    return isinstance(value.get("nodes"), list) and isinstance(
        value.get("definitions"), Mapping
    )


__all__ = [
    "OutputImagePersistence",
    "PersistedOutputImage",
    "workflow_metadata_json",
]
