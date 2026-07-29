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

"""Collect public CuteCanvas fingerprints for real-shell Output scenarios."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast
from uuid import UUID

from PySide6.QtGui import QImage
from cutecanvas import CanvasPresentationKind

from tests.support.real_output_canvas.models import CanvasFingerprint


def collect_canvas_fingerprint(shell: Any) -> CanvasFingerprint:
    """Capture workflow, preview, route, and public document diagnostics."""

    output_canvas = shell.output_canvas
    document = output_canvas.document
    document_session = document.session
    presentation = document_session.presentation
    output_session = getattr(output_canvas, "_output_session", None)
    active_composition_id = document.session.active_composition_id
    active_image_id = (
        document.image_id_for_composition(active_composition_id)
        if active_composition_id is not None
        and presentation.kind is CanvasPresentationKind.SINGLE
        else None
    )
    active_image = (
        None if active_image_id is None else document.image_payload(active_image_id)
    )
    pending_counts = shell.generation_feedback_dispatcher._coalescer.pending_counts()
    grid_viewport, grid_target_frames = _current_grid_geometry(
        document=document,
        workspace=output_canvas.workspace,
    )
    return CanvasFingerprint(
        active_workflow_id=shell.workflow_session_service.active_workflow_id,
        active_canvas_visible=shell.canvas_tabs.is_canvas_visible("Output"),
        output_session_workflow_id=getattr(
            getattr(output_session, "workflow_id", None), "value", None
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
        document_image_ids=document.image_ids(),
        active_image_id=active_image_id,
        active_composition_id=active_composition_id,
        presented_image_ids=document.image_ids_for_compositions(
            presentation.target_ids
        ),
        grid_viewport=grid_viewport,
        grid_target_frames=grid_target_frames,
        active_image_is_null=_image_is_null(active_image),
        active_image_rgb=_sample_rgb(active_image),
    )


def _active_source_tab_key(tabbar: object) -> str | None:
    """Return the concrete source tab selected by the rendered navigation bar."""

    current_route_key = getattr(tabbar, "currentRouteKey", None)
    if not callable(current_route_key):
        return None
    route_key = current_route_key()
    return route_key if isinstance(route_key, str) and route_key else None


def _current_grid_geometry(
    *,
    document: object,
    workspace: object,
) -> tuple[
    tuple[float, float, float, float] | None,
    tuple[tuple[UUID, UUID, float, float, float, float], ...],
]:
    """Return current responsive grid viewport and composition target frames."""

    snapshot_getter = getattr(workspace, "gridSnapshot", None)
    snapshot = snapshot_getter() if callable(snapshot_getter) else None
    if snapshot is None:
        return None, ()
    viewport = _rect_geometry(getattr(snapshot, "viewport", None))
    frames: list[tuple[UUID, UUID, float, float, float, float]] = []
    for frame in getattr(snapshot, "frames", ()):
        composition_id = getattr(frame, "target_id", None)
        image_id_for_composition = getattr(document, "image_id_for_composition", None)
        image_id = (
            image_id_for_composition(composition_id)
            if callable(image_id_for_composition) and isinstance(composition_id, UUID)
            else None
        )
        content = _rect_geometry(getattr(frame, "content", None))
        if (
            not isinstance(composition_id, UUID)
            or not isinstance(image_id, UUID)
            or content is None
        ):
            continue
        frames.append((composition_id, image_id, *content))
    return viewport, tuple(frames)


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
