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

"""Collect public QPane fingerprints for real-shell Output canvas scenarios."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast
from uuid import UUID

from PySide6.QtGui import QImage

from tests.support.real_output_canvas.models import CanvasFingerprint


def collect_canvas_fingerprint(shell: Any) -> CanvasFingerprint:
    """Capture workflow, preview, route, and public QPane scene diagnostics."""

    output_canvas = shell.output_canvas
    pane = output_canvas.pane
    session = getattr(output_canvas, "_output_session", None)
    current_image = getattr(pane, "currentImage", None)
    pending_counts = shell.generation_feedback_dispatcher._coalescer.pending_counts()
    scene_bounds, scene_layer_placements = _current_scene_geometry(pane)
    return CanvasFingerprint(
        active_workflow_id=shell.workflow_session_service.active_workflow_id,
        active_canvas_visible=shell.canvas_tabs.is_canvas_visible("Output"),
        output_session_workflow_id=getattr(
            getattr(session, "workflow_id", None), "value", None
        ),
        workflow_output_image_ids={
            workflow_id: tuple(workflow.output_image_uuids)
            for workflow_id, workflow in shell.workflow_session_service.workflows.items()
        },
        workflow_output_routes={
            workflow_id: (
                workflow.active_output_scene_key,
                workflow.active_output_scene_overview,
                workflow.active_output_source_key,
                workflow.active_output_set_index,
                workflow.active_output_uuid,
            )
            for workflow_id, workflow in shell.workflow_session_service.workflows.items()
        },
        workflow_output_focus_modes={
            workflow_id: workflow.output_focus_mode.value
            for workflow_id, workflow in shell.workflow_session_service.workflows.items()
        },
        active_source_tab_key=_active_source_tab_key(output_canvas.tabbar),
        navigation_container_hidden=output_canvas.tabbar_container.isHidden(),
        scene_selector_hidden=output_canvas.scene_selector_button.isHidden(),
        set_selector_hidden=output_canvas.set_selector_button.isHidden(),
        source_tabs_hidden=output_canvas.tabbar.isHidden(),
        source_selector_hidden=output_canvas.source_selector_button.isHidden(),
        preview_image_ids=tuple(shell.output_preview_registry.images_by_id()),
        preview_lane_keys=_preview_lane_keys(
            shell.output_preview_registry.lanes_for_session_like()
        ),
        pending_feedback_counts={
            "progress": pending_counts.progress_count,
            "model_load": pending_counts.model_load_count,
            "preview": pending_counts.preview_count,
            "output_image": pending_counts.output_image_count,
            "timing": pending_counts.timing_count,
            "failure": pending_counts.failure_count,
            "completed": pending_counts.completed_count,
        },
        pending_commit_count=_pending_commit_count(shell.output_image_pipeline),
        pending_projection_workflows=_pending_projection_workflows(
            shell.output_image_pipeline
        ),
        pane_image_ids=_pane_image_ids(pane),
        pane_current_image_id=_pane_current_image_id(pane),
        pane_current_composition_id=_pane_current_composition_id(pane),
        composition_image_ids=_composition_image_ids(pane),
        scene_bounds=scene_bounds,
        scene_layer_placements=scene_layer_placements,
        current_image_is_null=_image_is_null(current_image),
        current_image_rgb=_sample_rgb(current_image),
    )


def _active_source_tab_key(tabbar: object) -> str | None:
    """Return the concrete source tab selected by the rendered navigation bar."""

    current_route_key = getattr(tabbar, "currentRouteKey", None)
    if not callable(current_route_key):
        return None
    route_key = current_route_key()
    return route_key if isinstance(route_key, str) and route_key else None


def _pane_image_ids(pane: object) -> tuple[UUID, ...]:
    """Return image IDs currently known to QPane."""

    getter = getattr(pane, "imageIDs", None)
    if not callable(getter):
        return ()
    return tuple(image_id for image_id in getter() if isinstance(image_id, UUID))


def _pane_current_image_id(pane: object) -> UUID | None:
    """Return QPane's current image id."""

    getter = getattr(pane, "currentImageID", None)
    if not callable(getter):
        return None
    value = getter()
    return value if isinstance(value, UUID) else None


def _pane_current_composition_id(pane: object) -> UUID | None:
    """Return QPane's current composition id."""

    getter = getattr(pane, "currentCompositionID", None)
    if not callable(getter):
        return None
    value = getter()
    return value if isinstance(value, UUID) else None


