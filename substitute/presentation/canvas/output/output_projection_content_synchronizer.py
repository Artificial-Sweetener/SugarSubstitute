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

"""Synchronize application Output payload records with the CuteCanvas document."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.presentation.canvas.output.output_document import (
    OutputCanvasDocument,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.output.output_projection_content")


class OutputProjectionContentSynchronizer:
    """Admit and retire projection content through the Output document registry."""

    def __init__(
        self,
        *,
        image_registry: CanvasImageRegistry,
        output_document: OutputCanvasDocument,
    ) -> None:
        """Store authoritative application payload and document boundaries."""

        self._image_registry = image_registry
        self._output_document = output_document

    def synchronize_projection(self, projection: OutputCanvasProjection) -> None:
        """Admit every available final output payload used by projection routes."""

        for image_id in _projected_image_ids(projection):
            image = self._image_registry.payload_for(image_id)
            metadata = self._image_registry.metadata_for(image_id)
            if image is None or metadata is None:
                log_warning(
                    _LOGGER,
                    "Skipped Output document admission for incomplete image record",
                    image_id=str(image_id),
                    payload_available=image is not None,
                    metadata_available=metadata is not None,
                )
                continue
            self._output_document.admit_image(
                image_id,
                image,
                path=Path(metadata.path) if metadata.path else None,
            )

    def retire_unreferenced(self, image_ids: tuple[UUID, ...]) -> None:
        """Retire document content after application workflow ownership releases it."""

        for image_id in image_ids:
            self._output_document.retire_image(image_id)


def _projected_image_ids(projection: OutputCanvasProjection) -> tuple[UUID, ...]:
    """Return unique final image identities referenced by one projection."""

    image_ids: list[UUID] = []
    for source in projection.sources:
        image_ids.extend(item.image_id for item in source.images_by_set.values())
    for scene in projection.scene_groups:
        if scene.primary_image_id is not None:
            image_ids.append(scene.primary_image_id)
        for source in scene.sources:
            image_ids.extend(item.image_id for item in source.images_by_set.values())
    return tuple(dict.fromkeys(image_ids))


__all__ = ["OutputProjectionContentSynchronizer"]
