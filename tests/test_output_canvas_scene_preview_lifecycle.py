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

"""Verify OutputCanvas scene-preview lifecycle behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from substitute.domain.workflow import ImageMeta
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_scene_overview,
)
from tests.canvas_widget_import_helpers import import_canvas_modules
from tests.support.output_canvas.grid_fakes import (
    attach_output_grid_layout_helpers,
    build_scene_preview_focus_fake,
    compose_scene_overview_route_request,
    route_application_controller,
)
from tests.support.output_canvas.host_fakes import bind_fake_output_projection
from tests.support.output_canvas.models import ImageStub
from tests.support.output_canvas.preview_fakes import (
    apply_registry_preview,
    install_fake_output_preview_controller,
    install_test_preview_lane,
    output_preview_cache,
)


def test_output_canvas_inactive_scene_preview_is_cached_without_focus(
    monkeypatch: Any,
) -> None:
    """Inactive scene previews should not interrupt the active scene view."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, added, current_ids, _composed = build_scene_preview_focus_fake(
        output_mod,
        active_scene_key="scene-a",
        active_scene_overview=False,
        scene_count=2,
    )

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="scene-b",
        scene_title="Scene B",
        scene_order=1,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )

    cache = output_preview_cache(output_mod, fake)
    scene_slot = output_mod._PreviewSlotKey(
        "run-1",
        "scene-b",
        "wf:upscale",
        1,
        "run-1",
    )
    scene_preview_id = cache.preview_ids_by_scene_slot[scene_slot]

    assert cache.scene_preview_slots_by_key["scene-b"].preview_id == scene_preview_id
    assert scene_preview_id in cache.preview_images_by_id
    assert any(cast(Any, call)[0] == scene_preview_id for call in added)
    assert cache.preview_ids_by_source_key == {}
    assert cache.preview_ids_by_source_slot == {}
    assert cache.preview_labels_by_source_key == {}
    assert cache.preview_images_by_source_key == {}
    assert current_ids == []


def test_output_canvas_active_scene_preview_still_takes_focus(
    monkeypatch: Any,
) -> None:
    """Active scene previews should keep the current live-preview behavior."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, added, current_ids, _composed = build_scene_preview_focus_fake(
        output_mod,
        active_scene_key="scene-b",
        active_scene_overview=False,
        scene_count=2,
    )

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="scene-b",
        scene_title="Scene B",
        scene_order=1,
        scene_count=2,
        include_scene=True,
        include_source=True,
    )

    cache = output_preview_cache(output_mod, fake)
    preview_id = cache.preview_ids_by_source_slot[
        output_mod._SourcePreviewSlotKey("run-1", "scene-b", "wf:upscale", 1, "run-1")
    ]

    assert cast(Any, added[-1])[0] == preview_id
    assert current_ids == [preview_id]


def test_output_canvas_single_scene_preview_behavior_is_unchanged(
    monkeypatch: Any,
) -> None:
    """Single-scene source previews should still become the active pane image."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, added, current_ids, _composed = build_scene_preview_focus_fake(
        output_mod,
        active_scene_key=None,
        active_scene_overview=False,
        scene_count=1,
    )

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
    )

    preview_id = output_preview_cache(output_mod, fake).preview_ids_by_source_key[
        "wf:upscale"
    ]

    assert cast(Any, added[-1])[0] == preview_id
    assert current_ids == [preview_id]


