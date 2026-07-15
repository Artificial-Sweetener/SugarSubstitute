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

"""Verify OutputCanvas preview lifecycle widget integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
    OutputPreviewLaneKey,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLanePlacement,
)
from substitute.domain.workflow import CanvasSessionRevision, ImageMeta
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_item,
    sync_output_set_selector_button,
)
from tests.canvas_widget_import_helpers import import_canvas_modules
from tests.support.output_canvas.grid_fakes import compose_scene_overview_route_request
from tests.support.output_canvas.host_fakes import (
    SignalStub,
    bind_fake_output_projection,
)
from tests.support.output_canvas.models import ImageStub
from tests.support.output_canvas.preview_fakes import (
    apply_registry_preview,
    ensure_output_preview_session,
    install_test_preview_lane,
    output_preview_cache,
    output_preview_registry,
    preview_close_identity,
)


def test_output_canvas_apply_preview_acceptance_rejects_stale_session_lane(
    monkeypatch: Any,
) -> None:
    """OutputCanvas should not register or route lanes from stale session revisions."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake = SimpleNamespace()
    session = ensure_output_preview_session(
        output_mod,
        fake,
        source_key="wf:node",
        scene_key=None,
        scene_title=None,
        scene_order=None,
        scene_count=None,
    )
    registered: list[UUID] = []
    fake._qpane_presenter = SimpleNamespace(
        register_image=lambda image_id, _image, _path: registered.append(image_id),
        remove_image=lambda _image_id: None,
    )
    preview_id = uuid4()
    stale_lane = OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            source_key="wf:node",
        ),
        preview_id=preview_id,
        image=ImageStub(64, 64),
        source_label="Node",
        client_id="client-1",
        session_revision=session.revision.next(),
    )

    output_mod.OutputCanvas.apply_preview_acceptance(
        fake,
        output_mod.OutputPreviewAcceptance(accepted=True, lanes=(stale_lane,)),
    )

    assert registered == []


