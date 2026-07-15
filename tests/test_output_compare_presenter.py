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

"""Contract tests for Output compare presentation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresenter,
)


class _RouteProjector:
    """Record compare route commands issued by the presenter."""

    def __init__(self) -> None:
        """Initialize recorded route calls."""

        self.compare_calls: list[
            tuple[CanvasRouteIdentity, UUID, UUID, float, str]
        ] = []
        self.clear_calls: list[CanvasRouteIdentity] = []

    def apply_compare(
        self,
        *,
        route: CanvasRouteIdentity,
        base_image_id: UUID,
        comparison_image_id: UUID,
        split_position: float,
        orientation: str,
    ) -> bool:
        """Record an authorized compare route application."""

        self.compare_calls.append(
            (
                route,
                base_image_id,
                comparison_image_id,
                split_position,
                orientation,
            )
        )
        return True

    def clear_compare(self, *, route: CanvasRouteIdentity) -> bool:
        """Record a compare clear route application."""

        self.clear_calls.append(route)
        return True


def test_compare_presenter_applies_compare_through_route_projector() -> None:
    """Enabled compare state should activate only via the route projector."""

    base_id = uuid4()
    comparison_id = uuid4()
    projection = _projection(base_id, comparison_id)
    projector = _RouteProjector()
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
        split_position=0.25,
        orientation="horizontal",
    )

    presentation = OutputComparePresenter(
        cast(OutputRouteProjectorPort, projector)
    ).present(
        projection=projection,
        state=state,
    )

    assert presentation.applied is True
    assert presentation.state == state
    assert projector.clear_calls == []
    route, applied_base, applied_comparison, split, orientation = (
        projector.compare_calls[0]
    )
    assert route.route_kind == "output_image"
    assert route.primary_image_id == base_id
    assert applied_base == base_id
    assert applied_comparison == comparison_id
    assert split == 0.25
    assert orientation == "horizontal"


def test_compare_presenter_clears_compare_when_route_is_blocked() -> None:
    """Grid and scene-overview routes should clear compare rendering."""

    base_id = uuid4()
    comparison_id = uuid4()
    projection = _projection(
        base_id,
        comparison_id,
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
    )
    projector = _RouteProjector()
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )

    presentation = OutputComparePresenter(
        cast(OutputRouteProjectorPort, projector)
    ).present(
        projection=projection,
        state=state,
        route_blocked=True,
    )

    assert presentation.applied is True
    assert projector.compare_calls == []
    assert projector.clear_calls[0].route_kind == "source_grid"


def test_compare_presenter_enabled_state_uses_current_batch_first_and_last() -> None:
    """Enabled compare defaults should keep the current batch comparison source."""

    projection = _batch_projection()

    state = OutputComparePresenter(
        cast(OutputRouteProjectorPort, _RouteProjector())
    ).state_for_enabled(
        projection,
        current_selection=OutputCompareSelection(None, 2, "source-c"),
    )

    assert state.enabled is True
    assert state.base == OutputCompareSelection(None, 2, "source-a")
    assert state.comparison == OutputCompareSelection(None, 2, "source-c")


def test_compare_presenter_normalizes_qpane_change_state() -> None:
    """QPane divider changes should update only transient compare display settings."""

    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )

    changed = OutputComparePresenter(
        cast(OutputRouteProjectorPort, _RouteProjector())
    ).state_from_qpane_change(
        state,
        SimpleNamespace(split_position=0.8, orientation="diagonal"),
    )

    assert changed.split_position == 0.8
    assert changed.orientation == "vertical"
    assert changed.base == state.base
    assert changed.comparison == state.comparison


def _projection(
    base_id: UUID,
    comparison_id: UUID,
    *,
    active_source_key: str = "source-a",
    active_set_index: int = 1,
    active_uuid: UUID | None = None,
) -> OutputCanvasProjection:
    """Return a two-source projection for compare presenter tests."""

    selected_id = active_uuid if active_uuid is not None else base_id
    return OutputCanvasProjection(
        sources=(
            _source("source-a", base_id),
            _source("source-b", comparison_id),
        ),
        active_source_key=active_source_key,
        active_set_index=active_set_index,
        active_uuid=selected_id,
        set_count=1,
    )


def _source(source_key: str, image_id: UUID) -> OutputCanvasSourceGroup:
    """Return one compare-capable source group."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={
            1: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=ImageMeta("wf", source_key, 1, "", f"E:/{source_key}.png"),
                set_index=1,
            )
        },
    )


def _batch_projection() -> OutputCanvasProjection:
    """Return a three-source, two-batch projection for compare defaults."""

    sources = (
        _batch_source("source-a"),
        _batch_source("source-b"),
        _batch_source("source-c"),
    )
    return OutputCanvasProjection(
        sources=sources,
        active_source_key="source-c",
        active_set_index=2,
        active_uuid=sources[-1].images_by_set[2].image_id,
        set_count=2,
    )


def _batch_source(source_key: str) -> OutputCanvasSourceGroup:
    """Return one compare-capable source with two batch images."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={
            set_index: OutputCanvasImageItem(
                image_id=uuid4(),
                image_meta=ImageMeta(
                    "wf",
                    source_key,
                    set_index,
                    "",
                    f"E:/{source_key}_{set_index}.png",
                ),
                set_index=set_index,
            )
            for set_index in (1, 2)
        },
    )
