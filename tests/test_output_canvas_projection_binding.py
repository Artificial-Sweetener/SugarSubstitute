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

"""Verify narrow Output projection and navigation integration seams."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_grid_for_source,
    activate_output_item,
    select_output_set,
    select_output_source,
    sync_output_set_selector_button,
)
from tests.canvas_widget_import_helpers import import_canvas_modules
from tests.support.output_canvas.grid_fakes import (
    attach_output_grid_layout_helpers,
    install_fake_output_grid_event_controller,
    install_fake_output_interaction_controller,
    route_application_controller,
)
from tests.support.output_canvas.host_fakes import (
    SignalStub,
    bind_fake_output_projection,
)
from tests.support.output_canvas.models import ImageStub
from tests.support.output_canvas.projection_binding_fakes import (
    _meta,
    _selector,
)


def test_output_canvas_plain_pane_event_does_not_mutate_qpane_presenter(
    monkeypatch: Any,
) -> None:
    """Plain QPane-owned interaction should not trigger Sugar display mutations."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)

    class _PresenterProbe:
        """Fail the test if OutputCanvas tries to mutate QPane display state."""

        def __getattr__(self, name: str) -> object:
            """Raise on any unexpected presenter method access."""

            raise AssertionError(f"unexpected presenter call: {name}")

    pane = object()
    fake = SimpleNamespace(
        pane=pane,
        active_scene_overview=False,
        active_set_index=1,
        _qpane_presenter=_PresenterProbe(),
    )
    install_fake_output_grid_event_controller(output_mod, fake)

    assert fake._grid_event_controller.handle_event_filter(pane, object()) is False


