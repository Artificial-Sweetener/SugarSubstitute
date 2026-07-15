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

"""Verify visible Output projection presentation modes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_grid_for_source,
    sync_output_set_selector_button,
)
from tests.canvas_widget_import_helpers import import_canvas_modules
from tests.support.output_canvas.grid_fakes import (
    attach_output_grid_layout_helpers,
    install_fake_output_interaction_controller,
    route_application_controller,
)
from tests.support.output_canvas.host_fakes import (
    SignalStub,
    bind_fake_output_projection,
    install_fake_output_asset_lookup,
    install_fake_output_projection_chrome,
)
from tests.support.output_canvas.models import ImageStub, session_for_projection
from tests.support.output_canvas.preview_fakes import install_test_preview_lane
from tests.support.output_canvas.projection_fakes import (
    install_fake_output_compare_presenter,
    install_fake_output_source_tabs_controller,
)
from tests.support.output_canvas.projection_binding_fakes import (
    _bind_projection_session,
    _meta,
    _projection_fake,
    _selector,
    _session_for_projection,
    _tabbar,
)


def test_bind_projection_rebuilds_source_tabs_and_active_uuid() -> None:
    """Projection binding should render source tabs and select active image."""

    removed: list[str] = []
    added: list[tuple[str, str]] = []
    current: list[str] = []
    pane_calls: list[object] = []
    presented: list[dict[str, object]] = []
    tabbar = _tabbar(
        removed=removed,
        added=added,
        current=current,
        items={"old": object()},
    )
    selector = _selector()
    fake = _projection_fake(
        tabbar=tabbar,
        set_selector_button=selector,
        pane_calls=pane_calls,
        presented=presented,
    )
    id_a = uuid4()
    id_b = uuid4()
    meta_a = _meta(source_key="source-a", source_label="Cube A")
    meta_b = _meta(source_key="source-b", source_label="Cube B")
    projection = OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source-a",
                label="Cube A",
                images_by_set={
                    1: OutputCanvasImageItem(id_a, meta_a, 1),
                },
            ),
            OutputCanvasSourceGroup(
                source_key="source-b",
                label="Cube B",
                images_by_set={
                    1: OutputCanvasImageItem(id_b, meta_b, 1),
                },
            ),
        ),
        active_source_key="source-b",
        active_set_index=1,
        active_uuid=id_b,
        set_count=1,
    )

    _bind_projection_session(fake, _session_for_projection(projection))

    assert removed == ["old"]
    assert added == [("source-a", "Cube A"), ("source-b", "Cube B")]
    assert current == ["source-b"]
    assert fake._output_projection is projection
    assert pane_calls == [id_b]
    assert selector.visible[-1:] == [False]
    assert presented[-1]["projection"] is projection


def test_bind_projection_skips_current_qpane_image_when_unchanged() -> None:
    """Projection binding should avoid commanding QPane for an unchanged image."""

    pane_calls: list[object] = []
    current_tab: list[str] = []
    target_id = uuid4()
    fake = _projection_fake(
        tabbar=_tabbar(current=current_tab),
        set_selector_button=_selector(),
        pane_current_image=target_id,
        pane_calls=pane_calls,
    )
    projection = OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source-a",
                label="Cube A",
                images_by_set={
                    1: OutputCanvasImageItem(
                        target_id,
                        _meta(source_key="source-a", source_label="Cube A"),
                        1,
                    ),
                },
            ),
        ),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=target_id,
        set_count=1,
    )

    _bind_projection_session(fake, _session_for_projection(projection))

    assert pane_calls == []
    assert current_tab == ["source-a"]
    assert fake.active_source_key == "source-a"


def test_output_canvas_sync_projection_selects_final_before_retiring_preview(
    monkeypatch: Any,
) -> None:
    """Final projection should not remove the live preview before selecting final."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSourceGroup,
    )

    events: list[tuple[str, UUID]] = []
    removed_tabs: list[str] = []
    added_tabs: list[tuple[str, str]] = []
    tab_current: list[str] = []
    preview_id = uuid4()
    final_id = uuid4()
    old_output_id = uuid4()
    tabbar = _tabbar(
        removed=removed_tabs,
        added=added_tabs,
        current=tab_current,
        items={"old": object()},
    )
    selector = _selector()
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[old_output_id],
        metas_by_id={},
        images_by_id={
            old_output_id: ImageStub(512, 768),
            preview_id: ImageStub(512, 768),
            final_id: ImageStub(512, 768),
        },
        preview_ids_by_source_key={"source-b": preview_id},
        preview_ids_by_source_slot={},
        preview_ids_by_scene_slot={},
        scene_preview_slots_by_key={},
        completed_preview_slots=set(),
        pending_final_preview_retire_ids={final_id},
        preview_labels_by_source_key={"source-b": "Cube B"},
        preview_images_by_source_key={"source-b": ImageStub(512, 768)},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        scene_groups={},
        active_source_key="source-b",
        active_set_index=1,
        active_scene_key=None,
        active_scene_overview=False,
        last_real_set_index=1,
        set_count=0,
        pane=SimpleNamespace(
            setCurrentImageID=lambda image_id: events.append(("current", image_id)),
            removeImageByID=lambda image_id: events.append(("remove", image_id)),
            setControlMode=lambda _mode: None,
        ),
        set_selector_button=selector,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    meta = _meta(source_key="source-b", source_label="Cube B")
    projection = output_mod.OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="source-b",
                label="Cube B",
                images_by_set={1: OutputCanvasImageItem(final_id, meta, 1)},
            ),
        ),
        active_source_key="source-b",
        active_set_index=1,
        active_uuid=final_id,
        set_count=1,
    )
    session = session_for_projection(projection)
    install_test_preview_lane(
        output_mod,
        fake,
        preview_id=preview_id,
        image=fake.images_by_id[preview_id],
        source_key="source-b",
        source_label="Cube B",
    )
    install_fake_output_compare_presenter(fake)
    install_fake_output_projection_chrome(fake)

    _bind_projection_session(fake, session)

    current_ids = [image_id for action, image_id in events if action == "current"]
    assert events == [("current", final_id)]
    assert old_output_id not in current_ids
    assert preview_id in fake._asset_lookup.preview_images()
    assert output_mod.output_revision_cache(fake).preview_ids_by_source_key == {
        "source-b": preview_id
    }
    assert (
        output_mod.output_revision_cache(fake).pending_final_preview_retire_ids == set()
    )


