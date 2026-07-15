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

"""Tests for listener runtime collaborator composition."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.listener_runtime_composition import (
    build_listener_runtime_composition,
)
from substitute.infrastructure.comfy.websocket_transport import (
    PreconnectedComfyWebsocketSession,
)

_COMPOSITION_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_runtime_composition.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _WebSocketClient:
    """Provide a minimal websocket-client protocol test double."""

    def connect(self, *args: object, **kwargs: object) -> object:
        """Ignore connect calls."""

        return None

    def send(self, payload: str) -> object:
        """Ignore sent websocket messages."""

        return None

    def recv(self) -> object:
        """Return no websocket payload."""

        return None

    def close(self) -> object:
        """Ignore close calls."""

        return None


def test_listener_runtime_composition_imports_no_ui_or_listener_boundaries() -> None:
    """Runtime composition must stay independent of UI and listener facade code."""

    source = _COMPOSITION_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_listener_runtime_composition_builds_default_connection_context() -> None:
    """Composition should wire listener identity and default websocket URL."""

    endpoint = ComfyEndpoint(host="10.0.0.5", port=9000)
    runtime = build_listener_runtime_composition(
        request=_request(
            {
                "1": {"class_type": "KSampler"},
                "2": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.Output"},
                    "inputs": {"image": ["1", 0]},
                },
            }
        ),
        callbacks=_callbacks(),
        logger=logging.getLogger("tests.listener_runtime_composition"),
        decode_preview_image=lambda _image_bytes: object(),
        websocket_url=None,
        endpoint=endpoint,
        preconnected_session=None,
        connect_timeout_seconds=2.5,
        receive_timeout_seconds=7.5,
    )

    source_identity = runtime.output_source_resolver.resolve("1")

    assert runtime.endpoint == endpoint
    assert runtime.receive_timeout_seconds == 7.5
    assert runtime.websocket_connection_manager.client_id == "client-1"
    assert runtime.websocket_connection_manager.websocket_url == endpoint.websocket_url(
        "client-1"
    )
    assert runtime.websocket_connection_manager.connect_timeout_seconds == 2.5
    assert runtime.progress_context.workflow_id == "wf-1"
    assert runtime.progress_context.generation_run_id == "run-1"
    assert runtime.progress_context.prompt_id == "pid-1"
    assert runtime.progress_context.client_id == "client-1"
    assert runtime.cube_output_node_ids == {"2"}
    assert source_identity.node_id == "2"
    assert source_identity.source_key == "wf-1:2"
    assert source_identity.cube_alias == "CubeA"


def test_listener_runtime_composition_preserves_explicit_websocket_session() -> None:
    """Composition should keep caller-provided websocket URL and preconnection."""

    preconnected_session = PreconnectedComfyWebsocketSession(
        client_id="client-1",
        websocket_url="ws://example/preconnected",
        websocket_client=_WebSocketClient(),
    )

    runtime = build_listener_runtime_composition(
        request=_request({"1": {"class_type": "KSampler"}}),
        callbacks=_callbacks(),
        logger=logging.getLogger("tests.listener_runtime_composition"),
        decode_preview_image=lambda _image_bytes: object(),
        websocket_url="ws://example/explicit",
        endpoint=None,
        preconnected_session=preconnected_session,
        connect_timeout_seconds=1.25,
        receive_timeout_seconds=6.0,
    )

    assert runtime.endpoint == ComfyEndpoint(host="127.0.0.1", port=8188)
    assert runtime.websocket_connection_manager.websocket_url == "ws://example/explicit"
    assert runtime.websocket_connection_manager.preconnected_session is (
        preconnected_session
    )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _request(workflow_payload: dict[str, object]) -> ListenerStartRequest:
    """Build a listener start request for composition tests."""

    return ListenerStartRequest(
        prompt_id="pid-1",
        generation_run_id="run-1",
        client_id="client-1",
        listener_session=ListenerSessionHandle(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
            session=object(),
        ),
        output_dir=Path("out"),
        workflow_payload=workflow_payload,
        sugar_script="line one",
        workflow_id="wf-1",
        workflow_name="Workflow",
    )


def _callbacks() -> ListenerCallbacks:
    """Build callbacks required by runtime composition."""

    return ListenerCallbacks(
        on_progress=lambda _event: None,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda _event: None,
        on_timing=lambda _event: None,
        on_completed=lambda _event: None,
    )
