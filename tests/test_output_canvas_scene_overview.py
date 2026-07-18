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

"""Verify OutputCanvas scene-overview widget integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4
from PySide6.QtCore import QEvent
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)

from substitute.domain.workflow import CanvasRouteIdentity, ImageMeta
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_grid_for_source,
    activate_output_scene,
    activate_output_scene_overview,
    sync_output_set_selector_button,
)
from tests.canvas_widget_import_helpers import import_canvas_modules
from tests.support.output_canvas.grid_fakes import (
    attach_output_grid_layout_helpers,
    attach_scene_overview_compose_helpers,
    build_scene_preview_focus_fake,
    grid_mouse_event,
    install_fake_output_grid_event_controller,
    install_fake_output_interaction_controller,
    route_application_controller,
)
from tests.support.output_canvas.host_fakes import (
    SignalStub,
    bind_fake_output_projection,
    install_fake_navigation_chrome,
)
from tests.support.output_canvas.models import ImageStub
from tests.support.output_canvas.preview_fakes import (
    apply_registry_preview,
    output_preview_cache,
)
from tests.support.output_canvas.projection_fakes import (
    install_fake_output_source_tabs_controller,
)
from tests.support.output_canvas.route_fakes import RecordingOutputRouteProjector


def test_output_canvas_scene_overview_composes_scene_grid(
    monkeypatch: Any,
) -> None:
    """Scene overview should compose one clickable tile per scene result."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    first_id = uuid4()
    second_id = uuid4()
    route_projector = RecordingOutputRouteProjector()
    fake = SimpleNamespace(
        pane=SimpleNamespace(),
        _route_projector=route_projector,
        scene_overview_scene_id=None,
        scene_grid_layer_ids_by_key={},
        images_by_id={
            first_id: ImageStub(512, 768),
            second_id: ImageStub(512, 768),
        },
        scene_preview_slots_by_key={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=first_id,
            ),
            "cafe": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="cafe",
                title="Cafe",
                order=1,
                sources=(),
                primary_image_id=second_id,
            ),
        },
    )
    attach_scene_overview_compose_helpers(fake, output_mod)

    route_application_controller(output_mod, fake).present_scene_overview(activate=True)

    request, activate = route_projector.scene_overview_calls[0]
    scene_request = cast(Any, request)
    assert activate is True
    assert scene_request.title == "All scenes"
    assert [layer.role for layer in scene_request.layers] == [
        "scene-output",
        "scene-output",
    ]
    assert [layer.metadata["scene_key"] for layer in scene_request.layers] == [
        "portrait",
        "cafe",
    ]
    assert {layer.metadata["scene_run_id"] for layer in scene_request.layers} == {
        "run-1"
    }
    assert all(layer.metadata["grid_kind"] == "scene" for layer in scene_request.layers)