def test_output_canvas_preview_reuses_source_uuid_and_stays_out_of_outputs(
    monkeypatch: Any,
) -> None:
    """Source previews should replace one transient UUID without joining grids."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    added: list[tuple[object, object, object]] = []
    current_ids: list[object] = []
    composed: list[tuple[object, bool]] = []

    def add_image(image_id: object, image: object, path: object) -> None:
        """Record image additions made by the preview lifecycle path."""

        added.append((image_id, image, path))

    def compose_scene(request: Any, activate: bool = True) -> object:
        """Record deterministic composition requests without creating QPane scenes."""

        composed.append((request, activate))
        return request.composition_id

    tab_items: dict[str, object] = {}

    def remove_tab_item(key: str) -> object | None:
        """Record source-tab removal by mutating the fake tab item map."""

        return tab_items.pop(key, None)

    def add_tab_item(key: str, label: object) -> None:
        """Record source-tab insertion by mutating the fake tab item map."""

        tab_items[key] = label

    selector = SimpleNamespace()

    def set_selector_text(text: object) -> None:
        """Record selector text updates on the fake selector."""

        selector.text = text

    def set_selector_visible(visible: object) -> None:
        """Record selector visibility updates on the fake selector."""

        selector.visible = visible

    pane = SimpleNamespace(
        addImage=add_image,
        setCurrentImageID=lambda image_id: current_ids.append(image_id),
        composeScene=compose_scene,
    )
    tabbar = SimpleNamespace(
        items=tab_items,
        currentItemChanged=SignalStub(),
        removeWidget=remove_tab_item,
        addItem=add_tab_item,
        adjustSize=lambda: None,
        setCurrentItem=lambda _key: None,
    )
    selector = SimpleNamespace(
        setText=set_selector_text,
        setVisible=set_selector_visible,
    )
    fake = SimpleNamespace(
        pane=pane,
        images_by_id={},
        image_ids=[],
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        source_groups={},
        active_source_key=None,
        active_scene_key=None,
        active_scene_overview=False,
        scene_count=0,
        active_set_index=1,
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
        set_count=0,
        _update_tabbar_container=lambda: None,
        _on_tab_changed=lambda _route: None,
    )
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(256, 384),
        source_key="wf-1:node",
        source_label="Cube",
    )
    first_preview_id = output_preview_cache(
        output_mod,
        fake,
    ).preview_ids_by_source_key["wf-1:node"]
    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(256, 384),
        source_key="wf-1:node",
        source_label="Cube",
    )

    assert (
        output_preview_cache(output_mod, fake).preview_ids_by_source_key["wf-1:node"]
        == first_preview_id
    )
    assert [call[0] for call in added] == [first_preview_id, first_preview_id]
    assert current_ids == [first_preview_id, first_preview_id]
    assert fake.image_ids == []
    assert fake.source_groups == {}
    assert tab_items == {}
    assert composed == []


def test_output_canvas_register_output_clears_matching_scene_preview_slot(
    monkeypatch: Any,
) -> None:
    """Final output registration should retire its exact scene preview slot."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    preview_id = uuid4()
    output_id = uuid4()
    fake = SimpleNamespace(
        images_by_id={preview_id: ImageStub(512, 768)},
        metas_by_id={},
        image_ids=[],
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
                preview_image_id=preview_id,
                representative_source_key="wf:text",
                representative_set_index=1,
                status="running",
            )
        },
    )
    close_identity = preview_close_identity(
        output_mod,
        image_id=output_id,
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="run-1",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
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

    output_mod.OutputCanvas.close_final_output_preview_lane(fake, close_identity)

    cache = output_preview_cache(output_mod, fake)
    assert cache.scene_preview_slots_by_key == {}
    assert cache.preview_ids_by_scene_slot == {}
    assert preview_id not in cache.preview_images_by_id


def test_output_canvas_register_output_commits_scene_overview_final(
    monkeypatch: Any,
) -> None:
    """Preview closure should retire scene previews without composing finals."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    preview_id = uuid4()
    output_id = uuid4()
    removed: list[object] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(removeImageByID=lambda image_id: removed.append(image_id)),
        images_by_id={preview_id: ImageStub(512, 768)},
        metas_by_id={},
        image_ids=[],
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey(
                "run-1",
                "scene3",
                "wf:upscale",
                1,
            ): preview_id
        },
        scene_preview_slots_by_key={
            "scene3": output_mod._ScenePreviewSlot(
                "run-1",
                "scene3",
                "wf:upscale",
                1,
                preview_id,
            )
        },
        scene_groups={
            "scene3": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="scene3",
                title="Scene 3",
                order=2,
                sources=(),
                preview_image_id=preview_id,
                representative_source_key="wf:upscale",
                representative_set_index=1,
                status="running",
            )
        },
        active_scene_overview=True,
        scene_count=3,
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        scene_groups=tuple(fake.scene_groups.values()),
        active_scene_key="scene3",
        active_scene_overview=True,
        scene_count=3,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    close_identity = preview_close_identity(
        output_mod,
        image_id=output_id,
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="run-1",
        scene_run_id="run-1",
        scene_key="scene3",
        scene_title="Scene 3",
        scene_order=2,
        scene_count=3,
    )
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=preview_id,
        image=fake.images_by_id[preview_id],
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="scene3",
        scene_title="Scene 3",
        scene_order=2,
        scene_count=3,
        accepted_for_overview=True,
    )

    output_mod.OutputCanvas.close_final_output_preview_lane(fake, close_identity)

    route_request = compose_scene_overview_route_request(output_mod, fake)

    assert removed == [preview_id]
    cache = output_preview_cache(output_mod, fake)
    assert preview_id not in cache.preview_images_by_id
    scene3 = output_mod.output_scene_groups_by_key(
        output_mod.output_route_state_snapshot(fake)
    )["scene3"]
    assert scene3.primary_image_id is None
    assert scene3.representative_source_key == "wf:upscale"
    assert scene3.representative_set_index == 1
    assert route_request is None


def test_output_canvas_register_output_retires_matching_source_preview(
    monkeypatch: Any,
) -> None:
    """Final output registration should retire the matching source preview image."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    scene_preview_id = uuid4()
    source_preview_id = uuid4()
    output_id = uuid4()
    removed: list[object] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(removeImageByID=lambda image_id: removed.append(image_id)),
        images_by_id={
            scene_preview_id: ImageStub(512, 768),
            source_preview_id: ImageStub(512, 768),
        },
        metas_by_id={},
        image_ids=[],
        preview_ids_by_source_key={"wf:upscale": source_preview_id},
        preview_ids_by_source_slot={
            output_mod._SourcePreviewSlotKey(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
            ): source_preview_id
        },
        preview_labels_by_source_key={"wf:upscale": "Upscale"},
        preview_images_by_source_key={"wf:upscale": ImageStub(512, 768)},
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
            ): scene_preview_id
        },
        scene_preview_slots_by_key={
            "portrait": output_mod._ScenePreviewSlot(
                "run-1",
                "portrait",
                "wf:upscale",
                1,
                scene_preview_id,
            )
        },
        scene_groups={},
        grid_layer_ids_by_key={("wf:upscale", source_preview_id): uuid4()},
    )
    close_identity = preview_close_identity(
        output_mod,
        image_id=output_id,
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="run-1",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
    )
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=scene_preview_id,
        image=fake.images_by_id[scene_preview_id],
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
        accepted_for_overview=True,
    )
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=source_preview_id,
        image=fake.images_by_id[source_preview_id],
        source_key="wf:upscale",
        source_label="Upscale",
        scene_run_id="run-1",
        scene_key="portrait",
        placement=OutputPreviewLanePlacement.SOURCE,
    )

    output_mod.OutputCanvas.close_final_output_preview_lane(fake, close_identity)

    cache = output_preview_cache(output_mod, fake)
    assert scene_preview_id not in cache.preview_images_by_id
    assert source_preview_id not in cache.preview_images_by_id
    assert cache.preview_ids_by_source_key == {}
    assert cache.preview_ids_by_source_slot == {}
    assert cache.preview_labels_by_source_key == {}
    assert cache.preview_images_by_source_key == {}
    assert fake.grid_layer_ids_by_key
    assert set(removed) == {scene_preview_id, source_preview_id}


