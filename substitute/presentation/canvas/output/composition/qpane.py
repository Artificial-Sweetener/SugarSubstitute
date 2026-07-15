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

"""Compose Output QPane and guarded route collaborators."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.application.workflows.canvas_pane_catalog_port import (
    CanvasPaneCatalogPort,
)
from substitute.presentation.canvas.output.output_canvas_route_presenter import (
    OutputCanvasRoutePresenter,
    OutputRouteImageCatalog,
    OutputRouteImageRegistrar,
)
from substitute.presentation.canvas.qpane.canvas_pane_catalog import CanvasPaneCatalog
from substitute.presentation.canvas.qpane.canvas_route_projector import (
    OutputRouteProjector,
)
from substitute.presentation.canvas.qpane.output_pane_adapter import (
    OutputQPaneRouteAdapter,
)
from substitute.presentation.canvas.qpane.output_qpane_presenter import (
    OutputCanvasQPanePresenter,
)


def output_qpane_catalog(pane: object) -> CanvasPaneCatalog:
    """Return the catalog adapter for an Output QPane host."""

    return CanvasPaneCatalog(pane)


def output_qpane_presenter(
    catalog: CanvasPaneCatalogPort,
) -> OutputCanvasQPanePresenter:
    """Return the presenter that applies output image catalog mutations."""

    return OutputCanvasQPanePresenter(catalog=catalog)


def output_route_projector_for(
    pane: object,
    *,
    session_boundary: CanvasRouteSessionBoundaryPort,
) -> OutputRouteProjector:
    """Return the guarded route projector for an Output QPane host."""

    return OutputRouteProjector(
        OutputQPaneRouteAdapter(pane),
        session_boundary=session_boundary,
    )


def output_route_presenter(
    *,
    catalog: Callable[[], OutputRouteImageCatalog],
    image_registrar: Callable[[], OutputRouteImageRegistrar],
    layer_payload: Callable[[object], object | None],
    layer_path: Callable[[object], Path | None],
) -> OutputCanvasRoutePresenter:
    """Return the presenter that prepares Output route requests."""

    return OutputCanvasRoutePresenter(
        catalog=catalog,
        image_registrar=image_registrar,
        layer_payload=layer_payload,
        layer_path=layer_path,
    )
