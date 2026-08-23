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

"""Test generation interruption gateway behavior."""

from __future__ import annotations

from __future__ import annotations
from substitute.application.ports import (
    InterruptResult,
)

from tests.application.generation.generation_service.support import (
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _FakeGateway,
    _build_generation_service,
)


def test_interrupt_generation_returns_gateway_result() -> None:
    """Interrupt call should delegate to gateway and return typed result."""
    interrupt_result = InterruptResult(
        status="failed",
        status_code=500,
        error="HTTP 500",
    )
    fake_gateway = _FakeGateway(
        queue_results=[],
        interrupt_result=interrupt_result,
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.interrupt_generation()

    assert result == interrupt_result