def test_output_canvas_inactive_scene_preview_retains_only_scene_scoped_state(
    monkeypatch: Any,
) -> None:
    """Inactive scene previews should not repopulate stale source-level caches."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, _added, current_ids, _composed = build_scene_preview_focus_fake(
        output_mod,
        active_scene_key="scene-a",
        active_scene_overview=False,
        scene_count=2,
    )

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="scene-b",
        scene_title="Scene B",
        scene_order=1,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )

    cache = output_preview_cache(output_mod, fake)
    scene_slot = output_mod._PreviewSlotKey(
        "run-1",
        "scene-b",
        "wf:upscale",
        1,
        "run-1",
    )
    scene_preview_id = cache.preview_ids_by_scene_slot[scene_slot]

    assert scene_preview_id in cache.preview_images_by_id
    assert cache.scene_preview_slots_by_key["scene-b"].preview_id == scene_preview_id
    assert cache.preview_ids_by_source_key == {}
    assert cache.preview_ids_by_source_slot == {}
    assert cache.preview_labels_by_source_key == {}
    assert cache.preview_images_by_source_key == {}
    assert current_ids == []


def test_output_canvas_scene_source_previews_use_distinct_scene_slot_ids(
    monkeypatch: Any,
) -> None:
    """Scene-aware source previews must not reuse IDs across scene tiles."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    added: list[object] = []
    pane = SimpleNamespace(
        addImage=lambda image_id, image, path: added.append((image_id, image, path)),
        setCurrentImageID=lambda _image_id: None,
        composeScene=lambda _request, activate=True: uuid4(),
    )
    fake = SimpleNamespace(
        pane=pane,
        images_by_id={},
        image_ids=[],
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        preview_ids_by_source_slot={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        source_groups={},
        scene_groups={},
        active_scene_key=None,
        active_scene_overview=False,
        scene_count=0,
        scene_overview_scene_id=None,
        scene_grid_layer_ids_by_key={},
        active_source_key=None,
        active_set_index=1,
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        set_count=0,
    )
    install_fake_output_preview_controller(output_mod, fake)
    fake._set_scene_preview_image = lambda image, **kwargs: (
        fake._preview_controller.set_scene_preview_image(image, **kwargs)
    )
    fake._activate_scene_overview = lambda: activate_output_scene_overview(
        fake,
        update_tabbar_container=fake._update_tabbar_container,
    )
    fake._compose_scene_overview_grid = lambda *, activate: (
        route_application_controller(
            output_mod,
            fake,
        ).present_scene_overview(activate=activate)
    )
    attach_output_grid_layout_helpers(fake)
    fake._sync_scene_selector_button = lambda: None
    fake._sync_set_selector_button = lambda: None
    fake._update_tabbar_container = lambda: None

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="scene1",
        scene_title="Scene 1",
        scene_order=0,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )
    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="run-1",
        scene_run_id="run-1",
        scene_key="scene2",
        scene_title="Scene 2",
        scene_order=1,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )

    scene1_slot = output_mod._PreviewSlotKey(
        "run-1",
        "scene1",
        "wf:upscale",
        1,
        "run-1",
    )
    scene2_slot = output_mod._PreviewSlotKey(
        "run-1",
        "scene2",
        "wf:upscale",
        1,
        "run-1",
    )
    cache = output_preview_cache(output_mod, fake)
    scene1_preview_id = cache.preview_ids_by_scene_slot[scene1_slot]
    scene2_preview_id = cache.preview_ids_by_scene_slot[scene2_slot]

    assert scene1_preview_id != scene2_preview_id
    assert any(cast(Any, call)[0] == scene1_preview_id for call in added)
    assert any(cast(Any, call)[0] == scene2_preview_id for call in added)
    assert cache.preview_ids_by_source_slot == {}


def test_output_canvas_scene_preview_accepts_later_running_source_slot(
    monkeypatch: Any,
) -> None:
    """Scene overview preview should advance to a later running source slot."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    added: list[object] = []
    pane = SimpleNamespace(
        addImage=lambda image_id, image, path: added.append((image_id, image, path)),
    )
    text_meta = ImageMeta("wf", "Text", 1, "", "", source_key="wf:text")
    fake = SimpleNamespace(
        pane=pane,
        images_by_id={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(
                    OutputCanvasSourceGroup(
                        source_key="wf:text",
                        label="Text",
                        images_by_set={1: OutputCanvasImageItem(uuid4(), text_meta, 1)},
                    ),
                ),
                representative_source_key="wf:text",
                representative_set_index=1,
            )
        },
        active_scene_key="portrait",
        active_scene_overview=False,
        scene_count=2,
    )
    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )
    cache = output_preview_cache(output_mod, fake)
    upscale_preview_id = cache.preview_ids_by_scene_slot[
        output_mod._PreviewSlotKey("run-1", "portrait", "wf:upscale", 1, "run-1")
    ]
    assert cache.scene_preview_slots_by_key["portrait"].preview_id == upscale_preview_id
    assert cache.scene_preview_slots_by_key["portrait"].source_key == "wf:upscale"
    assert (
        output_mod.output_scene_groups_by_key(
            output_mod.output_route_state_snapshot(fake)
        )["portrait"].preview_image_id
        is None
    )

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:text",
        source_label="Text",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )

    cache = output_preview_cache(output_mod, fake)
    text_preview_id = cache.preview_ids_by_scene_slot[
        output_mod._PreviewSlotKey("run-1", "portrait", "wf:text", 1, "run-1")
    ]
    assert cache.scene_preview_slots_by_key["portrait"].preview_id == text_preview_id
    assert cache.scene_preview_slots_by_key["portrait"].source_key == "wf:text"
    assert (
        output_mod.output_scene_groups_by_key(
            output_mod.output_route_state_snapshot(fake)
        )["portrait"].preview_image_id
        is None
    )
    assert upscale_preview_id != text_preview_id
    assert len(added) == 2


def test_output_canvas_scene_grid_tile_prefers_representative_final_over_later_outputs(
    monkeypatch: Any,
) -> None:
    """Scene overview tiles should use the scene group's stable representative final."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    representative_id = uuid4()
    later_output_id = uuid4()
    preview_id = uuid4()
    fake = SimpleNamespace(
        images_by_id={
            representative_id: ImageStub(512, 768),
            later_output_id: ImageStub(512, 768),
            preview_id: ImageStub(512, 768),
        },
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey("run-1", "portrait", "wf:text", 1): preview_id
        },
        scene_preview_slots_by_key={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=representative_id,
                representative_source_key="wf:text",
                representative_set_index=1,
            )
        },
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        scene_groups=tuple(fake.scene_groups.values()),
        active_scene_key="portrait",
        active_scene_overview=True,
        scene_count=1,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    route_request = compose_scene_overview_route_request(output_mod, fake)

    assert route_request is not None
    layer = cast(Any, route_request.request).layers[0]
    assert layer.image_id == representative_id
    assert layer.metadata["preview"] is False
    assert layer.metadata["representative_source_key"] == "wf:text"
    assert layer.metadata["representative_set_index"] == 1


