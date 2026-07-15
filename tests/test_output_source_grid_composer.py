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

"""Contract tests for Output source-grid scene request composition."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
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


def test_output_grid_composer_returns_source_grid_scene_request() -> None:
    """Source-grid composition should produce route metadata without QPane calls."""

    first_id = uuid4()
    second_id = uuid4()
    payloads = {
        first_id: _Image(512, 768),
        second_id: _Image(512, 768),
    }
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            1: _item(first_id, 1),
            2: _item(second_id, 2),
        },
    )

    route_request = _composer(payloads.get).compose_source_grid(
        source,
        scene_key="scene-a",
    )

    assert route_request is not None
    request = cast(Any, route_request.request)
    assert route_request.route.route_kind == "source_grid"
    assert route_request.route.route_key == "scene:scene-a;source:source-a;set:0"
    assert request.title == "Source A grid"
    assert len(request.layers) == 2
    assert [layer.metadata["set_index"] for layer in request.layers] == [
        1,
        2,
    ]
    assert {layer.metadata["source_key"] for layer in request.layers} == {"source-a"}
    assert all(isinstance(layer.layer_id, UUID) for layer in request.layers)


def test_output_grid_composer_reuses_deterministic_layer_ids() -> None:
    """Recomposing one source route should preserve ordered layer identities."""

    first_id = uuid4()
    second_id = uuid4()
    payloads = {
        first_id: _Image(512, 768),
        second_id: _Image(512, 768),
    }
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={
            2: _item(second_id, 2),
            1: _item(first_id, 1),
        },
    )
    composer = _composer(payloads.get)

    first = composer.compose_source_grid(source, scene_key="scene-a")
    second = composer.compose_source_grid(source, scene_key="scene-a")

    assert first is not None
    assert second is not None
    first_request = cast(Any, first.request)
    second_request = cast(Any, second.request)
    assert [layer.metadata["set_index"] for layer in first_request.layers] == [1, 2]
    assert [layer.layer_id for layer in second_request.layers] == [
        layer.layer_id for layer in first_request.layers
    ]


def _item(image_id: UUID, set_index: int) -> OutputCanvasImageItem:
    """Return one source-grid projection item."""

    return OutputCanvasImageItem(
        image_id=image_id,
        image_meta=ImageMeta("wf", "Source A", set_index, "", "E:/out.png"),
        set_index=set_index,
    )


def _composer(payload_lookup: Any) -> OutputSourceGridComposer:
    """Return a source composer with deterministic responsive collaborators."""

    return OutputSourceGridComposer(
        payload_lookup,
        scene_builder=OutputGridSceneBuilder(),
        viewport_extent=lambda: CanvasViewportExtent(1000.0, 1000.0),
    )
