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

"""Tests for Comfy listener diagnostic logging helpers."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.comfy_binary_event_diagnostics import (
    BinaryEventDiagnostic,
)
from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputDiagnostic,
)
from substitute.infrastructure.comfy.listener_diagnostic_logging import (
    ListenerDiagnosticLogger,
)
from substitute.infrastructure.comfy.model_load_source_metadata_resolver import (
    ModelLoadSourceMetadataDiagnostic,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceDiagnostic,
)
from substitute.infrastructure.comfy.visual_event_guard import (
    VisualEventRejectionDiagnostic,
)
from substitute.shared.logging.logger import get_logger

_LOGGING_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_diagnostic_logging.py"
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


def test_listener_diagnostic_logging_imports_no_ui_or_listener_boundaries() -> None:
    """Diagnostic logging must stay independent of UI and listener code."""

    source = _LOGGING_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_log_binary_event_diagnostic_uses_selected_levels(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Binary diagnostics should preserve debug, info, and warning levels."""

    diagnostic_logger = ListenerDiagnosticLogger(
        get_logger("tests.listener_diagnostic_logging.binary")
    )
    caplog.set_level(logging.DEBUG, logger=diagnostic_logger.logger.name)

    diagnostic_logger.binary_event(
        BinaryEventDiagnostic(
            level="debug",
            message="binary debug",
            fields={"node_id": "1"},
        ),
    )
    diagnostic_logger.binary_event(
        BinaryEventDiagnostic(
            level="info",
            message="binary info",
            fields={"node_id": "2"},
        ),
    )
    diagnostic_logger.binary_event(
        BinaryEventDiagnostic(
            level="warning",
            message="binary warning",
            fields={"node_id": "3"},
        ),
    )

    assert ("DEBUG", "binary debug | node_id=1") in _level_messages(caplog.records)
    assert ("INFO", "binary info | node_id=2") in _level_messages(caplog.records)
    assert (
        "WARNING",
        "binary warning | node_id=3",
    ) in _level_messages(caplog.records)


def test_log_cube_output_diagnostic_uses_selected_levels(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cube-output diagnostics should preserve selected log levels."""

    diagnostic_logger = ListenerDiagnosticLogger(
        get_logger("tests.listener_diagnostic_logging.cube_output")
    )
    caplog.set_level(logging.DEBUG, logger=diagnostic_logger.logger.name)

    diagnostic_logger.cube_output(
        CubeOutputDiagnostic(
            level="debug",
            message="cube debug",
            fields={"node_id": "1"},
        ),
    )
    diagnostic_logger.cube_output(
        CubeOutputDiagnostic(
            level="info",
            message="cube info",
            fields={"node_id": "2"},
        ),
    )
    diagnostic_logger.cube_output(
        CubeOutputDiagnostic(
            level="warning",
            message="cube warning",
            fields={"node_id": "3"},
        ),
    )

    assert ("DEBUG", "cube debug | node_id=1") in _level_messages(caplog.records)
    assert ("INFO", "cube info | node_id=2") in _level_messages(caplog.records)
    assert ("WARNING", "cube warning | node_id=3") in _level_messages(caplog.records)


def test_log_model_load_source_metadata_diagnostic_uses_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Model-load source metadata diagnostics should log at info."""

    diagnostic_logger = ListenerDiagnosticLogger(
        get_logger("tests.listener_diagnostic_logging.model_load")
    )
    caplog.set_level(logging.INFO, logger=diagnostic_logger.logger.name)

    diagnostic_logger.model_load_source_metadata(
        ModelLoadSourceMetadataDiagnostic(
            level="info",
            message="model metadata",
            fields={"source_node_id": "2"},
        ),
    )

    assert ("INFO", "model metadata | source_node_id=2") in _level_messages(
        caplog.records
    )


def test_log_visual_and_output_source_diagnostics_use_selected_levels(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Visual and output-source diagnostics should preserve selected log levels."""

    diagnostic_logger = ListenerDiagnosticLogger(
        get_logger("tests.listener_diagnostic_logging.visual_output")
    )
    caplog.set_level(logging.DEBUG, logger=diagnostic_logger.logger.name)

    diagnostic_logger.visual_event(
        VisualEventRejectionDiagnostic(
            level="debug",
            message="visual debug",
            fields={"reason": "prompt_mismatch"},
        ),
    )
    diagnostic_logger.visual_event(
        VisualEventRejectionDiagnostic(
            level="warning",
            message="visual warning",
            fields={"reason": "unknown_source"},
        ),
    )
    diagnostic_logger.output_source(
        OutputSourceDiagnostic(
            level="debug",
            message="output debug",
            fields={"node_id": "1"},
        ),
    )
    diagnostic_logger.output_source(
        OutputSourceDiagnostic(
            level="warning",
            message="output warning",
            fields={"node_id": "2"},
        ),
    )

    messages = _level_messages(caplog.records)
    assert ("DEBUG", "visual debug | reason=prompt_mismatch") in messages
    assert ("WARNING", "visual warning | reason=unknown_source") in messages
    assert ("DEBUG", "output debug | node_id=1") in messages
    assert ("WARNING", "output warning | node_id=2") in messages


def _level_messages(records: list[logging.LogRecord]) -> set[tuple[str, str]]:
    """Return level/message pairs from captured log records."""

    return {(record.levelname, record.getMessage()) for record in records}
