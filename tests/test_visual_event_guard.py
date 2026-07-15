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

"""Tests for Comfy visual event identity guard policy."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventContext,
    VisualEventRejectionReason,
    VisualEventRequestIdentity,
    substitute_visual_identity_rejection_reason,
    visual_event_rejection_diagnostic,
    visual_preview_missing_identity_diagnostic,
)

_GUARD_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "visual_event_guard.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _request_identity() -> VisualEventRequestIdentity:
    """Return the canonical listener run identity used by guard tests."""

    return VisualEventRequestIdentity(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )


def _event_context() -> VisualEventContext:
    """Return the canonical listener event context used by diagnostic tests."""

    return VisualEventContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        event_type="substitute_cube_output",
        node_id="node-1",
        display_node_id="display-1",
    )


def _visual_identity(**overrides: str) -> SubstituteVisualIdentity:
    """Return a valid visual identity with selected field overrides."""

    return SubstituteVisualIdentity(
        workflow_id=overrides.get("workflow_id", "wf-1"),
        generation_run_id=overrides.get("generation_run_id", "run-1"),
        client_id=overrides.get("client_id", "client-1"),
        source_key=overrides.get("source_key", "wf-1:source"),
        source_label=overrides.get("source_label", "Source"),
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


def test_visual_event_guard_imports_no_ui_or_listener_boundaries() -> None:
    """Visual identity guard policy must stay independent of UI and listener code."""

    source = _GUARD_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_visual_event_guard_accepts_matching_identity() -> None:
    """A fully matching visual identity should be accepted."""

    reason = substitute_visual_identity_rejection_reason(
        _visual_identity(),
        _request_identity(),
        prompt_id="pid-1",
    )

    assert reason is None


@pytest.mark.parametrize(
    ("identity", "prompt_id", "expected_reason"),
    [
        (None, "pid-1", "missing_substitute_identity"),
        (_visual_identity(), "other-prompt", "prompt_mismatch"),
        (_visual_identity(client_id="other-client"), "pid-1", "client_mismatch"),
        (_visual_identity(workflow_id="other-workflow"), "pid-1", "workflow_mismatch"),
        (
            _visual_identity(generation_run_id="other-run"),
            "pid-1",
            "generation_run_mismatch",
        ),
        (_visual_identity(source_key=""), "pid-1", "unknown_source"),
        (_visual_identity(source_label=""), "pid-1", "unknown_source"),
    ],
)
def test_visual_event_guard_reports_rejection_reason(
    identity: SubstituteVisualIdentity | None,
    prompt_id: str,
    expected_reason: str,
) -> None:
    """Visual event guard should report the first failing identity invariant."""

    reason = substitute_visual_identity_rejection_reason(
        identity,
        _request_identity(),
        prompt_id=prompt_id,
    )

    assert reason == expected_reason


@pytest.mark.parametrize(
    ("reason", "expected_level", "expected_message"),
    [
        (
            "missing_substitute_identity",
            "warning",
            "Ignoring visual event without Substitute identity",
        ),
        (
            "prompt_mismatch",
            "debug",
            "Ignoring visual event for different prompt",
        ),
        (
            "client_mismatch",
            "warning",
            "Ignoring visual event for different client",
        ),
        (
            "workflow_mismatch",
            "warning",
            "Ignoring visual event for different workflow",
        ),
        (
            "generation_run_mismatch",
            "debug",
            "Ignoring visual event for stale generation run",
        ),
        (
            "unknown_source",
            "warning",
            "Ignoring visual event without source identity",
        ),
    ],
)
def test_visual_event_guard_reports_rejection_diagnostic_level_and_message(
    reason: VisualEventRejectionReason,
    expected_level: str,
    expected_message: str,
) -> None:
    """Visual event guard should own rejection diagnostic severity and message."""

    diagnostic = visual_event_rejection_diagnostic(
        reason,
        _visual_identity(),
        _event_context(),
        event_prompt_id="pid-2",
    )

    assert diagnostic.level == expected_level
    assert diagnostic.message == expected_message
    assert diagnostic.fields["reason"] == reason


def test_visual_event_guard_reports_missing_identity_diagnostic_fields() -> None:
    """Missing identity diagnostics should include run and visual event context."""

    diagnostic = visual_event_rejection_diagnostic(
        "missing_substitute_identity",
        None,
        _event_context(),
        event_prompt_id="pid-1",
    )

    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "node_id": "node-1",
        "display_node_id": "display-1",
        "event_type": "substitute_cube_output",
        "reason": "missing_substitute_identity",
    }


def test_visual_event_guard_reports_prompt_mismatch_diagnostic_fields() -> None:
    """Prompt mismatch diagnostics should include expected and event prompt IDs."""

    diagnostic = visual_event_rejection_diagnostic(
        "prompt_mismatch",
        _visual_identity(),
        _event_context(),
        event_prompt_id="pid-2",
    )

    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "expected_prompt_id": "pid-1",
        "event_prompt_id": "pid-2",
        "event_type": "substitute_cube_output",
        "reason": "prompt_mismatch",
    }


def test_visual_event_guard_reports_identity_mismatch_diagnostic_fields() -> None:
    """Identity mismatch diagnostics should include the mismatched identity fields."""

    diagnostic = visual_event_rejection_diagnostic(
        "client_mismatch",
        _visual_identity(client_id="client-2"),
        _event_context(),
        event_prompt_id="pid-1",
    )

    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "expected_client_id": "client-1",
        "event_client_id": "client-2",
        "event_type": "substitute_cube_output",
        "reason": "client_mismatch",
    }


def test_visual_event_guard_reports_unknown_source_diagnostic_fields() -> None:
    """Unknown source diagnostics should include node and listener run context."""

    diagnostic = visual_event_rejection_diagnostic(
        "unknown_source",
        _visual_identity(source_key=""),
        _event_context(),
        event_prompt_id="pid-1",
    )

    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "node_id": "node-1",
        "event_type": "substitute_cube_output",
        "reason": "unknown_source",
    }


def test_visual_event_guard_reports_preview_missing_identity_diagnostic() -> None:
    """Preview emission diagnostics should include run and source node context."""

    diagnostic = visual_preview_missing_identity_diagnostic(
        VisualEventContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            event_type="preview",
            node_id="node-1",
        )
    )

    assert diagnostic.level == "debug"
    assert (
        diagnostic.message
        == "Ignoring Comfy preview without Substitute visual identity"
    )
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "node_id": "node-1",
        "reason": "missing_substitute_identity",
    }