def _composition_image_ids(pane: object) -> tuple[UUID, ...]:
    """Return image IDs in the active QPane composition."""

    snapshot_getter = getattr(pane, "getCompositionSnapshot", None)
    if not callable(snapshot_getter):
        return ()
    snapshot = snapshot_getter()
    composition_id = _pane_current_composition_id(pane)
    compositions = getattr(snapshot, "compositions", None)
    if composition_id is None or not isinstance(compositions, Mapping):
        return ()
    entry = compositions.get(composition_id)
    source_image_ids = getattr(entry, "source_image_ids", ())
    if not isinstance(source_image_ids, Iterable):
        return ()
    return tuple(
        image_id for image_id in source_image_ids if isinstance(image_id, UUID)
    )


def _current_scene_geometry(
    pane: object,
) -> tuple[
    tuple[float, float, float, float] | None,
    tuple[tuple[UUID, UUID, float, float, float, float], ...],
]:
    """Return active scene bounds and ordered public layer placements."""

    current_scene = getattr(pane, "currentScene", None)
    scene = current_scene() if callable(current_scene) else None
    if scene is None:
        return None, ()
    bounds = _rect_geometry(getattr(scene, "bounds", None))
    placements: list[tuple[UUID, UUID, float, float, float, float]] = []
    for layer in getattr(scene, "layers", ()):
        layer_id = getattr(layer, "layer_id", None)
        image_id = getattr(layer, "image_id", None)
        placement = _rect_geometry(getattr(layer, "placement", None))
        if (
            not isinstance(layer_id, UUID)
            or not isinstance(image_id, UUID)
            or placement is None
        ):
            continue
        placements.append((layer_id, image_id, *placement))
    return bounds, tuple(placements)


def _rect_geometry(rect: object) -> tuple[float, float, float, float] | None:
    """Normalize QRectF-like geometry into immutable scalar diagnostics."""

    if rect is None:
        return None
    accessors = tuple(
        getattr(rect, name, None) for name in ("x", "y", "width", "height")
    )
    if not all(callable(accessor) for accessor in accessors):
        return None
    return tuple(float(accessor()) for accessor in accessors)  # type: ignore[misc,return-value]


def _image_is_null(image: object) -> bool:
    """Return whether an image object is missing or null."""

    is_null = getattr(image, "isNull", None)
    return image is None or (callable(is_null) and bool(is_null()))


def _sample_rgb(image: object) -> tuple[int, int, int] | None:
    """Return the center-pixel color for a QImage-like object."""

    if not isinstance(image, QImage) or image.isNull():
        return None
    color = image.pixelColor(image.width() // 2, image.height() // 2)
    red, green, blue, _alpha = cast(tuple[int, int, int, int], color.getRgb())
    return red, green, blue


def _preview_lane_keys(lanes: Iterable[object]) -> tuple[str, ...]:
    """Return stable diagnostic labels for transient preview lanes."""

    labels: list[str] = []
    for lane in lanes:
        key = getattr(lane, "key", None)
        workflow_id = getattr(key, "workflow_id", "")
        source_key = getattr(key, "source_key", "")
        scene_key = getattr(key, "scene_key", "")
        placement = getattr(getattr(key, "placement", None), "value", "")
        labels.append(f"{workflow_id}:{source_key}:{scene_key}:{placement}")
    return tuple(labels)


def _pending_commit_count(output_image_pipeline: object) -> int:
    """Return pending prepared output commits, if the real queue is present."""

    commit_queue = getattr(output_image_pipeline, "_commit_queue", None)
    pending_count = getattr(commit_queue, "pending_count", None)
    if not callable(pending_count):
        return 0
    return int(pending_count())


def _pending_projection_workflows(output_image_pipeline: object) -> tuple[str, ...]:
    """Return workflow IDs with pending generated or deferred projections."""

    scheduler = getattr(output_image_pipeline, "_projection_scheduler", None)
    generated = getattr(scheduler, "_pending_generated", {})
    deferred = getattr(scheduler, "_pending_deferred", {})
    workflow_ids: set[str] = set()
    if isinstance(generated, Mapping):
        workflow_ids.update(str(workflow_id) for workflow_id in generated)
    if isinstance(deferred, Mapping):
        workflow_ids.update(str(workflow_id) for workflow_id in deferred)
    return tuple(sorted(workflow_ids))


__all__: list[str] = []