def test_output_canvas_scene_overview_caches_missing_layer_images(
    monkeypatch: Any,
) -> None:
    """Scene overview composition should repair stale QPane catalog gaps."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    first_id = uuid4()
    second_id = uuid4()
    compositions: dict[UUID, object] = {}
    pane_images: dict[UUID, tuple[object, object]] = {}
    current_composition_id: UUID | None = None

    def compose_scene(request: object, *, activate: bool = True) -> UUID:
        """Compose only when every scene layer exists in the fake catalog."""

        nonlocal current_composition_id
        scene_request = cast(Any, request)
        for layer in scene_request.layers:
            if layer.image_id not in pane_images:
                raise KeyError("scene layer image_id must exist in the catalog")
        composition_id = cast(UUID, scene_request.composition_id)
        compositions[composition_id] = SimpleNamespace(
            composition_id=composition_id,
            kind="layered-scene",
            source_image_ids=tuple(layer.image_id for layer in scene_request.layers),
            current_image_id=None,
            comparison=SimpleNamespace(enabled=False, source_id=None),
        )
        if activate:
            current_composition_id = composition_id
        return composition_id

    pane = SimpleNamespace(
        addImage=lambda image_id, image, path: pane_images.__setitem__(
            image_id,
            (image, path),
        ),
        imageIDs=lambda: list(pane_images),
        composeScene=compose_scene,
        currentImageID=lambda: None,
        currentCompositionID=lambda: current_composition_id,
        getCompositionSnapshot=lambda: SimpleNamespace(
            current_composition_id=current_composition_id,
            compositions=compositions,
        ),
        clearComparisonImage=lambda: None,
        setCurrentImageID=lambda _image_id: None,
    )
    first_image = ImageStub(512, 768)
    second_image = ImageStub(512, 768)
    fake = SimpleNamespace(
        pane=pane,
        scene_overview_scene_id=None,
        scene_grid_layer_ids_by_key={},
        images_by_id={first_id: first_image, second_id: second_image},
        scene_preview_slots_by_key={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=first_id,
            ),
            "cafe": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="cafe",
                title="Cafe",
                order=1,
                sources=(),
                primary_image_id=second_id,
            ),
        },
    )
    attach_scene_overview_compose_helpers(fake, output_mod)

    composition_id = route_application_controller(
        output_mod,
        fake,
    ).present_scene_overview(activate=True)

    assert composition_id is not None
    assert set(pane_images) == {first_id, second_id}
    assert pane_images[first_id][0] is first_image
    assert pane_images[second_id][0] is second_image


def test_output_canvas_activate_scene_overview_clears_source_route(
    monkeypatch: Any,
) -> None:
    """Scene overview activation should clear stale source navigation state."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    scene_id = uuid4()
    removed_tabs: list[str] = []
    tabbar = _tabbar(removed=removed_tabs, items={"source-a": object()})
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            currentImageID=lambda: None,
            setControlMode=lambda _mode: None,
        ),
        tabbar=tabbar,
        scene_count=2,
        active_scene_key="scene-a",
        active_scene_overview=False,
        active_source_key="source-a",
        active_set_index=1,
        source_groups={"source-a": object()},
        set_count=3,
        _compose_scene_overview_grid=lambda *, activate: scene_id,
        _on_tab_changed=lambda _route: None,
        _sync_scene_selector_button=lambda: None,
        _sync_set_selector_button=lambda: None,
        _sync_source_selector_button=lambda: None,
        _update_tabbar_container=lambda: None,
    )
    install_fake_output_interaction_controller(fake)
    install_fake_output_source_tabs_controller(output_mod, fake)

    activated = activate_output_scene_overview(
        fake,
        update_tabbar_container=fake._update_tabbar_container,
    )

    assert activated is True
    assert fake.active_scene_overview is True
    assert fake.active_source_key is None
    assert fake.set_count == 0
    assert removed_tabs == ["source-a"]
    assert tabbar.items == {}


def test_output_canvas_scene_preview_updates_overview_without_switching_to_image(
    monkeypatch: Any,
) -> None:
    """Scene previews should refresh All without taking over the pane image."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, added, current_ids, _composed = build_scene_preview_focus_fake(
        output_mod,
        active_scene_key=None,
        active_scene_overview=False,
        scene_count=0,
    )

    apply_registry_preview(
        output_mod,
        fake,
        ImageStub(512, 768),
        source_key="wf:node",
        source_label="Cube",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
        include_scene=True,
        include_source=False,
    )

    assert fake.active_scene_overview is True
    assert added
    assert current_ids == []


def test_output_canvas_overview_scene_preview_updates_without_raw_focus(
    monkeypatch: Any,
) -> None:
    """All-scenes previews should update overview composition without raw focus."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, added, current_ids, _composed = build_scene_preview_focus_fake(
        output_mod,
        active_scene_key="scene-a",
        active_scene_overview=True,
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
    preview_id = cache.preview_ids_by_scene_slot[
        output_mod._PreviewSlotKey("run-1", "scene-b", "wf:upscale", 1, "run-1")
    ]

    assert any(cast(Any, call)[0] == preview_id for call in added)
    assert cache.preview_ids_by_source_key == {}
    assert cache.preview_ids_by_source_slot == {}
    assert cache.preview_labels_by_source_key == {}
    assert cache.preview_images_by_source_key == {}
    assert current_ids == []


