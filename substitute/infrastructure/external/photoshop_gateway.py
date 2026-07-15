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

"""Provide external-editor adapter that opens canvas outputs in Photoshop."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence, cast

from substitute.domain.workflow import ImageMeta
from substitute.shared.logging.logger import get_logger, log_exception, log_warning

_LOGGER = get_logger("infrastructure.external.photoshop_gateway")


class PhotoshopGateway:
    """Open one or many generated images as Photoshop documents/layers."""

    def open_image(self, *, image: object, image_meta: ImageMeta) -> bool:
        """Open one image in Photoshop and paste it into a named document."""

        session_type = self._import_session()
        if session_type is None:
            return False

        image_path = self._resolve_image_path(image=image, image_meta=image_meta)
        if image_path is None:
            return False

        width, height = self._image_size(image)
        resolution = self._image_resolution(image)
        if width <= 0 or height <= 0:
            log_warning(
                _LOGGER,
                "Rejected Photoshop open request due to invalid image dimensions",
                width=width,
                height=height,
                workflow_name=image_meta.workflow_name,
                cube_name=image_meta.cube_name,
            )
            return False

        parts: list[str] = []
        if image_meta.image_number >= 0:
            parts.append(f"{image_meta.image_number:03d}")
        if image_meta.workflow_name:
            parts.append(image_meta.workflow_name)
        if image_meta.cube_name:
            parts.append(image_meta.cube_name)
        layer_name = " ".join(parts) if parts else "Layer"

        try:
            with session_type() as ps:
                document = ps.app.documents.add(
                    width=width,
                    height=height,
                    resolution=resolution,
                    name=layer_name,
                )
                temp_doc = ps.app.open(str(image_path))
                temp_doc.selection.selectAll()
                temp_doc.selection.copy()
                ps.app.activeDocument = document
                document.paste()
                pasted_layer = document.activeLayer
                pasted_layer.name = layer_name
                temp_doc.close(2)  # 2 = DoNotSaveChanges
            return True
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to open image in Photoshop",
                path=image_path,
                workflow_name=image_meta.workflow_name,
                cube_name=image_meta.cube_name,
                error=error,
            )
            return False

    def open_images(self, *, images: Sequence[tuple[object, ImageMeta]]) -> bool:
        """Open many images in Photoshop and paste each as a separate layer."""

        if not images:
            return False

        session_type = self._import_session()
        if session_type is None:
            return False

        prepared: list[tuple[Path, object, ImageMeta]] = []
        for image, image_meta in images:
            image_path = self._resolve_image_path(image=image, image_meta=image_meta)
            if image_path is None:
                return False
            prepared.append((image_path, image, image_meta))

        max_width = max(self._image_size(image)[0] for _path, image, _meta in prepared)
        max_height = max(self._image_size(image)[1] for _path, image, _meta in prepared)
        max_dpi = max(self._image_resolution(image) for _path, image, _meta in prepared)
        first_meta = prepared[0][2]
        if first_meta.image_number >= 0:
            document_name = f"{first_meta.image_number:03d} {first_meta.workflow_name}"
        else:
            document_name = first_meta.workflow_name or "Workflow"

        try:
            with session_type() as ps:
                document = ps.app.documents.add(
                    width=max_width,
                    height=max_height,
                    resolution=max_dpi,
                    name=document_name,
                )
                for image_path, _image, image_meta in prepared:
                    layer_name = image_meta.cube_name or "Layer"
                    temp_doc = ps.app.open(str(image_path))
                    temp_doc.selection.selectAll()
                    temp_doc.selection.copy()
                    ps.app.activeDocument = document
                    document.paste()
                    pasted_layer = document.activeLayer
                    pasted_layer.name = layer_name
                    temp_doc.close(2)  # 2 = DoNotSaveChanges

                document.activeLayer = document.artLayers[-1]
            return True
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to open image sequence in Photoshop",
                image_count=len(prepared),
                workflow_name=first_meta.workflow_name,
                error=error,
            )
            return False

    @staticmethod
    def _import_session() -> type | None:
        """Resolve Photoshop Session type lazily so app startup stays resilient."""

        try:
            from photoshop import Session  # type: ignore[import-untyped]
        except Exception as error:
            log_warning(
                _LOGGER,
                "Photoshop integration unavailable",
                error=error,
            )
            return None
        return cast(type, Session)

    def _resolve_image_path(
        self, *, image: object, image_meta: ImageMeta
    ) -> Path | None:
        """Return on-disk image path, creating a temporary PNG when necessary."""

        candidate = image_meta.path.strip()
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path

        save_method = getattr(image, "save", None)
        if not callable(save_method):
            log_warning(
                _LOGGER,
                "Cannot create temporary image file for Photoshop export",
                workflow_name=image_meta.workflow_name,
                cube_name=image_meta.cube_name,
            )
            return None

        try:
            temp_file = NamedTemporaryFile(suffix=".png", delete=False)
            temp_path = Path(temp_file.name)
            temp_file.close()
            if not bool(save_method(str(temp_path), "PNG")):
                return None
            return temp_path
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to persist temporary image for Photoshop export",
                workflow_name=image_meta.workflow_name,
                cube_name=image_meta.cube_name,
                error=error,
            )
            return None

    @staticmethod
    def _image_size(image: object) -> tuple[int, int]:
        """Extract width/height from image-like object."""

        width_getter = getattr(image, "width", None)
        height_getter = getattr(image, "height", None)
        width = int(width_getter()) if callable(width_getter) else 0
        height = int(height_getter()) if callable(height_getter) else 0
        return width, height

    @staticmethod
    def _image_resolution(image: object) -> float:
        """Extract DPI-like value from image-like object with sane fallback."""

        dots_getter = getattr(image, "dotsPerMeterX", None)
        dots_per_meter_x = int(dots_getter()) if callable(dots_getter) else 0
        if dots_per_meter_x <= 0:
            return 72.0
        return float(dots_per_meter_x) * 0.0254


__all__ = [
    "PhotoshopGateway",
]
