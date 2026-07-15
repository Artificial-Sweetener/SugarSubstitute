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

"""Compose Output preview lifecycle collaborators."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
    preview_slot_is_completed,
    scene_preview_id_for_source,
    scene_preview_matches_representative,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
    output_revision_cache,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
)
from substitute.presentation.canvas.output.output_preview_controller import (
    OutputPreviewController,
    OutputPreviewPanePresenter,
)
from substitute.presentation.ui_load_activity import (
    default_prompt_projection_ui_load_activity,
)

from .projection import _active_scene_key_for


def output_preview_controller_for(
    *,
    preview_registry: Callable[[], OutputPreviewRegistry],
    qpane_presenter: Callable[[], OutputPreviewPanePresenter],
    output_session: Callable[[], OutputCanvasSession | None],
    scene_count: Callable[[], int],
    set_scene_count: Callable[[int], None],
    active_scene_key: Callable[[], str | None],
    set_active_scene_key: Callable[[str | None], None],
    active_scene_overview: Callable[[], bool],
    set_active_scene_overview: Callable[[bool], None],
    set_current_output_image: Callable[[UUID], bool],
    activate_scene_overview: Callable[[], None],
    mark_output_activity: Callable[[], None],
    preview_slot_is_completed: Callable[[PreviewSlotKey], bool],
    scene_preview_id_for_source: Callable[..., UUID],
    scene_groups_by_key: Callable[[], dict[str, OutputCanvasSceneGroup]],
    scene_preview_matches_representative: Callable[..., bool],
    scene_preview_slots: Callable[[], dict[str, ScenePreviewSlot]],
    preview_image_cache: Callable[[], dict[UUID, object]],
    preview_scene_groups_by_key: Callable[[], dict[str, OutputCanvasSceneGroup]],
) -> OutputPreviewController:
    """Return the controller that applies Output preview mutations."""

    return OutputPreviewController(
        preview_registry=preview_registry,
        qpane_presenter=qpane_presenter,
        output_session=output_session,
        scene_count=scene_count,
        set_scene_count=set_scene_count,
        active_scene_key=active_scene_key,
        set_active_scene_key=set_active_scene_key,
        active_scene_overview=active_scene_overview,
        set_active_scene_overview=set_active_scene_overview,
        set_current_output_image=set_current_output_image,
        activate_scene_overview=activate_scene_overview,
        mark_output_activity=mark_output_activity,
        preview_slot_is_completed=preview_slot_is_completed,
        scene_preview_id_for_source=scene_preview_id_for_source,
        scene_groups_by_key=scene_groups_by_key,
        scene_preview_matches_representative=scene_preview_matches_representative,
        scene_preview_slots=scene_preview_slots,
        preview_image_cache=preview_image_cache,
        preview_scene_groups_by_key=preview_scene_groups_by_key,
    )


def output_preview_controller_for_host(
    host: object,
    *,
    asset_lookup: OutputCanvasAssetLookup,
    qpane_presenter: OutputPreviewPanePresenter,
    output_session: Callable[[], OutputCanvasSession | None],
    set_current_output_image: Callable[[UUID], bool],
    activate_scene_overview: Callable[[], None],
    mark_output_activity: Callable[[], None] | None = None,
) -> OutputPreviewController:
    """Return the preview controller wired to an Output canvas host."""

    activity_marker = mark_output_activity or (
        lambda: default_prompt_projection_ui_load_activity().mark_output_activity(
            reason="output_canvas_preview_set",
        )
    )
    return output_preview_controller_for(
        preview_registry=lambda: output_preview_registry(host),
        qpane_presenter=lambda: qpane_presenter,
        output_session=output_session,
        scene_count=lambda: int(getattr(host, "scene_count", 0)),
        set_scene_count=lambda scene_count: setattr(
            host,
            "scene_count",
            scene_count,
        ),
        active_scene_key=lambda: _active_scene_key_for(host),
        set_active_scene_key=lambda scene_key: setattr(
            host,
            "active_scene_key",
            scene_key,
        ),
        active_scene_overview=lambda: bool(
            getattr(host, "active_scene_overview", False)
        ),
        set_active_scene_overview=lambda active: setattr(
            host,
            "active_scene_overview",
            active,
        ),
        set_current_output_image=set_current_output_image,
        activate_scene_overview=activate_scene_overview,
        mark_output_activity=activity_marker,
        preview_slot_is_completed=lambda slot_key: preview_slot_is_completed(
            slot_key=slot_key,
            scene=output_scene_groups_by_key(output_route_state_snapshot(host)).get(
                slot_key.scene_key
            ),
            completed_preview_slots=output_revision_cache(host).completed_preview_slots,
        ),
        scene_preview_id_for_source=lambda **kwargs: scene_preview_id_for_source(
            output_revision_cache(host).preview_ids_by_scene_slot,
            **kwargs,
        ),
        scene_groups_by_key=lambda: output_scene_groups_by_key(
            output_route_state_snapshot(host)
        ),
        scene_preview_matches_representative=lambda *, scene_key, source_key: (
            scene_preview_matches_representative(
                scene=output_scene_groups_by_key(output_route_state_snapshot(host)).get(
                    scene_key
                ),
                current_slot=output_revision_cache(host).scene_preview_slots_by_key.get(
                    scene_key
                ),
                source_key=source_key,
            )
        ),
        scene_preview_slots=lambda: (
            output_revision_cache(host).scene_preview_slots_by_key
        ),
        preview_image_cache=asset_lookup.preview_images,
        preview_scene_groups_by_key=lambda: (
            output_revision_cache(host).preview_scene_groups_by_key
        ),
    )
