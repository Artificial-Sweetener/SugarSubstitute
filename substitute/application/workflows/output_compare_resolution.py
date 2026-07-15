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

"""Resolve output compare selections against output-canvas projections."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import OutputCompareSelection, OutputCompareState


def output_compare_candidates(
    projection: OutputCanvasProjection,
) -> tuple[OutputCompareSelection, ...]:
    """Return concrete output selections in stable navigation order."""

    candidates: list[OutputCompareSelection] = []
    if projection.scene_count > 1 and projection.scene_groups:
        for scene in projection.scene_groups:
            candidates.extend(
                _source_candidates(
                    scene.sources,
                    scene_key=scene.scene_key,
                )
            )
        return tuple(candidates)
    return tuple(_source_candidates(projection.sources, scene_key=None))


def resolve_output_compare_selection(
    projection: OutputCanvasProjection,
    selection: OutputCompareSelection,
) -> OutputCanvasImageItem | None:
    """Resolve one compare selection to an output image item."""

    sources = _sources_for_selection(projection, selection)
    source = _source_for_key(sources, selection.source_key)
    if source is None:
        return None
    return source.images_by_set.get(selection.set_index)


def output_compare_image_ids(
    projection: OutputCanvasProjection,
) -> tuple[UUID, ...]:
    """Return distinct resolvable compare image IDs in candidate order."""

    image_ids: list[UUID] = []
    for candidate in output_compare_candidates(projection):
        item = resolve_output_compare_selection(projection, candidate)
        if item is not None and item.image_id not in image_ids:
            image_ids.append(item.image_id)
    return tuple(image_ids)


def output_compare_available(projection: OutputCanvasProjection) -> bool:
    """Return whether the projection contains two distinct comparable images."""

    return len(output_compare_image_ids(projection)) >= 2


def default_output_compare_state(
    projection: OutputCanvasProjection,
) -> OutputCompareState:
    """Return enabled compare state using first and last valid outputs."""

    candidates = output_compare_candidates(projection)
    if not candidates or not output_compare_available(projection):
        return OutputCompareState()
    return OutputCompareState(
        enabled=True,
        base=candidates[0],
        comparison=candidates[-1],
    )


def default_output_compare_state_for_context(
    projection: OutputCanvasProjection,
    *,
    scene_key: str | None,
    set_index: int,
) -> OutputCompareState:
    """Return enabled compare state using first and last outputs in one context."""

    target_scene_key = scene_key if projection.scene_count > 1 else None
    scoped_candidates = [
        candidate
        for candidate in output_compare_candidates(projection)
        if candidate.scene_key == target_scene_key and candidate.set_index == set_index
    ]
    scoped_image_ids = {
        item.image_id
        for candidate in scoped_candidates
        for item in (resolve_output_compare_selection(projection, candidate),)
        if item is not None
    }
    if len(scoped_image_ids) < 2:
        return default_output_compare_state(projection)
    return OutputCompareState(
        enabled=True,
        base=scoped_candidates[0],
        comparison=scoped_candidates[-1],
    )


def reconcile_output_compare_state(
    projection: OutputCanvasProjection,
    state: OutputCompareState,
) -> OutputCompareState:
    """Return compare state with selections reconciled to current outputs."""

    if not state.enabled:
        return OutputCompareState(
            enabled=False,
            base=_reconcile_selection(projection, state.base),
            comparison=_reconcile_selection(projection, state.comparison),
            split_position=_clamp_split_position(state.split_position),
            orientation=_normalized_orientation(state.orientation),
        )
    candidates = output_compare_candidates(projection)
    if not candidates or not output_compare_available(projection):
        return OutputCompareState(
            enabled=False,
            base=_reconcile_selection(projection, state.base),
            comparison=_reconcile_selection(projection, state.comparison),
            split_position=_clamp_split_position(state.split_position),
            orientation=_normalized_orientation(state.orientation),
        )
    base = _reconcile_selection(projection, state.base) or candidates[0]
    comparison = _reconcile_selection(projection, state.comparison) or candidates[-1]
    return OutputCompareState(
        enabled=True,
        base=base,
        comparison=comparison,
        split_position=_clamp_split_position(state.split_position),
        orientation=_normalized_orientation(state.orientation),
    )


def _source_candidates(
    sources: tuple[OutputCanvasSourceGroup, ...],
    *,
    scene_key: str | None,
) -> list[OutputCompareSelection]:
    """Return compare selections for a group of output sources."""

    selections: list[OutputCompareSelection] = []
    set_indexes = sorted(
        {
            set_index
            for source in sources
            for set_index in source.images_by_set
            if set_index > 0
        }
    )
    for set_index in set_indexes:
        for source in sources:
            if set_index in source.images_by_set:
                selections.append(
                    OutputCompareSelection(
                        scene_key=scene_key,
                        set_index=set_index,
                        source_key=source.source_key,
                    )
                )
    return selections


def _reconcile_selection(
    projection: OutputCanvasProjection,
    selection: OutputCompareSelection | None,
) -> OutputCompareSelection | None:
    """Return a valid selection nearest to ``selection`` when possible."""

    candidates = output_compare_candidates(projection)
    if not candidates:
        return None
    if selection is None:
        return None
    if resolve_output_compare_selection(projection, selection) is not None:
        return selection
    same_scene = [
        candidate
        for candidate in candidates
        if candidate.scene_key == selection.scene_key
    ]
    scene_candidates = same_scene or list(candidates)
    same_source = [
        candidate
        for candidate in scene_candidates
        if candidate.source_key == selection.source_key
    ]
    source_candidates = same_source or scene_candidates
    return min(
        source_candidates,
        key=lambda candidate: (
            abs(candidate.set_index - selection.set_index),
            candidate.set_index,
            candidate.source_key,
            candidate.scene_key or "",
        ),
    )


def _sources_for_selection(
    projection: OutputCanvasProjection,
    selection: OutputCompareSelection,
) -> tuple[OutputCanvasSourceGroup, ...]:
    """Return projection sources scoped to a compare selection."""

    if projection.scene_count <= 1:
        return projection.sources
    for scene in projection.scene_groups:
        if scene.scene_key == selection.scene_key:
            return scene.sources
    return ()


def _source_for_key(
    sources: tuple[OutputCanvasSourceGroup, ...],
    source_key: str,
) -> OutputCanvasSourceGroup | None:
    """Return one source group by key."""

    for source in sources:
        if source.source_key == source_key:
            return source
    return None


def _clamp_split_position(position: float) -> float:
    """Return a bounded comparison split position."""

    try:
        value = float(position)
    except (TypeError, ValueError):
        return 0.5
    return min(1.0, max(0.0, value))


def _normalized_orientation(orientation: str) -> str:
    """Return a supported comparison orientation string."""

    return orientation if orientation in {"vertical", "horizontal"} else "vertical"


__all__ = [
    "default_output_compare_state",
    "default_output_compare_state_for_context",
    "output_compare_available",
    "output_compare_candidates",
    "output_compare_image_ids",
    "reconcile_output_compare_state",
    "resolve_output_compare_selection",
]
