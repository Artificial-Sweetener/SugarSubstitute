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

"""Verify Output projection route and session binding."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from substitute.domain.workflow import (
    CanvasRouteIdentity,
)
from tests.canvas_widget_import_helpers import import_canvas_modules
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from tests.support.output_canvas.projection_controller_factory import (
    output_canvas_projection_controller_for_test_host,
)
from tests.support.output_canvas.host_fakes import (
    install_fake_output_projection_chrome,
)
from tests.support.output_canvas.projection_binding_fakes import (
    _meta,
)


def test_output_canvas_route_binding_does_not_widen_foreign_source_scope(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    """Output route binding must not add requested foreign source keys to scope."""

    _input_mod, output_mod = import_canvas_modules(monkeypatch)
    from substitute.application.workflows import (  # noqa: PLC0415
        OutputCanvasImageItem,
        OutputCanvasSourceGroup,
        bind_output_canvas_session,
    )
    from substitute.presentation.canvas.qpane.canvas_route_projector import (  # noqa: PLC0415
        OutputRouteProjector,
    )
    from substitute.presentation.canvas.qpane.output_pane_adapter import (  # noqa: PLC0415
        OutputQPaneRouteAdapter,
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
            ),
            2: OutputCanvasImageItem(
                uuid4(),
                _meta(source_key="source-a", source_label="Source A"),
                2,
            ),
        },
    )
    projection = output_mod.OutputCanvasProjection(
        sources=(source,),
        active_source_key="source-a",
        active_set_index=0,
        active_uuid=None,
        set_count=2,
    )
    boundary = create_canvas_session_boundary()
    session = bind_output_canvas_session(
        boundary,
        workflow_id="wf",
        projection=projection,
        image_metadata_lookup={image_id: source.images_by_set[1].image_meta},
    )
    pane = SimpleNamespace(
        currentImageID=lambda: None,
        currentCompositionID=lambda: None,
        getCompositionSnapshot=lambda: None,
        clearComparisonImage=lambda: None,
        setCurrentImageID=lambda _image_id: None,
        composeScene=lambda _request, activate=True: uuid4(),
    )
    fake = SimpleNamespace(
        pane=pane,
        _route_session_boundary=boundary,
        _route_projector=OutputRouteProjector(
            OutputQPaneRouteAdapter(pane),
            session_boundary=boundary,
        ),
        _projection_workflow_id="wf",
        _output_projection=projection,
        _output_session=session,
    )
    install_fake_output_projection_chrome(fake)
    foreign_route = CanvasRouteIdentity(
        route_kind="source_grid",
        route_key="scene:;source:foreign;set:0",
    )
    request = SimpleNamespace(
        composition_id=None,
        title="Grid",
        layers=(SimpleNamespace(image_id=image_id),),
    )

    output_canvas_projection_controller_for_test_host(fake).bind_output_route_projector(
        foreign_route
    )
    with caplog.at_level(logging.WARNING):
        accepted = fake._route_projector.apply_source_grid_route(
            foreign_route,
            request,
            activate=True,
        )

    assert accepted is False
    assert "rejection_reason=foreign_source_route" in caplog.text
