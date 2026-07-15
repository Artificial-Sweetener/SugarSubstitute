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

"""Verify OutputCanvas grid composition widget integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4
from PySide6.QtCore import QEvent

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from tests.canvas_widget_import_helpers import import_canvas_modules
from tests.support.output_canvas.assertions import assert_stable_layer_identity
from tests.support.output_canvas.grid_fakes import (
    attach_output_grid_layout_helpers,
    build_output_grid_click_fake,
    grid_mouse_event,
    route_application_controller,
)
from tests.support.output_canvas.host_fakes import bind_fake_output_projection
from tests.support.output_canvas.models import ImageStub
from tests.support.output_canvas.route_fakes import RecordingOutputRouteProjector


def test_output_canvas_composed_hires_grid_uses_image_relative_gutter(
    monkeypatch: Any,
) -> None:
    """Composed large-image grid scenes should use proportional tile spacing."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    first_id = uuid4()
    second_id = uuid4()
    route_projector = RecordingOutputRouteProjector()
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
    fake = SimpleNamespace(
        pane=SimpleNamespace(),
        _route_projector=route_projector,
        images_by_id={
            first_id: ImageStub(2048, 2048),
            second_id: ImageStub(2048, 2048),
        },
        source_groups={"source-a": source},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
    )
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
    attach_output_grid_layout_helpers(fake)

    route_application_controller(output_mod, fake).present_source_grid(
        source,
        activate=True,
    )

    request, activate = route_projector.source_grid_calls[0]
    scene_request = cast(Any, request)
    assert activate is True
    expected_gutter = 4096.0 / 511.0
    assert scene_request.bounds.width() == 2048.0
    assert scene_request.bounds.height() == 4096.0 + expected_gutter
    placement_y = scene_request.layers[1].placement.y
    assert (placement_y() if callable(placement_y) else placement_y) == (
        2048.0 + expected_gutter
    )


def test_output_canvas_source_grid_replaces_unchanged_composition(
    monkeypatch: Any,
) -> None:
    """Unchanged source grids should replace the deterministic QPane composition."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    first_id = uuid4()
    second_id = uuid4()
    route_projector = RecordingOutputRouteProjector()
    opened: list[object] = []
    source = OutputCanvasSourceGroup(
        source_key="wf:upscale",
        label="Upscale",
        images_by_set={
            1: OutputCanvasImageItem(
                first_id,
                _meta(source_key="wf:upscale", source_label="Upscale"),
                1,
            ),
            2: OutputCanvasImageItem(
                second_id,
                _meta(source_key="wf:upscale", source_label="Upscale"),
                2,
            ),
        },
    )
    fake = SimpleNamespace(
        pane=SimpleNamespace(
            openComposition=lambda composition_id: opened.append(composition_id),
        ),
        _route_projector=route_projector,
        images_by_id={first_id: ImageStub(512, 768), second_id: ImageStub(512, 768)},
        source_groups={"wf:upscale": source},
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_scene_signatures_by_source_key={},
        grid_layer_ids_by_key={},
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="wf:upscale",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )
    bind_fake_output_projection(
        output_mod, fake, projection, payloads=fake.images_by_id
    )
    attach_output_grid_layout_helpers(fake)

    route_application_controller(output_mod, fake).present_source_grid(
        source,
        activate=True,
    )
    route_application_controller(output_mod, fake).present_source_grid(
        source,
        activate=True,
    )

    assert len(route_projector.source_grid_calls) == 2
    first_request = cast(Any, route_projector.source_grid_calls[0][0])
    second_request = cast(Any, route_projector.source_grid_calls[1][0])
    assert second_request.composition_id == first_request.composition_id
    assert_stable_layer_identity(first_request, second_request)
    assert opened == []


def test_output_canvas_grid_tile_click_opens_matching_batch_member(
    monkeypatch: Any,
) -> None:
    """Grid tile clicks should open the matching concrete output set."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    hit = SimpleNamespace(
        role="final-output",
        metadata={"source_key": "source-a", "set_index": 2},
        image_id=None,
    )
    fake, target_id, pane_calls, control_modes, hit_calls = (
        build_output_grid_click_fake(output_mod, hit)
    )
    hit.image_id = target_id

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
    assert fake.active_set_index == 2
    assert fake.last_real_set_index == 2
    assert pane_calls == []
    assert control_modes == [output_mod.QPane.CONTROL_MODE_PANZOOM]
    assert fake.activeOutputChanged.calls == [(str(target_id),)]
    assert fake.activeOutputGridChanged.calls == []


def test_output_canvas_grid_background_click_does_nothing(monkeypatch: Any) -> None:
    """Grid clicks without a scene hit should leave selection untouched."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    fake, _target_id, pane_calls, control_modes, hit_calls = (
        build_output_grid_click_fake(output_mod, None)
    )
    press = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonPress,
        10,
        10,
    )
    release = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonRelease,
        10,
        10,
    )

    fake._grid_event_controller.handle_event_filter(fake.pane, press)
    fake._grid_event_controller.handle_event_filter(fake.pane, release)

    assert hit_calls
    assert fake.active_set_index == 0
    assert pane_calls == []
    assert control_modes == []
    assert fake.activeOutputChanged.calls == []


def _meta(*, source_key: str, source_label: str) -> ImageMeta:
    """Return minimal output metadata for grid composition tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name=source_label,
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label=source_label,
    )


def test_output_canvas_grid_ignores_non_final_scene_hit(monkeypatch: Any) -> None:
    """Grid clicks on non-output scene layers should not activate an image."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    hit = SimpleNamespace(
        role="overlay",
        metadata={"source_key": "source-a", "set_index": 2},
        image_id=uuid4(),
    )
    fake, _target_id, pane_calls, control_modes, hit_calls = (
        build_output_grid_click_fake(output_mod, hit)
    )
    press = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonPress,
        10,
        10,
    )
    release = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonRelease,
        10,
        10,
    )

    fake._grid_event_controller.handle_event_filter(fake.pane, press)
    fake._grid_event_controller.handle_event_filter(fake.pane, release)

    assert hit_calls
    assert fake.active_set_index == 0
    assert pane_calls == []
    assert control_modes == []
    assert fake.activeOutputChanged.calls == []


def test_output_canvas_grid_drag_does_not_activate_tile(monkeypatch: Any) -> None:
    """Grid press/release movement beyond drag distance should not hit-test."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    hit = SimpleNamespace(
        role="final-output",
        metadata={"source_key": "source-a", "set_index": 2},
        image_id=uuid4(),
    )
    fake, _target_id, pane_calls, control_modes, hit_calls = (
        build_output_grid_click_fake(output_mod, hit)
    )
    press = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonPress,
        0,
        0,
    )
    release = grid_mouse_event(
        output_mod,
        QEvent.Type.MouseButtonRelease,
        20,
        0,
    )

    fake._grid_event_controller.handle_event_filter(fake.pane, press)
    fake._grid_event_controller.handle_event_filter(fake.pane, release)

    assert hit_calls == []
    assert fake.active_set_index == 0
    assert pane_calls == []
    assert control_modes == []
    assert fake.activeOutputChanged.calls == []
