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

"""Verify Output preview registry projection into revision-scoped caches."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    OutputCanvasRevisionCache,
    PreviewSlotKey,
    ScenePreviewSlot,
    SourcePreviewSlotKey,
    output_revision_cache_binding,
)
from substitute.domain.workflow import (
    CanvasSessionRevision,
)


from tests.application.workflows.output_preview_lifecycle.support import (
    build_session,
)


def test_revision_cache_projects_registry_lanes_to_preview_maps() -> None:
    """Revision cache should expose registry-owned source and scene preview state."""

    source_preview_id = uuid4()
    scene_preview_id = uuid4()
    source_image = object()
    scene_image = object()
    registry = OutputPreviewRegistry()
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=OutputPreviewLaneKey.source(
                workflow_id="workflow",
                generation_run_id="generation-run",
                prompt_id="prompt",
                source_key="wf:text",
                scene_run_id="scene-run",
                scene_key="portrait",
            ),
            preview_id=source_preview_id,
            image=source_image,
            source_label="Text",
            client_id="client",
            session_revision=CanvasSessionRevision(1),
        )
    )
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=OutputPreviewLaneKey.scene(
                workflow_id="workflow",
                generation_run_id="generation-run",
                prompt_id="prompt",
                source_key="wf:upscale",
                scene_run_id="scene-run",
                scene_key="portrait",
            ),
            preview_id=scene_preview_id,
            image=scene_image,
            source_label="Upscale",
            client_id="client",
            session_revision=CanvasSessionRevision(1),
            scene_title="Portrait",
            scene_order=2,
            scene_count=3,
            accepted_for_overview=True,
        )
    )

    cache = OutputCanvasRevisionCache(
        registry=registry,
        active_preview_generation_run_id="generation-run",
        active_preview_scene_run_id="scene-run",
    )

    assert cache.preview_images_by_id == {
        source_preview_id: source_image,
        scene_preview_id: scene_image,
    }
    assert cache.preview_ids_by_source_key == {"wf:text": source_preview_id}
    assert cache.preview_ids_by_source_slot == {
        SourcePreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:text",
            set_index=1,
        ): source_preview_id
    }
    assert cache.preview_ids_by_scene_slot == {
        PreviewSlotKey(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:upscale",
            set_index=1,
        ): scene_preview_id
    }
    assert cache.scene_preview_slots_by_key == {
        "portrait": ScenePreviewSlot(
            scene_run_id="scene-run",
            generation_run_id="generation-run",
            scene_key="portrait",
            source_key="wf:upscale",
            set_index=1,
            preview_id=scene_preview_id,
            source_label="Upscale",
        )
    }
    assert cache.preview_scene_groups_by_key["portrait"].preview_image_id == (
        scene_preview_id
    )
    assert cache.preview_labels_by_source_key == {"wf:text": "Text"}
    assert cache.preview_images_by_source_key == {"wf:text": source_image}
    assert cache.completed_preview_slots == set()
    assert cache.active_preview_generation_run_id == "generation-run"
    assert cache.active_preview_scene_run_id == "scene-run"


def test_output_revision_cache_binding_ignores_current_session_revision() -> None:
    """Revision cache binding should be a no-op for the current session revision."""

    registry = OutputPreviewRegistry()
    session = build_session(
        OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        )
    )

    binding = output_revision_cache_binding(
        registry,
        session,
        current_cache_key=(session.workflow_id.value, session.revision.value),
    )

    assert binding is None


def test_output_revision_cache_binding_scopes_cache_to_new_session_revision() -> None:
    """Revision cache binding should reset cache reads to the new Output session."""

    preview_id = uuid4()
    preview = object()
    registry = OutputPreviewRegistry()
    registry.store_accepted_lane(
        OutputPreviewLane(
            key=OutputPreviewLaneKey.source(
                workflow_id="old-wf",
                generation_run_id="run-1",
                prompt_id="prompt-1",
                source_key="old-wf:node",
            ),
            preview_id=preview_id,
            image=preview,
            source_label="Old",
            client_id="client-1",
            session_revision=CanvasSessionRevision(1),
        )
    )
    session = build_session(
        OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        ),
        workflow_id="new-wf",
    )

    binding = output_revision_cache_binding(
        registry,
        session,
        current_cache_key=("old-wf", 1),
    )

    assert binding is not None
    assert binding.cache_key == (session.workflow_id.value, session.revision.value)
    assert binding.cache.session is session
    assert binding.cache.preview_images_by_id == {}
    assert registry.images_by_id() == {preview_id: preview}