def test_output_canvas_on_tab_changed_resolves_source_set_and_emits_uuid(
    monkeypatch: Any,
) -> None:
    """Source route keys should update pane selection and emit active UUID."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    target = uuid4()
    pane_calls: list[object] = []
    control_modes: list[str] = []
    selected_tabs: list[str] = []
    emit_signal = SignalStub()
    pane = SimpleNamespace(
        setCurrentImageID=lambda image_id: pane_calls.append(image_id),
        setControlMode=lambda mode: control_modes.append(mode),
    )
    tabbar = SimpleNamespace(
        items={"source-a": object(), "source-b": object()},
        setCurrentItem=selected_tabs.append,
    )
    selector = SimpleNamespace(
        setText=lambda _text: None, setVisible=lambda _visible: None
    )
    fake = SimpleNamespace(
        pane=pane,
        activeOutputChanged=emit_signal,
        active_set_index=2,
        active_source_key=None,
        _suppress_tab_change=False,
        tabbar=tabbar,
        set_selector_button=selector,
        set_count=2,
        source_groups={
            "source-a": OutputCanvasSourceGroup(
                source_key="source-a",
                label="Source A",
                images_by_set={
                    2: OutputCanvasImageItem(
                        target,
                        _meta(source_key="source-a", source_label="Source A"),
                        2,
                    )
                },
            ),
            "source-b": OutputCanvasSourceGroup(
                source_key="source-b",
                label="Source B",
                images_by_set={
                    1: OutputCanvasImageItem(
                        uuid4(),
                        _meta(source_key="source-b", source_label="Source B"),
                        1,
                    )
                },
            ),
        },
    )
    fake._on_tab_changed = lambda _route: None
    projection = output_mod.OutputCanvasProjection(
        sources=tuple(fake.source_groups.values()),
        active_source_key="source-a",
        active_set_index=2,
        active_uuid=target,
        set_count=2,
    )
    bind_fake_output_projection(output_mod, fake, projection)
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

    select_output_source(
        fake,
        "source-a",
        source_groups_by_key=fake.source_groups,
        update_tabbar_container=fake._update_tabbar_container,
    )
    select_output_source(
        fake,
        "source-b",
        source_groups_by_key=fake.source_groups,
        update_tabbar_container=fake._update_tabbar_container,
    )

    assert pane_calls == []
    assert control_modes == [output_mod.QPane.CONTROL_MODE_PANZOOM]
    assert emit_signal.calls == [(str(target),)]
    assert fake.active_source_key == "source-a"
    assert fake.active_set_index == 2
    assert selected_tabs == ["source-a", "source-a"]


def test_output_canvas_activate_output_item_skips_unchanged_qpane_image(
    monkeypatch: Any,
) -> None:
    """Manual item activation should not reselect an already active QPane image."""

    _input_mod, _output_mod = import_canvas_modules(monkeypatch)
    target = uuid4()
    pane_calls: list[object] = []
    emit_signal = SignalStub()
    item = OutputCanvasImageItem(
        target,
        _meta(source_key="source-a", source_label=""),
        1,
    )
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={1: item},
    )
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            currentImageID=lambda: target,
            setCurrentImageID=lambda image_id: pane_calls.append(image_id),
            setControlMode=lambda _mode: None,
        ),
        activeOutputChanged=emit_signal,
        active_scene_overview=False,
        active_set_index=1,
        active_source_key=None,
        last_real_set_index=1,
        set_count=1,
        source_groups={"source-a": source},
        tabbar=SimpleNamespace(items={}),
        _on_tab_changed=lambda _route: None,
        _sync_set_selector_button=lambda: None,
    )
    install_fake_output_interaction_controller(fake)

    activate_output_item(
        fake,
        "source-a",
        item,
        update_tabbar_container=lambda: None,
    )

    assert pane_calls == []
    assert emit_signal.calls == [(str(target),)]


def test_output_canvas_on_tab_changed_preserves_grid_mode(monkeypatch: Any) -> None:
    """Source tabs should open the new source grid while grid mode is active."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    id_a = uuid4()
    id_b = uuid4()
    id_c = uuid4()
    compose_calls: list[object] = []
    control_modes: list[str] = []

    def _compose_scene(request: object, activate: bool = True) -> object:
        """Record a grid composition request and return its identity."""

        compose_calls.append((request, activate))
        return cast(Any, request).composition_id

    pane = SimpleNamespace(
        composeScene=_compose_scene,
        setCurrentImageID=lambda _image_id: None,
        setControlMode=lambda mode: control_modes.append(mode),
    )
    tabbar = SimpleNamespace(
        items={"source-a": object(), "source-b": object()},
        setCurrentItem=lambda _key: None,
    )
    selector = _selector()
    fake = SimpleNamespace(
        pane=pane,
        activeOutputChanged=SignalStub(),
        activeOutputGridChanged=SignalStub(),
        active_source_key="source-a",
        active_set_index=0,
        last_real_set_index=1,
        source_groups={
            "source-a": OutputCanvasSourceGroup(
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
            ),
            "source-b": OutputCanvasSourceGroup(
                source_key="source-b",
                label="Source B",
                images_by_set={
                    1: OutputCanvasImageItem(
                        id_c,
                        _meta(source_key="source-b", source_label="Source B"),
                        1,
                    ),
                    2: OutputCanvasImageItem(
                        uuid4(),
                        _meta(source_key="source-b", source_label="Source B"),
                        2,
                    ),
                },
            ),
        },
        images_by_id={
            id_a: ImageStub(512, 768),
            id_b: ImageStub(512, 768),
            id_c: ImageStub(512, 768),
        },
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
        set_count=2,
        _update_tabbar_container=lambda: None,
    )
    fake.images_by_id[fake.source_groups["source-b"].images_by_set[2].image_id] = (
        ImageStub(512, 768)
    )
    projection = output_mod.OutputCanvasProjection(
        sources=tuple(fake.source_groups.values()),
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
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

    select_output_source(
        fake,
        "source-b",
        source_groups_by_key=fake.source_groups,
        update_tabbar_container=fake._update_tabbar_container,
    )

    assert fake.active_source_key == "source-b"
    assert fake.active_set_index == 0
    assert compose_calls == []
    assert control_modes == [output_mod.QPane.CONTROL_MODE_CURSOR]
    assert fake.activeOutputChanged.calls == []


def test_output_canvas_set_selection_opens_real_image_and_emits_uuid(
    monkeypatch: Any,
) -> None:
    """Real set selection should leave grid mode and persist a concrete image UUID."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    target = uuid4()
    pane_calls: list[object] = []
    control_modes: list[str] = []
    emit_signal = SignalStub()
    tabbar = SimpleNamespace(
        items={"source-a": object()},
        setCurrentItem=lambda _key: None,
    )
    selector = _selector()
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            setCurrentImageID=lambda image_id: pane_calls.append(image_id),
            setControlMode=lambda mode: control_modes.append(mode),
        ),
        activeOutputChanged=emit_signal,
        active_source_key="source-a",
        active_set_index=0,
        last_real_set_index=1,
        source_groups={
            "source-a": OutputCanvasSourceGroup(
                source_key="source-a",
                label="Source A",
                images_by_set={
                    2: OutputCanvasImageItem(
                        target,
                        _meta(source_key="source-a", source_label="Source A"),
                        2,
                    ),
                },
            )
        },
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
        set_count=2,
        preview_ids_by_source_key={},
    )
    source = next(iter(fake.source_groups.values()))
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )
    bind_fake_output_projection(output_mod, fake, projection)
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

    select_output_set(
        fake,
        2,
        source_groups_by_key=fake.source_groups,
        update_tabbar_container=fake._update_tabbar_container,
    )

    assert fake.active_set_index == 2
    assert fake.last_real_set_index == 2
    assert pane_calls == []
    assert control_modes == [output_mod.QPane.CONTROL_MODE_PANZOOM]
    assert emit_signal.calls == [(str(target),)]


def test_output_canvas_set_zero_composes_grid_without_emitting_uuid(
    monkeypatch: Any,
) -> None:
    """Set zero should open a source grid scene instead of selecting an image."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    id_a = uuid4()
    id_b = uuid4()
    id_c = uuid4()
    id_d = uuid4()
    compose_calls: list[object] = []
    control_modes: list[str] = []

    def _compose_scene(request: object, activate: bool = True) -> object:
        """Record a grid composition request and return its identity."""

        compose_calls.append((request, activate))
        return cast(Any, request).composition_id

    pane = SimpleNamespace(
        composeScene=_compose_scene,
        setCurrentImageID=lambda _image_id: None,
        setControlMode=lambda mode: control_modes.append(mode),
    )
    tabbar = SimpleNamespace(
        items={"source-a": object()},
        setCurrentItem=lambda _key: None,
    )
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
            3: OutputCanvasImageItem(
                id_c,
                _meta(source_key="source-a", source_label="Source A"),
                3,
            ),
            4: OutputCanvasImageItem(
                id_d,
                _meta(source_key="source-a", source_label="Source A"),
                4,
            ),
        },
    )
    fake = SimpleNamespace(
        pane=pane,
        activeOutputChanged=SignalStub(),
        activeOutputGridChanged=SignalStub(),
        active_source_key="source-a",
        active_set_index=1,
        last_real_set_index=1,
        source_groups={"source-a": source},
        images_by_id={
            id_a: ImageStub(512, 768),
            id_b: ImageStub(512, 768),
            id_c: ImageStub(512, 768),
            id_d: ImageStub(512, 768),
        },
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        tabbar=tabbar,
        _suppress_tab_change=False,
        set_selector_button=selector,
        set_count=4,
        _update_tabbar_container=lambda: None,
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=id_a,
        set_count=4,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    fake._compose_grid_scene_for_source = lambda source, *, activate: (
        route_application_controller(
            output_mod,
            fake,
        ).present_source_grid(source, activate=activate)
    )
    attach_output_grid_layout_helpers(fake)
    fake._sync_set_selector_button = lambda: sync_output_set_selector_button(fake)
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

    select_output_set(
        fake,
        0,
        source_groups_by_key=fake.source_groups,
        update_tabbar_container=fake._update_tabbar_container,
    )

    assert fake.active_set_index == 0
    assert selector.text == "0"
    assert compose_calls == []
    assert control_modes == [output_mod.QPane.CONTROL_MODE_CURSOR]
    assert fake.activeOutputChanged.calls == []
    assert fake.activeOutputGridChanged.calls == [("source-a",)]