def test_output_canvas_scene_grid_tile_prefers_later_source_preview_over_primary(
    monkeypatch: Any,
) -> None:
    """Scene overview tiles should show a later running preview before its final exists."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    primary_id = uuid4()
    preview_id = uuid4()
    fake = SimpleNamespace(
        images_by_id={
            primary_id: ImageStub(512, 768),
            preview_id: ImageStub(512, 768),
        },
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
            ): preview_id
        },
        scene_preview_slots_by_key={
            "portrait": output_mod._ScenePreviewSlot(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
                preview_id,
            )
        },
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=primary_id,
                preview_image_id=preview_id,
                representative_source_key="wf:text",
                representative_set_index=1,
            )
        },
    )
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=preview_id,
        image=fake.images_by_id[preview_id],
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
        accepted_for_overview=True,
    )
    route_request = compose_scene_overview_route_request(output_mod, fake)

    assert route_request is not None
    layer = cast(Any, route_request.request).layers[0]
    assert layer.image_id == preview_id
    assert layer.metadata["preview"] is True
    assert layer.metadata["representative_source_key"] == "wf:upscale"
    assert layer.metadata["representative_set_index"] == 1


def test_output_canvas_scene_grid_tile_prefers_accepted_later_preview_over_rep_preview(
    monkeypatch: Any,
) -> None:
    """Scene overview tiles should let accepted later previews beat stale rep previews."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    primary_id = uuid4()
    text_preview_id = uuid4()
    upscale_preview_id = uuid4()
    fake = SimpleNamespace(
        images_by_id={
            primary_id: ImageStub(512, 768),
            text_preview_id: ImageStub(512, 768),
            upscale_preview_id: ImageStub(512, 768),
        },
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey(
                "run-1",
                "portrait",
                "wf:text",
                1,
            ): text_preview_id,
            output_mod._PreviewSlotKey(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
            ): upscale_preview_id,
        },
        scene_preview_slots_by_key={
            "portrait": output_mod._ScenePreviewSlot(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
                upscale_preview_id,
            )
        },
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=primary_id,
                preview_image_id=upscale_preview_id,
                representative_source_key="wf:text",
                representative_set_index=1,
            )
        },
    )
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=upscale_preview_id,
        image=fake.images_by_id[upscale_preview_id],
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
        accepted_for_overview=True,
    )
    route_request = compose_scene_overview_route_request(output_mod, fake)

    assert route_request is not None
    layer = cast(Any, route_request.request).layers[0]
    assert layer.image_id == upscale_preview_id
    assert layer.metadata["preview"] is True
    assert layer.metadata["representative_source_key"] == "wf:upscale"
    assert layer.metadata["representative_set_index"] == 1


def test_output_canvas_scene_grid_tile_ignores_earlier_source_preview_after_final(
    monkeypatch: Any,
) -> None:
    """Scene overview tiles should not let stale earlier previews hide final output."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    final_id = uuid4()
    preview_id = uuid4()
    text_meta = ImageMeta("wf", "Text", 1, "", "", source_key="wf:text")
    fake = SimpleNamespace(
        images_by_id={
            final_id: ImageStub(512, 768),
            preview_id: ImageStub(512, 768),
        },
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey("run-1", "portrait", "wf:text", 1): preview_id
        },
        scene_preview_slots_by_key={
            "portrait": output_mod._ScenePreviewSlot(
                "run-1",
                "portrait",
                "wf:text",
                1,
                preview_id,
            )
        },
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(
                    OutputCanvasSourceGroup(
                        source_key="wf:text",
                        label="Text",
                        images_by_set={1: OutputCanvasImageItem(uuid4(), text_meta, 1)},
                    ),
                    OutputCanvasSourceGroup(
                        source_key="wf:upscale",
                        label="Upscale",
                        images_by_set={},
                    ),
                ),
                primary_image_id=final_id,
                representative_source_key="wf:upscale",
                representative_set_index=1,
            )
        },
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        scene_groups=tuple(fake.scene_groups.values()),
        active_scene_key="portrait",
        active_scene_overview=True,
        scene_count=1,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    route_request = compose_scene_overview_route_request(output_mod, fake)

    assert route_request is not None
    layer = cast(Any, route_request.request).layers[0]
    assert layer.image_id == final_id
    assert layer.metadata["preview"] is False
