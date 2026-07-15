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

"""Tests for Comfy binary websocket diagnostic construction."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BINARY_TEXT_PREVIEW_LIMIT,
    BinaryEventContext,
    binary_text_event_diagnostic,
    malformed_binary_text_frame_diagnostic,
    malformed_metadata_preview_frame_diagnostic,
    malformed_preview_metadata_diagnostic,
    metadata_less_preview_frame_diagnostic,
    metadata_preview_missing_prompt_id_diagnostic,
    metadata_preview_missing_source_node_diagnostic,
    metadata_preview_prompt_mismatch_diagnostic,
    non_bytes_binary_payload_diagnostic,
    short_binary_frame_diagnostic,
    short_binary_text_frame_diagnostic,
    short_metadata_preview_frame_diagnostic,
    unencoded_binary_preview_event_diagnostic,
    undecodable_preview_image_diagnostic,
    unknown_binary_event_diagnostic,
)

_DIAGNOSTICS_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "comfy_binary_event_diagnostics.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _context() -> BinaryEventContext:
    """Return the canonical binary event diagnostic context."""

    return BinaryEventContext(
        workflow_id="wf-1",
        prompt_id="pid-1",
        generation_run_id="run-1",
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


def test_binary_event_diagnostics_import_no_ui_or_listener_boundaries() -> None:
    """Binary event diagnostics must stay independent of UI and listener code."""

    source = _DIAGNOSTICS_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_non_bytes_binary_payload_diagnostic() -> None:
    """Non-bytes payload diagnostics should include payload type context."""

    diagnostic = non_bytes_binary_payload_diagnostic(
        _context(),
        payload_type="str",
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring non-bytes websocket payload"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_type": "str",
    }


def test_short_binary_frame_diagnostic() -> None:
    """Short frame diagnostics should include payload length context."""

    diagnostic = short_binary_frame_diagnostic(
        _context(),
        payload_length=3,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring short Comfy binary websocket frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_length": 3,
    }


def test_short_binary_text_frame_diagnostic() -> None:
    """Short text frame diagnostics should include payload length context."""

    diagnostic = short_binary_text_frame_diagnostic(
        _context(),
        payload_length=2,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring short Comfy binary text frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_length": 2,
    }


def test_malformed_binary_text_frame_diagnostic() -> None:
    """Malformed text frame diagnostics should include framing context."""

    diagnostic = malformed_binary_text_frame_diagnostic(
        _context(),
        node_id_length=24,
        payload_length=12,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring malformed Comfy binary text frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "node_id_length": 24,
        "payload_length": 12,
    }


def test_binary_text_event_diagnostic_limits_text_preview() -> None:
    """Text event diagnostics should include bounded text preview context."""

    text = "x" * (BINARY_TEXT_PREVIEW_LIMIT + 10)

    diagnostic = binary_text_event_diagnostic(
        _context(),
        node_id="node-1",
        text=text,
    )

    assert diagnostic.level == "info"
    assert diagnostic.message == "Received Comfy binary text event"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "node_id": "node-1",
        "text_length": BINARY_TEXT_PREVIEW_LIMIT + 10,
        "text_preview": f"{'x' * BINARY_TEXT_PREVIEW_LIMIT}...",
    }


def test_metadata_less_preview_frame_diagnostic() -> None:
    """Metadata-less preview diagnostics should include binary frame context."""

    diagnostic = metadata_less_preview_frame_diagnostic(
        _context(),
        event_type=1,
        payload_length=256,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring metadata-less Comfy preview frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "binary_event_type": 1,
        "payload_length": 256,
        "reason": "missing_preview_metadata",
    }


def test_short_metadata_preview_frame_diagnostic() -> None:
    """Short metadata preview diagnostics should include payload length context."""

    diagnostic = short_metadata_preview_frame_diagnostic(
        _context(),
        payload_length=3,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring short Comfy metadata preview frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_length": 3,
    }


def test_malformed_metadata_preview_frame_diagnostic() -> None:
    """Malformed metadata preview diagnostics should include framing context."""

    diagnostic = malformed_metadata_preview_frame_diagnostic(
        _context(),
        metadata_length=512,
        payload_length=128,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring malformed Comfy metadata preview frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "metadata_length": 512,
        "payload_length": 128,
    }


def test_malformed_preview_metadata_diagnostic() -> None:
    """Malformed preview metadata diagnostics should include decode error context."""

    error = ValueError("bad metadata")

    diagnostic = malformed_preview_metadata_diagnostic(
        _context(),
        payload_length=12,
        error=error,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring malformed Comfy preview metadata"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "payload_length": 12,
        "error": error,
    }


def test_metadata_preview_missing_prompt_id_diagnostic() -> None:
    """Missing prompt diagnostics should include listener run context."""

    diagnostic = metadata_preview_missing_prompt_id_diagnostic(_context())

    assert diagnostic.level == "debug"
    assert diagnostic.message == "Ignoring Comfy metadata preview without prompt id"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "reason": "missing_prompt_id",
    }


def test_metadata_preview_prompt_mismatch_diagnostic() -> None:
    """Prompt mismatch diagnostics should include expected and event prompt ids."""

    diagnostic = metadata_preview_prompt_mismatch_diagnostic(
        _context(),
        event_prompt_id="pid-2",
    )

    assert diagnostic.level == "debug"
    assert diagnostic.message == "Ignoring Comfy metadata preview for different prompt"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "expected_prompt_id": "pid-1",
        "event_prompt_id": "pid-2",
        "reason": "prompt_mismatch",
    }


def test_metadata_preview_missing_source_node_diagnostic() -> None:
    """Missing source diagnostics should include metadata node context."""

    diagnostic = metadata_preview_missing_source_node_diagnostic(
        _context(),
        metadata_node_id="27.1",
        metadata_display_node_id="27",
    )

    assert diagnostic.level == "debug"
    assert (
        diagnostic.message
        == "Ignoring Comfy metadata preview without resolvable source node"
    )
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "generation_run_id": "run-1",
        "prompt_id": "pid-1",
        "metadata_node_id": "27.1",
        "metadata_display_node_id": "27",
        "reason": "missing_source_node",
    }


def test_unencoded_binary_preview_event_diagnostic() -> None:
    """Unsupported unencoded preview diagnostics should include event metadata."""

    diagnostic = unencoded_binary_preview_event_diagnostic(
        _context(),
        event_type=2,
        payload_length=128,
    )

    assert diagnostic.level == "info"
    assert (
        diagnostic.message
        == "Ignoring unsupported Comfy unencoded preview binary event"
    )
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "binary_event_type": 2,
        "payload_length": 128,
    }


def test_undecodable_preview_image_diagnostic() -> None:
    """Undecodable preview diagnostics should include prompt-safe decode context."""

    error = ValueError("invalid image bytes")

    diagnostic = undecodable_preview_image_diagnostic(
        _context(),
        node_id="node-1",
        image_format=2,
        event_type=3,
        payload_length=512,
        error=error,
    )

    assert diagnostic.level == "warning"
    assert diagnostic.message == "Ignoring undecodable Comfy preview image frame"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "node_id": "node-1",
        "image_format": 2,
        "binary_event_type": 3,
        "payload_length": 512,
        "error": error,
    }


def test_unknown_binary_event_diagnostic() -> None:
    """Unknown event diagnostics should include binary event type metadata."""

    diagnostic = unknown_binary_event_diagnostic(
        _context(),
        event_type=99,
        payload_length=64,
    )

    assert diagnostic.level == "info"
    assert diagnostic.message == "Ignoring unknown Comfy binary websocket event"
    assert diagnostic.fields == {
        "workflow_id": "wf-1",
        "prompt_id": "pid-1",
        "binary_event_type": 99,
        "payload_length": 64,
    }
