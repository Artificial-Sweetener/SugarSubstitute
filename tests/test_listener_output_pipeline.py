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

"""Tests for listener final-output pipeline assembly."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.listener_output_pipeline import (
    build_listener_output_pipeline,
)
from substitute.infrastructure.comfy.listener_visual_event_guard import (
    ListenerVisualEventGuard,
)

_PIPELINE_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_output_pipeline.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
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


def test_listener_output_pipeline_imports_no_ui_or_listener_boundaries() -> None:
    """Output pipeline assembly must stay independent of UI and listener code."""

    source = _PIPELINE_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_listener_output_pipeline_builds_source_resolver_for_cube_outputs() -> None:
    """Output pipeline should expose cube-output ids and source resolution."""

    pipeline = build_listener_output_pipeline(
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
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        callbacks=_callbacks(),
        visual_event_guard=_visual_event_guard(),
        on_output_source_diagnostic=lambda _diagnostic: None,
        on_cube_output_diagnostic=lambda _diagnostic: None,
    )

    source_identity = pipeline.output_source_resolver.resolve("1")

    assert pipeline.cube_output_node_ids == {"2"}
    assert source_identity.node_id == "2"
    assert source_identity.source_key == "wf-1:2"
    assert source_identity.cube_alias == "CubeA"


def test_listener_output_pipeline_logs_missing_cube_output_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing cube-output nodes should be logged with listener identity."""

    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.infrastructure.comfy.listener_output_pipeline",
    )

    pipeline = build_listener_output_pipeline(
        request=_request({"1": {"class_type": "KSampler"}}),
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        callbacks=_callbacks(),
        visual_event_guard=_visual_event_guard(),
        on_output_source_diagnostic=lambda _diagnostic: None,
        on_cube_output_diagnostic=lambda _diagnostic: None,
    )

    assert pipeline.cube_output_node_ids == set()
    assert (
        "No SugarCubes.CubeOutput nodes found in queued workflow payload" in caplog.text
    )
    assert "workflow_id=wf-1" in caplog.text
    assert "generation_run_id=run-1" in caplog.text
    assert "prompt_id=pid-1" in caplog.text


def _request(workflow_payload: dict[str, object]) -> ListenerStartRequest:
    """Build a listener start request for output-pipeline tests."""

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
    """Build callbacks required by output-pipeline construction."""

    return ListenerCallbacks(
        on_progress=lambda _event: None,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda _event: None,
        on_timing=lambda _event: None,
        on_completed=lambda _event: None,
    )


def _visual_event_guard() -> ListenerVisualEventGuard:
    """Build a visual event guard for output-pipeline construction."""

    return ListenerVisualEventGuard(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        on_diagnostic=lambda _diagnostic: None,
    )
