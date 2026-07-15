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

"""Contract tests for Output scene-overview scene request composition."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    ScenePreviewSlot,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
    OutputSceneOverviewPreview,
    scene_overview_preview_for_scene,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)


class _Image:
    """Test image double exposing a Qt-like size."""

    def __init__(self, width: int, height: int) -> None:
        """Store image dimensions."""

        self._size = SimpleNamespace(width=lambda: width, height=lambda: height)

    def size(self) -> object:
        """Return a Qt-like size object."""

        return self._size


def test_scene_overview_composer_returns_scene_request_for_final_tiles() -> None:
    """Final scene groups should compose a route request with scene metadata."""

    first_id = uuid4()
    second_id = uuid4()
    payloads = {
        first_id: _Image(640, 480),
        second_id: _Image(640, 480),
    }
    scenes = (
        _scene("scene-b", 1, second_id, "source-b", 2),
        _scene("scene-a", 0, first_id, "source-a", 1),
    )

    route_request = _composer(payloads.get).compose_scene_overview(
        scenes,
        active_scene_key="scene-a",
    )

    assert route_request is not None
    request = cast(Any, route_request.request)
    assert route_request.route.route_kind == "scene_overview"
    assert route_request.route.route_key == "scene:scene-a"
    assert request.title == "All scenes"
    assert len(request.layers) == 2
    assert [layer.metadata["scene_key"] for layer in request.layers] == [
        "scene-a",
        "scene-b",
    ]
    assert {
        layer.metadata["representative_source_key"] for layer in request.layers
    } == {"source-a", "source-b"}
    assert all(isinstance(layer.layer_id, UUID) for layer in request.layers)


def test_scene_overview_composer_reuses_ordered_deterministic_layer_ids() -> None:
    """Recomposing one overview route should preserve ordered layer identities."""

    first_id = uuid4()
    second_id = uuid4()
    payloads = {
        first_id: _Image(640, 480),
        second_id: _Image(640, 480),
    }
    scenes = (
        _scene("scene-b", 1, second_id, "source-b", 2),
        _scene("scene-a", 0, first_id, "source-a", 1),
    )
    composer = _composer(payloads.get)

    first = composer.compose_scene_overview(scenes, active_scene_key="scene-a")
    second = composer.compose_scene_overview(scenes, active_scene_key="scene-a")

    assert first is not None
    assert second is not None
    first_request = cast(Any, first.request)
    second_request = cast(Any, second.request)
    assert [layer.metadata["scene_key"] for layer in first_request.layers] == [
        "scene-a",
        "scene-b",
    ]
    assert [layer.layer_id for layer in second_request.layers] == [
        layer.layer_id for layer in first_request.layers
    ]


def test_scene_overview_composer_prefers_preview_tile_when_available() -> None:
    """Accepted previews should replace missing final tiles in overview requests."""

    preview_id = uuid4()
    scene = _scene("scene-a", 0, None, "source-a", 1)

    route_request = _composer(
        lambda _image_id: None,
        preview_lookup=lambda _scene: OutputSceneOverviewPreview(
            image_id=preview_id,
            image=_Image(512, 512),
            source_key="source-a",
            set_index=3,
        ),
    ).compose_scene_overview(
        (scene,),
        active_scene_key=None,
    )

    assert route_request is not None
    request = cast(Any, route_request.request)
    layer = request.layers[0]
    assert route_request.route.route_key == "scene:"
    assert layer.image_id == preview_id
    assert layer.metadata["kind"] == "preview"
    assert layer.metadata["preview"] is True
    assert layer.metadata["representative_source_key"] == "source-a"
    assert layer.metadata["representative_set_index"] == 3


def test_scene_overview_preview_for_scene_adapts_valid_preview_slot() -> None:
    """Scene preview lookup should adapt lifecycle slots into composer previews."""

    preview_id = uuid4()
    scene = _scene("scene-a", 0, None, "source-a", 1)

    preview = scene_overview_preview_for_scene(
        scene,
        preview_image_cache={preview_id: "preview-image"},
        scene_preview_slots={
            "scene-a": ScenePreviewSlot(
                scene_run_id=scene.scene_run_id,
                scene_key="scene-a",
                source_key="source-a",
                set_index=1,
                preview_id=preview_id,
                generation_run_id="run-1",
            )
        },
        completed_preview_slots=set(),
    )

    assert preview == OutputSceneOverviewPreview(
        image_id=preview_id,
        image="preview-image",
        source_key="source-a",
        set_index=1,
    )


def test_scene_overview_preview_for_scene_rejects_completed_preview_slot() -> None:
    """Completed final output slots should suppress transient overview previews."""

    preview_id = uuid4()
    scene = _scene("scene-a", 0, preview_id, "source-a", 1)
    preview_slot = ScenePreviewSlot(
        scene_run_id=scene.scene_run_id,
        scene_key="scene-a",
        source_key="source-a",
        set_index=1,
        preview_id=preview_id,
        generation_run_id="run-1",
    )

    preview = scene_overview_preview_for_scene(
        scene,
        preview_image_cache={preview_id: "preview-image"},
        scene_preview_slots={"scene-a": preview_slot},
        completed_preview_slots={
            PreviewSlotKey(
                scene_run_id=scene.scene_run_id,
                scene_key="scene-a",
                source_key="source-a",
                set_index=1,
                generation_run_id="run-1",
            )
        },
    )

    assert preview is None


def _scene(
    scene_key: str,
    order: int,
    primary_image_id: UUID | None,
    source_key: str,
    set_index: int,
) -> OutputCanvasSceneGroup:
    """Return one scene-overview projection group."""

    return OutputCanvasSceneGroup(
        scene_run_id=f"run-{scene_key}",
        scene_key=scene_key,
        title=f"Scene {scene_key}",
        order=order,
        sources=(),
        primary_image_id=primary_image_id,
        representative_source_key=source_key,
        representative_set_index=set_index,
    )


def _composer(
    payload_lookup: Any,
    *,
    preview_lookup: Any | None = None,
) -> OutputSceneOverviewComposer:
    """Return a scene composer with deterministic responsive collaborators."""

    return OutputSceneOverviewComposer(
        payload_lookup=payload_lookup,
        preview_lookup=preview_lookup,
        scene_builder=OutputGridSceneBuilder(),
        viewport_extent=lambda: CanvasViewportExtent(1000.0, 1000.0),
    )
