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

"""Prepare Output canvas route requests before QPane route application."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.output.output_canvas_route_presenter")


class OutputRouteImageCatalog(Protocol):
    """Report whether a QPane catalog already contains an image payload."""

    def contains(self, image_id: UUID) -> bool:
        """Return whether ``image_id`` is already present in the QPane catalog."""


class OutputRouteImageRegistrar(Protocol):
    """Register one image payload with the output QPane catalog."""

    def register_image(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Register one image payload and optional source path."""


@dataclass(frozen=True, slots=True)
class OutputCanvasRoutePresenter:
    """Prepare composed Output route requests for safe QPane application."""

    catalog: Callable[[], OutputRouteImageCatalog]
    image_registrar: Callable[[], OutputRouteImageRegistrar]
    layer_payload: Callable[[object], object | None]
    layer_path: Callable[[object], Path | None]

    def ensure_scene_request_images_cached(self, request: object) -> bool:
        """Ensure the QPane catalog contains every image required by ``request``."""

        layers = getattr(request, "layers", ())
        if not isinstance(layers, Iterable):
            return False

        catalog = self.catalog()
        registrar = self.image_registrar()
        for layer in layers:
            image_id = getattr(layer, "image_id", None)
            if not isinstance(image_id, UUID):
                continue
            if catalog.contains(image_id):
                continue

            image = self.layer_payload(layer)
            if image is None:
                metadata = _layer_metadata(layer)
                log_warning(
                    _LOGGER,
                    "Skipped Output scene composition with uncached image",
                    image_id=image_id,
                    role=getattr(layer, "role", ""),
                    grid_kind=metadata.get("grid_kind"),
                    scene_key=metadata.get("scene_key"),
                    source_key=metadata.get("source_key"),
                    set_index=metadata.get("set_index"),
                )
                return False

            registrar.register_image(image_id, image, self.layer_path(layer))
        return True


def _layer_metadata(layer: object) -> Mapping[str, object]:
    """Return route-layer metadata when the layer exposes a mapping."""

    metadata = getattr(layer, "metadata", {})
    return metadata if isinstance(metadata, Mapping) else {}


__all__ = [
    "OutputCanvasRoutePresenter",
    "OutputRouteImageCatalog",
    "OutputRouteImageRegistrar",
]
