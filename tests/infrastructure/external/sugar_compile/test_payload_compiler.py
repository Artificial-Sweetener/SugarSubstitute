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

"""Verify the backend Sugar workflow payload adapter."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.substitute_backend_sugar_compile_client import (
    BackendSugarWorkflowPayloadCompiler,
    SubstituteBackendSugarCompileClient,
)
from tests.infrastructure.external.sugar_compile.support import RecordingTransport


def test_backend_sugar_workflow_payload_compiler_delegates_to_client() -> None:
    """Preserve the workflow payload compiler port contract."""
    transport = RecordingTransport()
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )
    compiler = BackendSugarWorkflowPayloadCompiler(client=client)

    payload = compiler.compile_workflow_payload(
        sugar_script_text="use demo",
        output_dir=Path("outputs"),
    )

    assert payload["prompt"] == {"1": {"class_type": "KSampler"}}
    assert payload["workflow"] == {"nodes": []}