def test_output_canvas_register_output_does_not_close_duplicate_label_scene_preview(
    monkeypatch: Any,
) -> None:
    """Final outputs must not close preview lanes by display label alone."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    preview_id = uuid4()
    text_final_id = uuid4()
    upscale_final_id = uuid4()
    removed: list[object] = []
    text_meta = ImageMeta("workflow_76353", "Text to Image", 1, "", "")
    fake = SimpleNamespace(
        pane=SimpleNamespace(removeImageByID=lambda image_id: removed.append(image_id)),
        images_by_id={
            preview_id: ImageStub(512, 768),
            text_final_id: ImageStub(512, 768),
        },
        metas_by_id={},
        image_ids=[],
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey(
                "scene-run-1",
                "scene5",
                "workflow_76353:10",
                1,
                "generation-1",
            ): preview_id
        },
        scene_preview_slots_by_key={
            "scene5": output_mod._ScenePreviewSlot(
                scene_run_id="scene-run-1",
                generation_run_id="generation-1",
                scene_key="scene5",
                source_key="workflow_76353:10",
                set_index=1,
                preview_id=preview_id,
                source_label="Diffusion Upscale",
            )
        },
        scene_groups={
            "scene5": OutputCanvasSceneGroup(
                scene_run_id="scene-run-1",
                scene_key="scene5",
                title="Scene 5",
                order=4,
                sources=(
                    OutputCanvasSourceGroup(
                        source_key="workflow_76353:7",
                        label="Text to Image",
                        images_by_set={
                            1: OutputCanvasImageItem(text_final_id, text_meta, 1)
                        },
                    ),
                ),
                primary_image_id=text_final_id,
                representative_source_key="workflow_76353:7",
                representative_set_index=1,
                status="running",
            )
        },
        active_scene_overview=True,
        scene_count=5,
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        scene_groups=tuple(fake.scene_groups.values()),
        active_scene_key="scene5",
        active_scene_overview=True,
        scene_count=5,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    close_identity = preview_close_identity(
        output_mod,
        image_id=upscale_final_id,
        source_key="workflow_76353:16",
        source_label="Diffusion Upscale",
        generation_run_id="generation-1",
        scene_run_id="scene-run-1",
        scene_key="scene5",
        scene_title="Scene 5",
        scene_order=4,
        scene_count=5,
    )
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=preview_id,
        image=fake.images_by_id[preview_id],
        source_key="workflow_76353:10",
        source_label="Diffusion Upscale",
        generation_run_id="generation-1",
        scene_run_id="scene-run-1",
        scene_key="scene5",
        scene_title="Scene 5",
        scene_order=4,
        scene_count=5,
        accepted_for_overview=True,
    )

    output_mod.OutputCanvas.close_final_output_preview_lane(fake, close_identity)

    route_request = compose_scene_overview_route_request(output_mod, fake)

    assert removed == []
    cache = output_preview_cache(output_mod, fake)
    assert preview_id in cache.preview_images_by_id
    assert "scene5" in cache.scene_preview_slots_by_key
    scene5 = output_mod.output_scene_groups_by_key(
        output_mod.output_route_state_snapshot(fake)
    )["scene5"]
    assert scene5.preview_image_id is None
    assert scene5.representative_source_key == "workflow_76353:7"
    assert route_request is not None
    layer = cast(Any, route_request.request).layers[0]
    assert layer.image_id == preview_id
    assert layer.metadata["preview"] is True
    assert layer.metadata["representative_source_key"] == "workflow_76353:10"


def test_output_canvas_register_output_clears_only_matching_scene_preview_slot(
    monkeypatch: Any,
) -> None:
    """Preview clearing should be scoped to the matching scene/source/set."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    scene1_preview_id = uuid4()
    scene2_preview_id = uuid4()
    output_id = uuid4()
    fake = SimpleNamespace(
        images_by_id={
            scene1_preview_id: ImageStub(512, 768),
            scene2_preview_id: ImageStub(512, 768),
        },
        metas_by_id={},
        image_ids=[],
        preview_ids_by_scene_slot={
            output_mod._PreviewSlotKey(
                "run-1",
                "scene1",
                "wf:upscale",
                1,
            ): scene1_preview_id,
            output_mod._PreviewSlotKey(
                "run-1",
                "scene2",
                "wf:upscale",
                1,
            ): scene2_preview_id,
        },
        scene_preview_slots_by_key={
            "scene1": output_mod._ScenePreviewSlot(
                "run-1",
                "scene1",
                "wf:upscale",
                1,
                scene1_preview_id,
            ),
            "scene2": output_mod._ScenePreviewSlot(
                "run-1",
                "scene2",
                "wf:upscale",
                1,
                scene2_preview_id,
            ),
        },
        scene_groups={},
    )
    close_identity = preview_close_identity(
        output_mod,
        image_id=output_id,
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="run-1",
        scene_run_id="run-1",
        scene_key="scene2",
        scene_title="Scene 2",
        scene_order=1,
        scene_count=2,
    )

    registry = output_preview_registry(output_mod, fake)
    for scene_key, preview_id in (
        ("scene1", scene1_preview_id),
        ("scene2", scene2_preview_id),
    ):
        registry.store_accepted_lane(
            OutputPreviewLane(
                key=OutputPreviewLaneKey.scene(
                    workflow_id="wf",
                    generation_run_id="run-1",
                    prompt_id="prompt-1",
                    source_key="wf:upscale",
                    scene_run_id="run-1",
                    scene_key=scene_key,
                ),
                preview_id=preview_id,
                image=fake.images_by_id[preview_id],
                source_label="Upscale",
                client_id="client-1",
                session_revision=CanvasSessionRevision(1),
                accepted_for_overview=True,
            )
        )

    output_mod.OutputCanvas.close_final_output_preview_lane(fake, close_identity)

    cache = output_preview_cache(output_mod, fake)
    assert cache.scene_preview_slots_by_key == {
        "scene1": output_mod._ScenePreviewSlot(
            "run-1",
            "scene1",
            "wf:upscale",
            1,
            scene1_preview_id,
            generation_run_id="run-1",
            source_label="Upscale",
        )
    }
    assert scene1_preview_id in cache.preview_images_by_id
    assert scene2_preview_id not in cache.preview_images_by_id


