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

"""Tests for Substitute model-load progress event routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.ports.comfy_gateway import ModelLoadProgressUpdate
from substitute.infrastructure.comfy.model_load_progress_event_router import (
    route_model_load_progress_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "model_load_progress_event_router.py"
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


def test_model_load_progress_router_imports_no_ui_or_listener_boundaries() -> None:
    """Model-load routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_model_load_progress_event_dispatches_valid_updates() -> None:
    """Valid model-load events should be parsed and sent to the callback."""

    events: list[ModelLoadProgressUpdate] = []

    result = route_model_load_progress_event(
        "substitute_model_load_progress",
        {
            "version": 1,
            "prompt_id": "pid-1",
            "node_id": "24.0.1",
            "display_node_id": "24",
            "source_node_id": "2",
            "source_input_key": "ckpt_name",
            "phase": "dynamic_vram_staging",
            "state": "running",
            "percent": 140,
            "value": 2048,
            "max": 4897,
            "model_name": "example.safetensors",
        },
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"2", "24"},
        source_metadata_resolver=lambda _node_id, _all_node_ids: (
            "Cube",
            "checkpoint",
        ),
        on_model_load_progress=events.append,
    )

    assert result.handled is True
    assert result.emitted is True
    assert len(events) == 1
    event = events[0]
    assert event.workflow_id == "wf-1"
    assert event.prompt_id == "pid-1"
    assert event.node_id == "24.0.1"
    assert event.display_node_id == "24"
    assert event.percent == 100.0
    assert event.source_cube_alias == "Cube"
    assert event.source_workflow_node_name == "checkpoint"


def test_route_model_load_progress_event_consumes_malformed_payloads() -> None:
    """Malformed model-load events should be handled without callback dispatch."""

    events: list[ModelLoadProgressUpdate] = []

    result = route_model_load_progress_event(
        "substitute_model_load_progress",
        {
            "version": 99,
            "prompt_id": "pid-1",
            "phase": "dynamic_vram_staging",
            "state": "running",
        },
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"24"},
        source_metadata_resolver=lambda _node_id, _all_node_ids: (None, None),
        on_model_load_progress=events.append,
    )

    assert result.handled is True
    assert result.emitted is False
    assert events == []


def test_route_model_load_progress_event_ignores_unknown_event_types() -> None:
    """Non-model-load events should be left for later routing."""

    events: list[ModelLoadProgressUpdate] = []

    result = route_model_load_progress_event(
        "progress",
        {"prompt_id": "pid-1"},
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"24"},
        source_metadata_resolver=lambda _node_id, _all_node_ids: (None, None),
        on_model_load_progress=events.append,
    )

    assert result.handled is False
    assert result.emitted is False
    assert events == []