def test_output_canvas_sync_projection_activates_projected_grid_without_signal(
    monkeypatch: Any,
) -> None:
    """Projection set zero should activate grid without recording manual selection."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSourceGroup,
    )

    id_a = uuid4()
    id_b = uuid4()
    compose_calls: list[object] = []
    control_modes: list[str] = []

    def _compose_scene(request: object, activate: bool = True) -> object:
        """Record grid composition and return the requested composition id."""

        compose_calls.append((request, activate))
        return cast(Any, request).composition_id

    pane = SimpleNamespace(
        composeScene=_compose_scene,
        setCurrentImageID=lambda _image_id: None,
        setControlMode=lambda mode: control_modes.append(mode),
    )
    tabbar = _tabbar()
    selector = _selector()
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: OutputCanvasImageItem(
                id_a,
                _meta(source_key="source-a", source_label="Source A"),
                1,
            ),
            2: OutputCanvasImageItem(
                id_b,
                _meta(source_key="source-a", source_label="Source A"),
                2,
            ),
        },
    )
    fake = SimpleNamespace(
        pane=pane,
        activeOutputGridChanged=SignalStub(),
        image_ids=[],
        metas_by_id={},
        images_by_id={
            id_a: ImageStub(512, 768),
            id_b: ImageStub(512, 768),
        },
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        active_source_key=None,
        active_set_index=1,
        last_real_set_index=1,
        set_count=0,
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
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
        sources=(source,),
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    install_fake_output_compare_presenter(fake)

    _bind_projection_session(fake, session_for_projection(projection))

    assert fake.active_set_index == 0
    assert compose_calls
    assert control_modes == [output_mod.QPane.CONTROL_MODE_CURSOR]
    assert fake.activeOutputGridChanged.calls == []


def test_output_canvas_sync_projection_keeps_automatic_scene_overview(
    monkeypatch: Any,
) -> None:
    """Automatic multi-scene projections should keep the canvas on All."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSceneGroup,
        OutputCanvasSourceGroup,
    )

    image_id = uuid4()
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: OutputCanvasImageItem(
                image_id,
                _meta(source_key="source-a", source_label="Source A"),
                1,
            )
        },
    )
    activate_overview_calls: list[bool] = []
    activate_grid_calls: list[str | None] = []
    tabbar = _tabbar()
    selector = _selector()
    scene_selector = _selector()
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[],
        metas_by_id={},
        images_by_id={image_id: ImageStub(512, 768)},
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        scene_groups={},
        active_source_key=None,
        active_scene_key=None,
        active_scene_overview=False,
        active_set_index=1,
        last_real_set_index=1,
        set_count=0,
        scene_count=0,
        set_selector_button=selector,
        scene_selector_button=scene_selector,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )
    fake._grid_available_for_current_source = lambda: False
    fake._sync_scene_selector_button = lambda: None

    def _activate_scene_overview() -> bool:
        """Record automatic overview activation attempts."""

        activate_overview_calls.append(True)
        fake.active_scene_overview = True
        return True

    def _activate_grid_for_source(source_key: str | None) -> bool:
        """Record automatic grid activation attempts."""

        activate_grid_calls.append(source_key)
        return True

    fake._activate_scene_overview = _activate_scene_overview
    fake._activate_grid_for_source = _activate_grid_for_source
    install_fake_output_asset_lookup(output_mod, fake)
    install_fake_output_compare_presenter(fake)
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(source,),
                primary_image_id=image_id,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="cafe",
                title="Cafe",
                order=1,
                sources=(),
            ),
        ),
        active_scene_key="portrait",
        active_scene_overview=True,
        scene_count=2,
    )

    _bind_projection_session(fake, session_for_projection(projection))

    assert fake.active_scene_overview is True
    assert activate_overview_calls == []
    assert activate_grid_calls == []