def test_output_canvas_clear_previews_removes_transient_catalog_entries(
    monkeypatch: Any,
) -> None:
    """Preview cleanup should remove transient IDs and preview-only source tabs."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    preview_id = uuid4()
    removed: list[object] = []
    tab_items: dict[str, object] = {"wf-1:node": object()}

    def remove_tab_item(key: str) -> object | None:
        """Record source-tab removal by mutating the fake tab item map."""

        return tab_items.pop(key, None)

    def add_tab_item(key: str, label: object) -> None:
        """Record source-tab insertion by mutating the fake tab item map."""

        tab_items[key] = label

    tabbar = SimpleNamespace(
        items=tab_items,
        currentItemChanged=SignalStub(),
        removeWidget=remove_tab_item,
        addItem=add_tab_item,
        adjustSize=lambda: None,
        setCurrentItem=lambda _key: None,
    )
    fake = SimpleNamespace(
        pane=SimpleNamespace(removeImageByID=lambda image_id: removed.append(image_id)),
        images_by_id={preview_id: "preview"},
        preview_ids_by_source_key={"wf-1:node": preview_id},
        preview_labels_by_source_key={"wf-1:node": "Cube"},
        preview_images_by_source_key={"wf-1:node": "preview"},
        source_groups={
            "wf-1:node": SimpleNamespace(
                source_key="wf-1:node",
                label="Cube",
                images_by_set={},
            )
        },
        grid_scene_ids_by_source_key={"wf-1:node": uuid4()},
        grid_layer_ids_by_key={("wf-1:node", preview_id): uuid4()},
        active_source_key="wf-1:node",
        _unscoped_preview_image_id=uuid4(),
        tabbar=tabbar,
        _on_tab_changed=lambda _route: None,
    )
    fake._grid_available_for_current_source = lambda: False
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=preview_id,
        image=fake.images_by_id[preview_id],
        source_key="wf-1:node",
        source_label="Cube",
    )

    output_mod.OutputCanvas.clear_previews(fake)

    assert removed == [preview_id]
    assert output_preview_cache(output_mod, fake).preview_ids_by_source_key == {}
    assert fake.grid_layer_ids_by_key


def test_output_canvas_clear_previews_fallback_does_not_emit_uuid(
    monkeypatch: Any,
) -> None:
    """Preview cleanup fallback should not persist manual output UUID focus."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    preview_id = uuid4()
    final_id = uuid4()
    removed: list[object] = []
    pane_ids: list[object] = []
    control_modes: list[str] = []
    active_signal = SignalStub()
    tabbar = SimpleNamespace(
        items={"wf-1:node": object()},
        setCurrentItem=lambda _key: None,
    )
    selector = SimpleNamespace()

    def set_selector_text(text: object) -> None:
        """Record selector text updates on the fake selector."""

        selector.text = text

    def set_selector_visible(visible: object) -> None:
        """Record selector visibility updates on the fake selector."""

        selector.visible = visible

    selector.setText = set_selector_text
    selector.setVisible = set_selector_visible
    final_meta = ImageMeta("wf-1", "Cube", 1, "", "", source_key="wf-1:node")
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            removeImageByID=lambda image_id: removed.append(image_id),
            setCurrentImageID=lambda image_id: pane_ids.append(image_id),
            setControlMode=lambda mode: control_modes.append(mode),
        ),
        activeOutputChanged=active_signal,
        images_by_id={preview_id: "preview", final_id: "final"},
        metas_by_id={},
        image_ids=[final_id],
        preview_ids_by_source_key={"wf-1:node": preview_id},
        preview_labels_by_source_key={"wf-1:node": "Cube"},
        preview_images_by_source_key={"wf-1:node": "preview"},
        preview_ids_by_source_slot={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        scene_groups={},
        source_groups={
            "wf-1:node": OutputCanvasSourceGroup(
                source_key="wf-1:node",
                label="Cube",
                images_by_set={
                    1: OutputCanvasImageItem(final_id, final_meta, 1),
                },
            )
        },
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        active_source_key="wf-1:node",
        active_set_index=0,
        last_real_set_index=1,
        active_scene_overview=False,
        scene_count=1,
        _unscoped_preview_image_id=uuid4(),
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
        set_count=1,
        _update_tabbar_container=lambda: None,
    )
    fake._grid_available_for_current_source = lambda: False
    fake._activate_output_item = lambda source_key, item, **kwargs: (
        activate_output_item(
            fake,
            source_key,
            item,
            update_tabbar_container=fake._update_tabbar_container,
            **kwargs,
        )
    )
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=preview_id,
        image=fake.images_by_id[preview_id],
        source_key="wf-1:node",
        source_label="Cube",
    )

    output_mod.OutputCanvas.clear_previews(fake, source_key="wf-1:node")

    assert removed == [preview_id]
    assert pane_ids == []
    assert control_modes == []
    assert fake.active_source_key == "wf-1:node"
    assert fake.active_set_index == 0
    assert fake.last_real_set_index == 1
    assert active_signal.calls == []


def test_output_canvas_clear_previews_refreshes_active_scene_overview(
    monkeypatch: Any,
) -> None:
    """Preview cleanup should recompose active All after transient images are removed."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    preview_id = uuid4()
    removed: list[object] = []
    refreshes: list[object] = []

    def activate_scene_overview() -> bool:
        """Record active scene-overview refresh attempts for clear-preview cleanup."""

        refreshes.append(True)
        return True

    fake = SimpleNamespace(
        pane=SimpleNamespace(removeImageByID=lambda image_id: removed.append(image_id)),
        images_by_id={preview_id: "preview"},
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
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
        source_groups={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        active_source_key=None,
        active_scene_key="portrait",
        active_scene_overview=True,
        scene_count=2,
        _unscoped_preview_image_id=uuid4(),
        tabbar=SimpleNamespace(items={}),
        _on_tab_changed=lambda _route: None,
        _activate_scene_overview=activate_scene_overview,
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

    output_mod.OutputCanvas.clear_previews(fake)

    assert removed == [preview_id]
    cache = output_preview_cache(output_mod, fake)
    assert cache.preview_ids_by_scene_slot == {}
    assert cache.scene_preview_slots_by_key == {}
    assert refreshes == []
