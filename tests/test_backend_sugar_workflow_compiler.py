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

"""Tests for backend-owned Sugar workflow compilation clients."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.substitute_backend_sugar_compile_client import (
    BackendSugarCompileError,
    BackendSugarWorkflowPayloadCompiler,
    SubstituteBackendSugarCompileClient,
)


class _FakeResponse:
    """Small requests response test double."""

    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
    ) -> None:
        """Store response payload and status."""

        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        """Return the configured payload."""

        return self._payload

    def raise_for_status(self) -> None:
        """Raise a requests error for non-success responses."""

        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _RecordingTransport:
    """Record backend HTTP requests and return configured responses."""

    def __init__(
        self,
        *,
        compile_response: _FakeResponse | None = None,
        capabilities_response: _FakeResponse | None = None,
    ) -> None:
        """Configure fake response payloads."""

        self.get_calls: list[tuple[str, float]] = []
        self.post_calls: list[tuple[str, dict[str, object], float]] = []
        self._compile_response = compile_response or _FakeResponse(
            {"prompt": {"1": {"class_type": "KSampler"}}, "workflow": {"nodes": []}}
        )
        self._capabilities_response = capabilities_response or _FakeResponse(
            {
                "features": ["sugar-compile"],
                "sugarCompile": {
                    "schemaVersion": 1,
                    "available": True,
                    "compileRoute": "/substitute/v1/sugar/compile",
                    "liveNodeDefinitions": True,
                },
            }
        )

    def get(self, url: str, *, timeout: float) -> _FakeResponse:
        """Record a GET request."""

        self.get_calls.append((url, timeout))
        return self._capabilities_response

    def post(
        self, url: str, *, json: dict[str, object], timeout: float
    ) -> _FakeResponse:
        """Record a POST request."""

        self.post_calls.append((url, json, timeout))
        return self._compile_response


def test_endpoint_builds_sugar_compile_url() -> None:
    """Comfy endpoints should expose the Substitute BackEnd compile route."""

    endpoint = ComfyEndpoint(host="10.0.0.2", port=8189)

    assert (
        endpoint.substitute_sugar_compile_url()
        == "http://10.0.0.2:8189/substitute/v1/sugar/compile"
    )


def test_backend_sugar_compile_client_posts_expected_request_body() -> None:
    """Backend compile client should send the public compile request contract."""

    transport = _RecordingTransport()
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="10.0.0.2", port=8189),
        http_get=transport.get,
        http_post=transport.post,
        timeout_seconds=12.0,
    )

    payload = client.compile_workflow_payload(
        sugar_script_text='use "Owner/Repo/demo.cube" as demo',
        output_dir=Path("E:/outputs"),
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
                "outputDir": "E:\\outputs",
            },
            12.0,
        )
    ]


def test_backend_sugar_workflow_payload_compiler_delegates_to_client() -> None:
    """WorkflowPayloadCompiler adapter should preserve the existing port shape."""

    transport = _RecordingTransport()
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )
    compiler = BackendSugarWorkflowPayloadCompiler(client=client)

    payload = compiler.compile_workflow_payload(
        sugar_script_text="use demo",
        output_dir=Path("E:/outputs"),
    )

    assert payload["prompt"] == {"1": {"class_type": "KSampler"}}
    assert payload["workflow"] == {"nodes": []}


def test_backend_sugar_compile_client_maps_backend_errors() -> None:
    """Structured backend errors should become BackendSugarCompileError."""

    transport = _RecordingTransport(
        compile_response=_FakeResponse(
            {
                "error": {
                    "code": "sugar-cube-artifact-invalid",
                    "message": "Cube payload is invalid.",
                }
            },
            status_code=502,
        )
    )
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )

    with pytest.raises(BackendSugarCompileError) as error_info:
        client.compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("E:/outputs"),
        )

    assert str(error_info.value) == "Cube payload is invalid."
    assert error_info.value.status_code == 502
    assert error_info.value.backend_code == "sugar-cube-artifact-invalid"
    assert isinstance(error_info.value.raw_payload, dict)


def test_backend_sugar_compile_client_maps_503_response() -> None:
    """Unavailable compile routes should preserve the backend error code."""

    transport = _RecordingTransport(
        compile_response=_FakeResponse(
            {
                "error": {
                    "code": "sugar-compile-unavailable",
                    "message": "Sugar-DSL is not installed.",
                }
            },
            status_code=503,
        )
    )
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )

    with pytest.raises(BackendSugarCompileError) as error_info:
        client.compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("E:/outputs"),
        )

    assert str(error_info.value) == "Sugar-DSL is not installed."
    assert error_info.value.status_code == 503
    assert error_info.value.backend_code == "sugar-compile-unavailable"


def test_backend_sugar_compile_client_rejects_unavailable_capability() -> None:
    """Client should fail before posting when backend reports unavailable Sugar."""

    transport = _RecordingTransport(
        capabilities_response=_FakeResponse(
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
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )

    with pytest.raises(BackendSugarCompileError) as error_info:
        client.compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("E:/outputs"),
        )

    assert str(error_info.value) == "Sugar-DSL is not installed."
    assert error_info.value.backend_code == "sugar-compile-unavailable"
    assert transport.post_calls == []


def test_backend_sugar_compile_client_rejects_invalid_response_shape() -> None:
    """Compile responses must include wrapped prompt/workflow artifacts."""

    transport = _RecordingTransport(compile_response=_FakeResponse({"prompt": {}}))
    client = SubstituteBackendSugarCompileClient(
        ComfyEndpoint(host="127.0.0.1", port=8188),
        http_get=transport.get,
        http_post=transport.post,
    )

    with pytest.raises(BackendSugarCompileError, match="prompt/workflow"):
        client.compile_workflow_payload(
            sugar_script_text="use demo",
            output_dir=Path("E:/outputs"),
        )


def test_frontend_runtime_package_does_not_import_sugar_dsl() -> None:
    """Frontend runtime code should not import Sugar-DSL after backend migration."""

    offenders: list[str] = []
    for path in Path("substitute").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "from sugar." in source or "import sugar." in source:
            offenders.append(str(path))

    assert offenders == []