def test_output_canvas_sync_projection_overview_overrides_stale_scene_grid(
    monkeypatch: Any,
) -> None:
    """Automatic All projection should win over stale scene-local grid state."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSceneGroup,
        OutputCanvasSourceGroup,
    )

    scene1_id = uuid4()
    scene2_id = uuid4()
    source_a = OutputCanvasSourceGroup(
        source_key="main:7",
        label="Text to Image",
        images_by_set={
            1: OutputCanvasImageItem(
                scene1_id,
                _meta(source_key="main:7", source_label="Text to Image"),
                1,
            )
        },
    )
    source_b = OutputCanvasSourceGroup(
        source_key="main:30",
        label="Diffusion Upscale",
        images_by_set={
            1: OutputCanvasImageItem(
                scene2_id,
                _meta(source_key="main:30", source_label="Diffusion Upscale"),
                1,
            )
        },
    )
    activate_overview_calls: list[bool] = []
    activate_grid_calls: list[str | None] = []
    tabbar = _tabbar(items={"main:7": object()})
    selector = _selector()
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[],
        metas_by_id={},
        images_by_id={scene1_id: ImageStub(512, 768), scene2_id: ImageStub(512, 768)},
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={"main:7": uuid4()},
        grid_layer_ids_by_key={},
        source_groups={"main:7": source_a},
        scene_groups={},
        active_source_key="main:7",
        active_scene_key="scene1",
        active_scene_overview=False,
        active_set_index=0,
        last_real_set_index=1,
        set_count=3,
        scene_count=2,
        set_selector_button=selector,
        scene_selector_button=selector,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )
    fake._grid_available_for_current_source = lambda: True
    fake._sync_scene_selector_button = lambda: None
    fake._sync_set_selector_button = lambda: None

    def _activate_scene_overview() -> bool:
        """Record automatic overview activation attempts."""

        activate_overview_calls.append(True)
        fake.active_scene_overview = True
        return True

    def _activate_grid_for_source(source_key: str | None) -> bool:
        """Record automatic grid activation attempts."""

        activate_grid_calls.append(source_key)
        return True

    fake._activate_scene_overview = _activate_scene_overview
    fake._activate_grid_for_source = _activate_grid_for_source
    install_fake_output_asset_lookup(output_mod, fake)
    install_fake_output_compare_presenter(fake)
    projection = output_mod.OutputCanvasProjection(
        sources=(source_a, source_b),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=6,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="scene1",
                title="scene1",
                order=0,
                sources=(source_a,),
                primary_image_id=scene1_id,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="scene2",
                title="scene2",
                order=1,
                sources=(source_b,),
                primary_image_id=scene2_id,
            ),
        ),
        active_scene_key="scene2",
        active_scene_overview=True,
        scene_count=2,
    )

    _bind_projection_session(fake, session_for_projection(projection))

    assert fake.active_scene_overview is True
    assert fake.active_scene_key == "scene2"
    assert fake.active_source_key is None
    assert fake.active_set_index == 1
    assert activate_overview_calls == []
    assert activate_grid_calls == []


def test_output_canvas_sync_projection_preserves_selected_scene(
    monkeypatch: Any,
) -> None:
    """A user-selected concrete scene should not be replaced by automatic All."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSceneGroup,
        OutputCanvasSourceGroup,
    )

    image_id = uuid4()
    selected_source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: OutputCanvasImageItem(
                image_id,
                _meta(source_key="source-a", source_label="Source A"),
                1,
            )
        },
    )
    activate_overview_calls: list[bool] = []
    tabbar = _tabbar()
    selector = _selector()
    scene_selector = _selector()
    pane_calls: list[object] = []
    control_modes: list[str] = []
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[],
        metas_by_id={},
        images_by_id={image_id: ImageStub(512, 768)},
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        scene_groups={},
        active_source_key=None,
        active_scene_key="portrait",
        active_scene_overview=False,
        active_set_index=1,
        last_real_set_index=1,
        set_count=0,
        scene_count=2,
        pane=SimpleNamespace(
            setCurrentImageID=lambda value: pane_calls.append(value),
            setControlMode=lambda mode: control_modes.append(mode),
        ),
        set_selector_button=selector,
        scene_selector_button=scene_selector,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )
    fake._grid_available_for_current_source = lambda: False
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    fake._sync_scene_selector_button = lambda: None

    def _activate_scene_overview() -> bool:
        """Record unexpected automatic overview activation attempts."""

        activate_overview_calls.append(True)
        return True

    fake._activate_scene_overview = _activate_scene_overview
    install_fake_output_compare_presenter(fake)
    install_fake_output_interaction_controller(fake)
    install_fake_output_source_tabs_controller(output_mod, fake)
    projection = output_mod.OutputCanvasProjection(
        sources=(selected_source,),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(selected_source,),
                primary_image_id=image_id,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="cafe",
                title="Cafe",
                order=1,
                sources=(),
            ),
        ),
        active_scene_key="portrait",
        active_scene_overview=False,
        scene_count=2,
    )

    _bind_projection_session(fake, session_for_projection(projection))

    assert fake.active_scene_key == "portrait"
    assert fake.active_scene_overview is False
    assert activate_overview_calls == []
    assert pane_calls == [image_id]
    assert control_modes == [output_mod.QPane.CONTROL_MODE_PANZOOM]