def test_output_canvas_scene_grid_click_activates_scene(monkeypatch: Any) -> None:
    """Clicking an All-scenes tile should enter that scene's batch level."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.presentation.canvas.qpane.canvas_route_projector import (  # noqa: PLC0415
        OutputRouteProjector,
    )
    from substitute.presentation.canvas.qpane.output_pane_adapter import (  # noqa: PLC0415
        OutputQPaneRouteAdapter,
    )

    image_id = uuid4()
    hit_calls: list[object] = []
    hit = SimpleNamespace(
        role="scene-output",
        metadata={"grid_kind": "scene", "scene_key": "cafe"},
        image_id=image_id,
    )
    image_meta = _image_meta(source_key="source-a", set_index=1)
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={1: OutputCanvasImageItem(image_id, image_meta, 1)},
    )
    scene_group = OutputCanvasSceneGroup(
        scene_run_id="run-1",
        scene_key="cafe",
        title="Cafe",
        order=1,
        sources=(source,),
        primary_image_id=image_id,
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_groups=(scene_group,),
        active_scene_key="cafe",
        active_scene_overview=True,
        scene_count=1,
    )
    route = CanvasRouteIdentity(
        route_kind="scene_overview",
        route_key="scene:cafe",
    )
    boundary = create_canvas_session_boundary()
    session = bind_output_canvas_session(
        boundary,
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={image_id: source.images_by_set[1].image_meta},
    )
    projector = OutputRouteProjector(
        OutputQPaneRouteAdapter(SimpleNamespace()),
        session_boundary=boundary,
    )
    route_scope = output_mod.OutputRouteScope(
        session=session,
        allowed_image_ids=frozenset({image_id}),
        allowed_source_keys=frozenset({"source-a"}),
        allowed_scene_keys=frozenset({"cafe"}),
        allowed_composition_ids=session.allowed_composition_ids,
    )
    projector.bind(route_scope)
    composition_id = projector.route_composition_id(route)
    hit.composition_id = composition_id

    def scene_hit_test(point: object) -> object:
        """Record the requested scene hit-test point and return the fake tile."""

        hit_calls.append(point)
        return hit

    pane = SimpleNamespace(
        sceneHitTest=scene_hit_test,
        setControlMode=lambda _mode: None,
        currentCompositionID=lambda: composition_id,
        getCompositionSnapshot=lambda: SimpleNamespace(
            current_composition_id=composition_id,
            compositions={
                composition_id: SimpleNamespace(
                    source_image_ids=(image_id,),
                    current_image_id=None,
                    comparison=SimpleNamespace(enabled=False, source_id=None),
                )
            },
        ),
    )
    bound_projector = OutputRouteProjector(
        OutputQPaneRouteAdapter(pane),
        session_boundary=boundary,
    )
    bound_projector.bind(route_scope)
    fake = SimpleNamespace(
        pane=pane,
        _route_session_boundary=boundary,
        _route_projector=bound_projector,
        _projection_workflow_id="wf",
        _output_projection=projection,
        active_scene_overview=True,
        active_scene_key="cafe",
        active_source_key=None,
        active_set_index=1,
        last_real_set_index=1,
        set_count=1,
        activeOutputSceneChanged=SignalStub(),
        activeOutputGridChanged=SignalStub(),
        activeOutputChanged=SignalStub(),
        _grid_click_press_pos=None,
        scene_groups={"cafe": scene_group},
        preview_ids_by_source_key={},
        preview_ids_by_source_slot={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        tabbar=SimpleNamespace(items={}),
        _source_tabs_controller=SimpleNamespace(
            rebuild_source_tabs=lambda *, active_source_key: None,
            refresh_source_tab_tooltips=lambda: None,
        ),
        _sync_set_selector_button=lambda: None,
        _sync_scene_selector_button=lambda: None,
        _sync_source_selector_button=lambda: None,
    )
    install_fake_navigation_chrome(fake)
    install_fake_output_grid_event_controller(output_mod, fake)

    press = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonPress,
        10,
        10,
    )
    release = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonRelease,
        12,
        12,
    )

    assert fake._grid_event_controller.handle_event_filter(fake.pane, press) is False
    assert fake._grid_event_controller.handle_event_filter(fake.pane, release) is False

    assert hit_calls
    assert fake.active_scene_key == "cafe"
    assert fake.active_scene_overview is False
    assert fake.active_source_key == "source-a"
    assert fake.active_set_index == 0
    assert fake.activeOutputSceneChanged.calls == [
        (
            OutputSceneNavigationSelection(
                scene_key="cafe",
                overview=False,
                source_key="source-a",
                set_index=0,
                image_id=None,
            ),
        )
    ]


def test_output_canvas_scene_grid_click_opens_representative_source_grid(
    monkeypatch: Any,
) -> None:
    """Clicking a scene tile should enter the scene at its representative source."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    text_ids = [uuid4(), uuid4()]
    upscale_ids = [uuid4(), uuid4()]
    compose_calls: list[object] = []
    control_modes: list[str] = []
    tabbar = _tabbar()
    selector = _selector_button()
    scene_selector = _scene_selector_button()
    text_source = OutputCanvasSourceGroup(
        source_key="wf:text",
        label="Text to Image",
        images_by_set={
            index: OutputCanvasImageItem(
                image_id,
                _image_meta(source_key="wf:text", set_index=index),
                index,
            )
            for index, image_id in enumerate(text_ids, start=1)
        },
    )
    upscale_source = OutputCanvasSourceGroup(
        source_key="wf:upscale",
        label="Diffusion Upscale",
        images_by_set={
            index: OutputCanvasImageItem(
                image_id,
                _image_meta(source_key="wf:upscale", set_index=index),
                index,
            )
            for index, image_id in enumerate(upscale_ids, start=1)
        },
    )

    def compose_scene(request: object, *, activate: bool = True) -> UUID:
        """Record grid composition requests and return the requested scene ID."""

        route_request = cast(Any, request)
        compose_calls.append((request, activate))
        return cast(UUID, route_request.composition_id)

    fake = SimpleNamespace(
        pane=SimpleNamespace(
            composeScene=compose_scene,
            setControlMode=lambda mode: control_modes.append(mode),
        ),
        activeOutputChanged=SignalStub(),
        activeOutputGridChanged=SignalStub(),
        active_source_key=None,
        active_scene_key="portrait",
        active_scene_overview=True,
        active_set_index=1,
        last_real_set_index=1,
        set_count=0,
        scene_count=2,
        source_groups={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(text_source, upscale_source),
                representative_source_key="wf:upscale",
                representative_set_index=1,
            )
        },
        images_by_id={
            image_id: ImageStub(512, 768) for image_id in (*text_ids, *upscale_ids)
        },
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
        scene_selector_button=scene_selector,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )
    fake._activate_grid_for_source = lambda source_key, **kwargs: (
        activate_output_grid_for_source(
            fake,
            source_key,
            source_groups_by_key=output_mod.visible_output_source_groups_by_key(
                output_mod.output_route_state_snapshot(fake)
            ),
            update_tabbar_container=fake._update_tabbar_container,
            **kwargs,
        )
    )
    fake._compose_grid_scene_for_source = lambda source, *, activate: (
        route_application_controller(
            output_mod,
            fake,
        ).present_source_grid(source, activate=activate)
    )
    attach_output_grid_layout_helpers(fake)
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    projection = output_mod.OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=2,
        scene_groups=tuple(fake.scene_groups.values()),
        active_scene_key="portrait",
        active_scene_overview=True,
        scene_count=2,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )

    assert (
        activate_output_scene(
            fake,
            "portrait",
            scene_groups_by_key=output_mod.output_scene_groups_by_key(
                output_mod.output_route_state_snapshot(fake)
            ),
            update_tabbar_container=fake._update_tabbar_container,
        )
        is not None
    )

    assert fake.active_source_key == "wf:upscale"
    assert fake.active_set_index == 0
    assert compose_calls == []
    assert control_modes == [output_mod.QPane.CONTROL_MODE_CURSOR]


