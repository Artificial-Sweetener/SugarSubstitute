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

"""Present Output compare state through authorized route-projector commands."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_resolution import (
    default_output_compare_state,
    default_output_compare_state_for_context,
    reconcile_output_compare_state,
    resolve_output_compare_selection,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)


@dataclass(frozen=True, slots=True)
class OutputComparePresentation:
    """Report the reconciled compare state and whether rendering was applied."""

    state: OutputCompareState
    applied: bool
    state_changed: bool = False


class OutputComparePresenter:
    """Apply Output compare rendering without owning workflow compare state."""

    def __init__(self, route_projector: OutputRouteProjectorPort) -> None:
        """Store the authorized Output route projector used for compare display."""

        self._route_projector = route_projector

    def state_for_enabled(
        self,
        projection: OutputCanvasProjection,
        *,
        current_selection: OutputCompareSelection | None,
    ) -> OutputCompareState:
        """Return the default enabled compare state for current projection context."""

        if current_selection is None:
            return default_output_compare_state(projection)
        return default_output_compare_state_for_context(
            projection,
            scene_key=current_selection.scene_key,
            set_index=current_selection.set_index,
        )

    def state_for_disabled(self, state: OutputCompareState) -> OutputCompareState:
        """Return disabled compare state while preserving chooser memory."""

        return OutputCompareState(
            enabled=False,
            base=state.base,
            comparison=state.comparison,
            split_position=state.split_position,
            orientation=state.orientation,
        )

    def present(
        self,
        *,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
        route_blocked: bool = False,
    ) -> OutputComparePresentation:
        """Reconcile and apply compare rendering for one Output projection."""

        reconciled = reconcile_output_compare_state(projection, state)
        if (
            route_blocked
            or not reconciled.enabled
            or reconciled.base is None
            or reconciled.comparison is None
        ):
            cleared = self._route_projector.clear_compare(
                route=_clear_compare_route(projection)
            )
            return OutputComparePresentation(
                state=reconciled,
                applied=cleared,
                state_changed=reconciled != state,
            )

        base_item = resolve_output_compare_selection(projection, reconciled.base)
        comparison_item = resolve_output_compare_selection(
            projection,
            reconciled.comparison,
        )
        if base_item is None or comparison_item is None:
            cleared = self._route_projector.clear_compare(
                route=_clear_compare_route(projection)
            )
            return OutputComparePresentation(
                state=reconciled,
                applied=cleared,
                state_changed=reconciled != state,
            )

        route = CanvasRouteIdentity(
            route_kind="output_image",
            route_key=(
                f"image:{base_item.image_id};"
                f"scene:{reconciled.base.scene_key or ''};"
                f"source:{reconciled.base.source_key};"
                f"set:{reconciled.base.set_index}"
            ),
            primary_image_id=base_item.image_id,
        )
        applied = self._route_projector.apply_compare(
            route=route,
            base_image_id=base_item.image_id,
            comparison_image_id=comparison_item.image_id,
            split_position=reconciled.split_position,
            orientation=reconciled.orientation,
        )
        if not applied:
            self._route_projector.clear_compare(route=_clear_compare_route(projection))
        return OutputComparePresentation(
            state=reconciled,
            applied=applied,
            state_changed=reconciled != state,
        )

    def state_from_qpane_change(
        self,
        state: OutputCompareState,
        qpane_state: object,
    ) -> OutputCompareState:
        """Return compare state updated from a QPane divider-change payload."""

        if not state.enabled:
            return state
        raw_orientation = getattr(qpane_state, "orientation", state.orientation)
        orientation = str(getattr(raw_orientation, "value", raw_orientation))
        return OutputCompareState(
            enabled=True,
            base=state.base,
            comparison=state.comparison,
            split_position=float(
                getattr(qpane_state, "split_position", state.split_position)
            ),
            orientation=(
                orientation if orientation in {"vertical", "horizontal"} else "vertical"
            ),
        )


def _clear_compare_route(projection: OutputCanvasProjection) -> CanvasRouteIdentity:
    """Return an authorized route suitable for clearing compare rendering."""

    if projection.active_scene_overview:
        return CanvasRouteIdentity(
            route_kind="scene_overview",
            route_key=f"scene:{projection.active_scene_key or ''}",
        )
    if projection.active_set_index == 0 and projection.active_source_key is not None:
        return CanvasRouteIdentity(
            route_kind="source_grid",
            route_key=(
                f"scene:{projection.active_scene_key or ''};"
                f"source:{projection.active_source_key};set:0"
            ),
        )
    return CanvasRouteIdentity.empty()


__all__ = [
    "OutputComparePresentation",
    "OutputComparePresenter",
]
