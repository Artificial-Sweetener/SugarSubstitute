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

"""Build generic responsive Output grid scene requests for QPane."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias, cast
from uuid import UUID, uuid5

from PySide6.QtCore import QRectF, QSize
from qpane import (
    QPane,
    QPaneCatalogImageLayerRequest,
    QPaneSceneRequest,
)

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.presentation.canvas.shared.canvas_grid_layout import (
    grid_layout_for_dimensions,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasGridTileExtent,
    CanvasViewportExtent,
    ResponsiveCanvasGridPolicy,
    ResponsiveGridRequest,
)

GridContentScalar: TypeAlias = str | int | float | bool | None
GridContentKey: TypeAlias = tuple[GridContentScalar, ...]
_REQUEST_COMPOSITION_PLACEHOLDER = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True, slots=True)
class OutputGridTile:
    """Describe one ordered generic Output grid tile."""

    image_id: UUID
    image: object
    layer_namespace: UUID
    layer_identity_seed: str
    role: str
    metadata: dict[str, object]
    content_key: GridContentKey


@dataclass(frozen=True, slots=True)
class OutputGridContentSignature:
    """Identify route and ordered content independent of viewport topology."""

    route: CanvasRouteIdentity
    tile_keys: tuple[GridContentKey, ...]


@dataclass(frozen=True, slots=True)
class OutputGridLayoutSignature:
    """Identify content, reference extent, and selected topology."""

    content: OutputGridContentSignature
    reference_extent: CanvasGridTileExtent
    dimensions: tuple[int, int]


@dataclass(frozen=True, slots=True)
class OutputGridScenePlan:
    """Carry a guarded route, QPane request, and deduplication signature."""

    route: CanvasRouteIdentity
    request: QPaneSceneRequest
    layout_signature: OutputGridLayoutSignature


class OutputGridSceneBuilder:
    """Build responsive QPane requests from specialized ordered tiles."""

    def __init__(self, policy: ResponsiveCanvasGridPolicy | None = None) -> None:
        """Store the pure responsive topology policy."""

        self._policy = policy or ResponsiveCanvasGridPolicy()

    def build(
        self,
        *,
        route: CanvasRouteIdentity,
        title: str,
        tiles: tuple[OutputGridTile, ...],
        viewport_extent: CanvasViewportExtent,
        previous_dimensions: tuple[int, int] | None = None,
    ) -> OutputGridScenePlan | None:
        """Build a responsive scene plan when ordered tiles are measurable."""

        measured = tuple((tile, _image_extent(tile.image)) for tile in tiles)
        reference_extent = next(
            (extent for _tile, extent in measured if extent is not None), None
        )
        if reference_extent is None:
            return None
        decision = self._policy.choose(
            ResponsiveGridRequest(len(tiles), reference_extent, viewport_extent),
            previous_dimensions,
        )
        if decision is None:
            return None
        candidate = decision.candidate
        layout = grid_layout_for_dimensions(
            tile_count=len(tiles),
            tile_width=reference_extent.width,
            tile_height=reference_extent.height,
            gutter=candidate.gutter,
            columns=candidate.dimensions[0],
            rows=candidate.dimensions[1],
        )
        layers = tuple(
            self._layer_request(tile, extent, layout.placements[index])
            for index, (tile, extent) in enumerate(measured)
            if extent is not None
        )
        if len(layers) != len(tiles):
            return None
        content = OutputGridContentSignature(
            route=route,
            tile_keys=tuple(
                (*tile.content_key, extent.width, extent.height)
                for tile, extent in measured
                if extent is not None
            ),
        )
        signature = OutputGridLayoutSignature(
            content=content,
            reference_extent=reference_extent,
            dimensions=candidate.dimensions,
        )
        request = QPaneSceneRequest(
            composition_id=_REQUEST_COMPOSITION_PLACEHOLDER,
            title=title,
            bounds=layout.bounds,
            layers=layers,
        )
        return OutputGridScenePlan(route, request, signature)

    @staticmethod
    def _layer_request(
        tile: OutputGridTile,
        extent: CanvasGridTileExtent,
        cell: QRectF,
    ) -> QPaneCatalogImageLayerRequest:
        """Build one aspect-fitted QPane catalog layer request."""

        placement = QPane.fitSceneRect(
            QSize(round(extent.width), round(extent.height)), cell
        )
        return QPaneCatalogImageLayerRequest(
            layer_id=uuid5(tile.layer_namespace, tile.layer_identity_seed),
            image_id=tile.image_id,
            placement=placement,
            role=tile.role,
            metadata=MappingProxyType(dict(tile.metadata)),
        )


def _image_extent(image: object) -> CanvasGridTileExtent | None:
    """Return positive dimensions from a Qt-like image payload."""

    size_getter = getattr(image, "size", None)
    size = size_getter() if callable(size_getter) else image
    width = _positive_dimension(getattr(size, "width", None))
    height = _positive_dimension(getattr(size, "height", None))
    if width is None or height is None:
        return None
    return CanvasGridTileExtent(width, height)


def _positive_dimension(value: object) -> float | None:
    """Convert a callable or scalar dimension into a positive float."""

    raw = value() if callable(value) else value
    try:
        dimension = float(cast(float, raw))
    except (TypeError, ValueError):
        return None
    return dimension if dimension > 0.0 else None


__all__ = [
    "GridContentKey",
    "GridContentScalar",
    "OutputGridContentSignature",
    "OutputGridLayoutSignature",
    "OutputGridSceneBuilder",
    "OutputGridScenePlan",
    "OutputGridTile",
]
