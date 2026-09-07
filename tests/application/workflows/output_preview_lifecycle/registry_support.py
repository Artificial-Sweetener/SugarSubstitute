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

"""Build focused Output preview registry contract values."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from substitute.application.ports import PreviewImageUpdate
from substitute.application.workflows import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSession,
    OutputCanvasSourceGroup,
    OutputPreviewCloseIdentity,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_visual_events import LivePreviewEvent
from substitute.domain.workflow import CanvasSessionBoundary


def build_registry_session(
    *,
    source_keys: tuple[str, ...],
    scene_keys: tuple[str, ...] = (),
    boundary: CanvasSessionBoundary | None = None,
) -> OutputCanvasSession:
    """Build an Output canvas session with the requested authority."""

    projection = OutputCanvasProjection(
        sources=tuple(
            OutputCanvasSourceGroup(
                source_key=source_key,
                label=source_key,
                images_by_set={},
            )
            for source_key in source_keys
        ),
        active_source_key=source_keys[0] if source_keys else None,
        active_set_index=0 if source_keys else 1,
        active_uuid=None,
        set_count=0,
        scene_groups=tuple(
            OutputCanvasSceneGroup(
                scene_run_id="scene-run",
                scene_key=scene_key,
                title=scene_key,
                order=0,
                sources=(),
            )
            for scene_key in scene_keys
        ),
        active_scene_key=scene_keys[0] if scene_keys else None,
        active_scene_overview=False,
        scene_count=len(scene_keys),
    )
    return bind_output_canvas_session(
        boundary or CanvasSessionBoundary(),
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={},
    )


def build_preview_event(
    *,
    workflow_id: str = "wf",
    source_key: str,
    source_label: str | None = None,
    generation_run_id: str = "run",
    prompt_id: str = "prompt",
    client_id: str = "client",
    output_session_id: str = "",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
) -> LivePreviewEvent:
    """Build a strict preview event for registry tests."""

    event = LivePreviewEvent.from_update(
        PreviewImageUpdate(
            workflow_id=workflow_id,
            image=object(),
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
            output_session_id=output_session_id or None,
            node_id="preview-node",
            source_key=source_key,
            source_label=source_label or source_key,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
        )
    )
    assert event is not None
    return event


def build_close_identity(
    *,
    source_key: str,
    image_id: UUID,
    source_label: str | None = None,
    batch_index: int | None = 0,
) -> OutputPreviewCloseIdentity:
    """Build final-output preview close identity for registry tests."""

    return OutputPreviewCloseIdentity(
        workflow_id="wf",
        image_id=image_id,
        source_key=source_key,
        source_label=source_label or source_key,
        generation_run_id="run",
        prompt_id="prompt",
        client_id="client",
        node_id="save",
        list_index=0,
        batch_index=batch_index,
        scene_run_id=None,
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )


def uuid_sequence() -> Callable[[], UUID]:
    """Return a UUID factory that starts at one and increments."""

    next_value = 0

    def factory() -> UUID:
        """Return the next deterministic UUID."""

        nonlocal next_value
        next_value += 1
        return UUID(int=next_value)

    return factory
