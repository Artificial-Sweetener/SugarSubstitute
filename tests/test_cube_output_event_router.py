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

"""Tests for Substitute cube-output event validation routing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputRouteContext,
    route_cube_output_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "cube_output_event_router.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _payload(**updates: object) -> dict[str, object]:
    """Return a valid cube-output payload with optional top-level updates."""

    payload: dict[str, object] = {
        "version": 2,
        "prompt_id": "pid-1",
        "node_id": "output-node",
        "list_index": 0,
        "cube_id": "cube-1",
        "default_alias": "CubeA",
        "instance_alias": "CubeA",
        "instance_id": "instance-1",
        "media_kind": "image",
        "value_type": "image",
        "artifacts": [
            {
                "filename": "image.png",
                "subfolder": "",
                "type": "output",
                "media_kind": "image",
            }
        ],
        "substitute": {
            "schemaVersion": 1,
            "workflowId": "wf-1",
            "generationRunId": "run-1",
            "clientId": "client",
            "sourceKey": "wf-1:output-node",
            "sourceLabel": "CubeA",
        },
    }
    payload.update(updates)
    return payload


def _context() -> CubeOutputRouteContext:
    """Return a default listener context for routing tests."""

    return CubeOutputRouteContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )


def _accept_identity(
    _identity: object,
    _prompt_id: str | None,
    _node_id: str | None,
) -> bool:
    """Accept visual identity for routing tests."""

    return True


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_cube_output_router_imports_no_ui_or_listener_boundaries() -> None:
    """Cube-output routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_cube_output_event_returns_valid_event_and_source_identity() -> None:
    """Valid image outputs should return parsed data for persistence."""

    result = route_cube_output_event(
        _payload(),
        context=_context(),
        identity_acceptor=_accept_identity,
    )

    assert result.diagnostic is None
    assert result.cube_output is not None
    assert result.cube_output.node_id == "output-node"
    assert result.source_identity is not None
    assert result.source_identity.node_id == "output-node"
    assert result.source_identity.source_key == "wf-1:output-node"
    assert result.source_identity.source_label == "CubeA"
    assert result.source_identity.cube_alias == "CubeA"


@pytest.mark.parametrize(
    ("payload", "message", "level", "reason"),
    [
        (
            {"version": 99},
            "Ignoring malformed cube-output websocket event",
            "warning",
            None,
        ),
        (
            _payload(prompt_id=None),
            "Ignoring cube-output event without prompt id",
            "warning",
            "missing_prompt_id",
        ),
        (
            _payload(prompt_id="other"),
            "Ignoring cube-output event for different prompt",
            "debug",
            "prompt_mismatch",
        ),
        (
            _payload(media_kind="value"),
            "Ignoring unsupported cube-output media kind",
            "info",
            None,
        ),
        (
            _payload(node_id=None),
            "Ignoring cube-output event without node id",
            "warning",
            None,
        ),
        (
            _payload(list_index=-1),
            "Ignoring cube-output event without usable list index",
            "warning",
            "negative_list_index",
        ),
    ],
)
def test_route_cube_output_event_returns_expected_diagnostics(
    payload: dict[str, object],
    message: str,
    level: str,
    reason: str | None,
) -> None:
    """Invalid cube-output payloads should return current listener diagnostics."""

    result = route_cube_output_event(
        payload,
        context=_context(),
        identity_acceptor=_accept_identity,
    )

    assert result.cube_output is None
    assert result.source_identity is None
    assert result.diagnostic is not None
    assert result.diagnostic.message == message
    assert result.diagnostic.level == level
    assert result.diagnostic.fields["workflow_id"] == "wf-1"
    if reason is not None:
        assert result.diagnostic.fields["reason"] == reason


@pytest.mark.parametrize(
    ("list_index", "reason"),
    [
        (None, "missing_list_index"),
        ("0", "non_integer_list_index"),
        (True, "non_integer_list_index"),
        (-1, "negative_list_index"),
    ],
)
def test_route_cube_output_event_rejects_unusable_list_index(
    list_index: object,
    reason: str,
) -> None:
    """Live final events without usable list indexes should fail closed."""

    result = route_cube_output_event(
        _payload(list_index=list_index),
        context=_context(),
        identity_acceptor=_accept_identity,
    )

    assert result.diagnostic is not None
    assert (
        result.diagnostic.message
        == "Ignoring cube-output event without usable list index"
    )
    assert result.diagnostic.fields["reason"] == reason


def test_route_cube_output_event_stops_after_identity_rejection() -> None:
    """Rejected Substitute visual identity should suppress persistence and diagnostics."""

    result = route_cube_output_event(
        _payload(),
        context=_context(),
        identity_acceptor=lambda _identity, _prompt_id, _node_id: False,
    )

    assert result.cube_output is None
    assert result.source_identity is None
    assert result.diagnostic is None
