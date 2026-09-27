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

"""Verify the bootstrap's lazy transport preserves native Cube queue options."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from substitute.app.bootstrap.lazy_comfy_gateway import LazyComfyGateway
from substitute.application.ports.comfy_gateway import QueueVisualRunContext
from substitute.domain.onboarding import ComfyEndpoint


def test_lazy_gateway_forwards_native_execution_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installed composition must preserve the selected Cube stage target."""

    gateway = LazyComfyGateway(ComfyEndpoint(host="127.0.0.1", port=8188))
    concrete_gateway = Mock()
    monkeypatch.setattr(gateway, "_resolve", lambda: concrete_gateway)
    context = QueueVisualRunContext(
        workflow_id="wf", generation_run_id="run", client_id="client"
    )
    workflow: dict[str, object] = {"nodes": []}

    gateway.queue_cube_workflow(
        workflow,
        client_id="client",
        visual_context=context,
        execution_targets=("image-instance",),
    )

    concrete_gateway.queue_cube_workflow.assert_called_once_with(
        workflow,
        client_id="client",
        preview_method=None,
        visual_context=context,
        persistence_sugar_script=None,
        execution_targets=("image-instance",),
    )
