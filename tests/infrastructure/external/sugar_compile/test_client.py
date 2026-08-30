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

"""Verify backend-owned Sugar workflow compilation requests and errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.substitute_backend_sugar_compile_client import (
    BackendSugarCompileError,
    SubstituteBackendSugarCompileClient,
)
from tests.infrastructure.external.sugar_compile.support import (
    FakeResponse,
    RecordingTransport,
)


def _client(transport: RecordingTransport) -> SubstituteBackendSugarCompileClient:
    """Build a client using the recording transport."""
    return SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )


def test_backend_sugar_compile_client_posts_expected_request_body() -> None:
    """Send the public compile request contract."""
    transport = RecordingTransport()
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=transport.get,
        http_post=transport.post,
        timeout_seconds=12.0,
    )
    output_dir = Path("outputs")

    payload = client.compile_workflow_payload(
        sugar_script_text='use "Owner/Repo/demo.cube" as demo',
        output_dir=output_dir,
    )

    assert payload == {
        "prompt": {"1": {"class_type": "KSampler"}},
        "workflow": {"nodes": []},
    }
    assert transport.get_calls == [
        ("http://10.0.0.2:8189/substitute/v1/capabilities", 3.0)
    ]
    assert transport.post_calls == [
        (
            "http://10.0.0.2:8189/substitute/v1/sugar/compile",
            {
                "schemaVersion": 1,
                "sugarScriptText": 'use "Owner/Repo/demo.cube" as demo',
                "outputDir": str(output_dir),
            },
            12.0,
        )
    ]


def test_backend_sugar_compile_client_maps_backend_errors() -> None:
    """Map a structured backend error to the client error contract."""
    transport = RecordingTransport(
        compile_response=FakeResponse(
            {
                "error": {
                    "code": "sugar-cube-artifact-invalid",
                    "message": "Cube payload is invalid.",
                }
            },
            status_code=502,
        )
    )

    with pytest.raises(BackendSugarCompileError) as error_info:
        _client(transport).compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("outputs"),
        )

    assert str(error_info.value) == "Cube payload is invalid."
    assert error_info.value.status_code == 502
    assert error_info.value.backend_code == "sugar-cube-artifact-invalid"
    assert isinstance(error_info.value.raw_payload, dict)


def test_backend_sugar_compile_client_maps_503_response() -> None:
    """Preserve the backend code for an unavailable compile route."""
    transport = RecordingTransport(
        compile_response=FakeResponse(
            {
                "error": {
                    "code": "sugar-compile-unavailable",
                    "message": "Sugar-DSL is not installed.",
                }
            },
            status_code=503,
        )
    )

    with pytest.raises(BackendSugarCompileError) as error_info:
        _client(transport).compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("outputs"),
        )

    assert str(error_info.value) == "Sugar-DSL is not installed."
    assert error_info.value.status_code == 503
    assert error_info.value.backend_code == "sugar-compile-unavailable"


def test_backend_sugar_compile_client_rejects_unavailable_capability() -> None:
    """Fail before posting when the backend reports Sugar unavailable."""
    transport = RecordingTransport(
        capabilities_response=FakeResponse(
            {
                "features": [],
                "sugarCompile": {
                    "schemaVersion": 1,
                    "available": False,
                    "unavailableReason": "Sugar-DSL is not installed.",
                },
            }
        )
    )

    with pytest.raises(BackendSugarCompileError) as error_info:
        _client(transport).compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("outputs"),
        )

    assert str(error_info.value) == "Sugar-DSL is not installed."
    assert error_info.value.backend_code == "sugar-compile-unavailable"
    assert transport.post_calls == []


def test_backend_sugar_compile_client_rejects_invalid_response_shape() -> None:
    """Require wrapped prompt and workflow artifacts."""
    transport = RecordingTransport(compile_response=FakeResponse({"prompt": {}}))

    with pytest.raises(BackendSugarCompileError, match="prompt/workflow"):
        _client(transport).compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("outputs"),
        )