def test_output_canvas_sync_projection_unlocks_after_previous_grid_workflow(
    monkeypatch: Any,
) -> None:
    """A concrete projection should not inherit cursor mode from a prior grid."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSourceGroup,
    )

    first_id = uuid4()
    second_id = uuid4()
    pane_calls: list[object] = []
    control_modes: list[str] = []
    activate_grid_calls: list[str | None] = []
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: OutputCanvasImageItem(
                first_id,
                _meta(source_key="source-a", source_label="Source A"),
                1,
            ),
            2: OutputCanvasImageItem(
                second_id,
                _meta(source_key="source-a", source_label="Source A"),
                2,
            ),
        },
    )
    tabbar = _tabbar()
    selector = _selector()
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[],
        metas_by_id={},
        images_by_id={},
        pending_final_preview_retire_ids=set(),
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        active_source_key="previous-source",
        active_scene_key=None,
        active_scene_overview=False,
        active_set_index=0,
        last_real_set_index=1,
        set_count=2,
        scene_count=1,
        pane=SimpleNamespace(
            setCurrentImageID=lambda value: pane_calls.append(value),
            setControlMode=lambda mode: control_modes.append(mode),
        ),
        set_selector_button=selector,
        _suppress_tab_change=False,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )

    def _activate_grid_for_source(source_key: str | None) -> bool:
        """Record unexpected grid activation attempts."""

        activate_grid_calls.append(source_key)
        return True

    fake._activate_grid_for_source = _activate_grid_for_source
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    install_fake_output_compare_presenter(fake)
    install_fake_output_interaction_controller(fake)
    install_fake_output_source_tabs_controller(output_mod, fake)
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=first_id,
        set_count=2,
    )

    _bind_projection_session(fake, session_for_projection(projection))

    assert fake.active_set_index == 1
    assert activate_grid_calls == []
    assert pane_calls == [first_id]
    assert control_modes == [output_mod.QPane.CONTROL_MODE_PANZOOM]


def test_output_canvas_sync_projection_unlocks_after_previous_scene_overview(
    monkeypatch: Any,
) -> None:
    """A concrete scene projection should not inherit All-scenes cursor mode."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSceneGroup,
        OutputCanvasSourceGroup,
    )

    image_id = uuid4()
    pane_calls: list[object] = []
    control_modes: list[str] = []
    activate_overview_calls: list[bool] = []
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: OutputCanvasImageItem(
                image_id,
                _meta(source_key="source-a", source_label="Source A"),
                1,
            )
        },
    )
    tabbar = _tabbar()
    selector = _selector()
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[],
        metas_by_id={},
        images_by_id={},
        pending_final_preview_retire_ids=set(),
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        scene_groups={},
        active_source_key=None,
        active_scene_key=None,
        active_scene_overview=True,
        active_set_index=1,
        last_real_set_index=1,
        set_count=0,
        scene_count=2,
        pane=SimpleNamespace(
            setCurrentImageID=lambda value: pane_calls.append(value),
            setControlMode=lambda mode: control_modes.append(mode),
        ),
        set_selector_button=selector,
        _suppress_tab_change=False,
        _on_tab_changed=lambda _route: None,
        _update_tabbar_container=lambda: None,
    )
    fake._grid_available_for_current_source = lambda: False
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
    fake._sync_scene_selector_button = lambda: None

    def _activate_scene_overview() -> bool:
        """Record unexpected automatic overview activation attempts."""

        activate_overview_calls.append(True)
        return True

    fake._activate_scene_overview = _activate_scene_overview
    install_fake_output_compare_presenter(fake)
    install_fake_output_interaction_controller(fake)
    install_fake_output_source_tabs_controller(output_mod, fake)
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="portrait",
                title="Portrait",
                order=0,
                sources=(source,),
                primary_image_id=image_id,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-1",
                scene_key="cafe",
                title="Cafe",
                order=1,
                sources=(),
            ),
        ),
        active_scene_key="portrait",
        active_scene_overview=False,
        scene_count=2,
    )

    _bind_projection_session(fake, session_for_projection(projection))

    assert fake.active_scene_overview is False
    assert activate_overview_calls == []
    assert pane_calls == [image_id]
    assert control_modes == [output_mod.QPane.CONTROL_MODE_PANZOOM]
