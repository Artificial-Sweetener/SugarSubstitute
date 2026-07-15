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

"""Apply output-canvas catalog mutations through the QPane catalog adapter."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.canvas_pane_catalog_port import (
    CanvasPaneCatalogPort,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.qpane.output_qpane_presenter")


class OutputCanvasQPanePresenter:
    """Isolate output-canvas catalog mutations from product route state."""

    def __init__(
        self,
        *,
        catalog: CanvasPaneCatalogPort,
    ) -> None:
        """Store the required catalog adapter."""

        self._catalog = catalog

    def register_image(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Insert or replace one image through the shared catalog adapter."""

        self._catalog.ensure_image_cached(image_id, image, path)

    def remove_image(self, image_id: UUID) -> None:
        """Remove one unreferenced preview image through the catalog adapter."""

        try:
            self._catalog.remove_unreferenced_image(image_id)
        except RuntimeError:
            log_warning(
                _LOGGER,
                "Output image removal skipped because QPane rejected the image",
                image_id=image_id,
            )


__all__ = ["OutputCanvasQPanePresenter"]