def test_output_canvas_scene_overview_resets_composition_when_signature_changes(
    monkeypatch: Any,
) -> None:
    """Changed scene overview topology should compose a fresh QPane scene."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    previous_scene_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    route_projector = RecordingOutputRouteProjector()
    removed: list[object] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            removeComposition=lambda composition_id: removed.append(composition_id),
        ),
        _route_projector=route_projector,
        scene_overview_scene_id=previous_scene_id,
        scene_overview_signature=(("portrait", "run-1", first_id, False), 1, 1),
        scene_grid_layer_ids_by_key={},
        images_by_id={
            first_id: ImageStub(512, 768),
            second_id: ImageStub(512, 768),
        },
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=first_id,
            ),
            "cafe": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="cafe",
                title="Cafe",
                order=1,
                sources=(),
                primary_image_id=second_id,
            ),
        },
    )
    attach_scene_overview_compose_helpers(fake, output_mod)

    route_application_controller(output_mod, fake).present_scene_overview(activate=True)

    request, activate = route_projector.scene_overview_calls[0]
    scene_request = cast(Any, request)
    assert activate is True
    assert isinstance(scene_request.composition_id, UUID)
    assert removed == []
    assert [layer.metadata["scene_key"] for layer in scene_request.layers] == [
        "portrait",
        "cafe",
    ]
    assert [layer.image_id for layer in scene_request.layers] == [first_id, second_id]


def test_output_canvas_scene_overview_replaces_composition_when_signature_matches(
    monkeypatch: Any,
) -> None:
    """Unchanged scene overview content should replace the deterministic scene."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    image_id = uuid4()
    route_projector = RecordingOutputRouteProjector()
    opened: list[object] = []
    removed: list[object] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            openComposition=lambda composition_id: opened.append(composition_id),
            removeComposition=lambda composition_id: removed.append(composition_id),
        ),
        _route_projector=route_projector,
        scene_overview_scene_id=None,
        scene_grid_layer_ids_by_key={},
        images_by_id={image_id: ImageStub(512, 768)},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        scene_groups={
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(),
                primary_image_id=image_id,
            ),
        },
    )
    attach_scene_overview_compose_helpers(fake, output_mod)

    route_application_controller(output_mod, fake).present_scene_overview(activate=True)
    route_application_controller(output_mod, fake).present_scene_overview(activate=True)

    first_request, _first_activate = route_projector.scene_overview_calls[0]
    first_scene_request = cast(Any, first_request)
    assert isinstance(first_scene_request.composition_id, UUID)
    second_request, _second_activate = route_projector.scene_overview_calls[1]
    second_scene_request = cast(Any, second_request)
    assert len(route_projector.scene_overview_calls) == 2
    assert second_scene_request.composition_id == first_scene_request.composition_id
    assert opened == []
    assert removed == []


