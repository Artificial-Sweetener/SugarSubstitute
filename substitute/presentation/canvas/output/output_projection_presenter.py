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

"""Select the document presentation for one Output canvas projection."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.output_automatic_frontier_projection import (
    automatic_frontier_image_ids,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    output_route_identity_for_projection,
)
from substitute.application.workflows.output_compare_resolution import (
    resolve_output_compare_selection,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.domain.workflow import OutputFocusMode
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_document_navigation import (
    OutputDocumentNavigation,
)
from substitute.presentation.canvas.output.output_document_route_projector import (
    OutputDocumentRouteProjector,
)
from substitute.presentation.canvas.output.output_preview_navigation_presenter import (
    OutputPreviewNavigationPresenter,
    scene_overview_image_ids,
)


class OutputProjectionPresenter:
    """Own precedence among comparison, grid, preview, and detail presentations."""

    def __init__(
        self,
        *,
        document: OutputCanvasDocument,
        document_navigation: OutputDocumentNavigation,
        preview_navigation: OutputPreviewNavigationPresenter,
        route_projector: OutputDocumentRouteProjector,
    ) -> None:
        """Bind the document collaborators used by presentation selection."""

        self._document = document
        self._document_navigation = document_navigation
        self._preview_navigation = preview_navigation
        self._route_projector = route_projector

    def present(
        self,
        projection: OutputCanvasProjection,
        *,
        compare_state: OutputCompareState,
        active_scene_overview: bool,
        active_source_key: str | None,
        active_set_index: int,
    ) -> None:
        """Choose exactly one document presentation for the current projection."""

        if compare_state.enabled and compare_state.base and compare_state.comparison:
            base = resolve_output_compare_selection(projection, compare_state.base)
            comparison = resolve_output_compare_selection(
                projection,
                compare_state.comparison,
            )
            if base is not None and comparison is not None:
                if self._document.present_comparison(
                    base.image_id,
                    comparison.image_id,
                    split_position=compare_state.split_position,
                    orientation=compare_state.orientation,
                ):
                    return
        if active_scene_overview:
            self._document.present_grid(
                scene_overview_image_ids(
                    projection,
                    preview_scenes=self._document_navigation.scene_groups(),
                )
            )
            return
        sources = tuple(self._document_navigation.visible_sources().values())
        if active_set_index == 0:
            source = next(
                (
                    source
                    for source in sources
                    if source.source_key == active_source_key
                ),
                None,
            )
            if source is not None:
                image_ids = (
                    automatic_frontier_image_ids(
                        sources,
                        source_key=source.source_key,
                    )
                    if projection.focus_mode is OutputFocusMode.AUTOMATIC
                    else _source_image_ids(source)
                )
                self._document.present_grid(image_ids)
                return
        if self._preview_navigation.present_active_item(projection):
            return
        if projection.active_uuid is not None:
            self._route_projector.apply_final_image_route(
                output_route_identity_for_projection(projection),
                projection.active_uuid,
            )
            return
        self._document.clear_presentation()


def _source_image_ids(source: OutputCanvasSourceGroup) -> tuple[UUID, ...]:
    """Return ordered image identities for one source-grid presentation."""

    return tuple(item.image_id for _index, item in sorted(source.images_by_set.items()))


__all__ = ["OutputProjectionPresenter"]