def test_output_canvas_scene_overview_resets_when_representative_changes(
    monkeypatch: Any,
) -> None:
    """Scene representative changes should compose a fresh overview scene."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    scene_one_id = uuid4()
    text_id = uuid4()
    upscale_id = uuid4()
    route_projector = RecordingOutputRouteProjector()
    removed: list[object] = []
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            removeComposition=lambda composition_id: removed.append(composition_id),
        ),
        _route_projector=route_projector,
        scene_overview_scene_id=None,
        scene_grid_layer_ids_by_key={},
        images_by_id={
            scene_one_id: ImageStub(512, 768),
            text_id: ImageStub(512, 768),
            upscale_id: ImageStub(512, 768),
        },
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        scene_groups={
            "scene1": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="scene1",
                title="Scene 1",
                order=0,
                sources=(),
                primary_image_id=scene_one_id,
                representative_source_key="wf:upscale",
                representative_set_index=1,
            ),
            "scene2": OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="scene2",
                title="Scene 2",
                order=1,
                sources=(),
                primary_image_id=text_id,
                representative_source_key="wf:text",
                representative_set_index=1,
            ),
        },
    )
    attach_scene_overview_compose_helpers(fake, output_mod)

    route_application_controller(output_mod, fake).present_scene_overview(activate=True)
    fake.scene_groups["scene2"] = OutputCanvasSceneGroup(
        scene_run_id="run-1",
        scene_key="scene2",
        title="Scene 2",
        order=1,
        sources=(),
        primary_image_id=upscale_id,
        representative_source_key="wf:upscale",
        representative_set_index=1,
    )
    attach_scene_overview_compose_helpers(fake, output_mod)
    route_application_controller(output_mod, fake).present_scene_overview(activate=True)

    second_request, _activate = route_projector.scene_overview_calls[1]
    second_scene_request = cast(Any, second_request)
    scene_two_layer = second_scene_request.layers[1]
    assert isinstance(second_scene_request.composition_id, UUID)
    assert scene_two_layer.image_id == upscale_id
    assert scene_two_layer.metadata["image_id"] == str(upscale_id)
    assert scene_two_layer.metadata["representative_source_key"] == "wf:upscale"
    assert removed == []


def _tabbar(
    *,
    removed: list[str] | None = None,
    items: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Return a minimal source-tab bar double for scene-overview tests."""

    removed_log = removed if removed is not None else []
    item_map = {} if items is None else dict(items)
    state = SimpleNamespace(current=None)

    def _remove_widget(key: str) -> None:
        item_map.pop(key, None)
        removed_log.append(key)

    def _add_item(key: str, label: str) -> None:
        item_map[key] = label

    return SimpleNamespace(
        items=item_map,
        currentItemChanged=SignalStub(),
        removeWidget=_remove_widget,
        addItem=_add_item,
        adjustSize=lambda: None,
        setCurrentItem=lambda key: setattr(state, "current", key),
        state=state,
    )


def _image_meta(*, source_key: str, set_index: int) -> ImageMeta:
    """Return typed image metadata for scene-overview navigation tests."""

    return ImageMeta(
        workflow_name="wf",
        cube_name="Cube",
        image_number=set_index,
        suffix="",
        path="",
        source_key=source_key,
    )


def _selector_button() -> SimpleNamespace:
    """Return a minimal set-selector button double."""

    state: dict[str, object] = {}
    return SimpleNamespace(
        state=state,
        setText=lambda text: state.__setitem__("text", text),
        setVisible=lambda visible: state.__setitem__("visible", visible),
    )


def _scene_selector_button() -> SimpleNamespace:
    """Return a minimal scene-selector button double."""

    state: dict[str, object] = {}
    return SimpleNamespace(
        state=state,
        setText=lambda text: state.__setitem__("text", text),
        setVisible=lambda visible: state.__setitem__("visible", visible),
        setFixedWidth=lambda width: state.__setitem__("width", width),
        setToolTip=lambda tooltip: state.__setitem__("tooltip", tooltip),
        fontMetrics=lambda: SimpleNamespace(horizontalAdvance=lambda text: len(text)),
    )
