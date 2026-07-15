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

"""Tests for Comfy nodepack reconciliation log emission."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceDiagnostic,
    SugarCubesMaintenanceResult,
)
from substitute.infrastructure.comfy import nodepack_reconciliation_logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "nodepack_reconciliation_logger.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_nodepack_reconciliation_logger_imports_no_ui_or_process_boundaries() -> None:
    """Logger formatting must stay independent from UI and process execution."""

    imported_modules = _imported_module_names(
        ast.parse(LOGGER_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_emit_sugarcubes_diagnostics_formats_bounded_callback_messages() -> None:
    """SugarCubes diagnostics should reach setup callbacks without raw payloads."""

    emitted: list[str] = []
    result = SugarCubesMaintenanceResult(
        exit_code=2,
        payload={},
        diagnostics=(
            SugarCubesMaintenanceDiagnostic(
                code="base_cubes_sync_failed",
                severity="warning",
                title="Base-Cubes sync failed",
                message="Using local checkout.",
                details={
                    "repoRef": "Artificial-Sweetener/Base-Cubes",
                    "reason": "ahead",
                    "ignored": "not surfaced",
                },
            ),
        ),
        output_excerpt=("{", '"raw": "payload"', "}"),
    )

    nodepack_reconciliation_logger.emit_sugarcubes_diagnostics(
        result,
        on_log=emitted.append,
    )

    assert emitted == [
        "WARNING: SugarCubes[base_cubes_sync_failed]: Base-Cubes sync failed: "
        "Using local checkout. (repoRef=Artificial-Sweetener/Base-Cubes; reason=ahead)"
    ]


def test_emit_log_writes_structured_context_and_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durable log entries should keep context while callbacks receive text only."""

    log_calls: list[tuple[str, dict[str, object]]] = []
    emitted: list[str] = []

    def fake_log_info(logger: object, message: str, **context: object) -> None:
        """Record logger context without depending on process logging config."""

        _ = logger
        log_calls.append((message, context))

    monkeypatch.setattr(nodepack_reconciliation_logger, "log_info", fake_log_info)

    nodepack_reconciliation_logger.emit_log(
        emitted.append,
        "[SugarCubes] Base-Cubes sync and dependencies are ready.",
        operation="sugarcubes_maintenance",
        diagnostic_code="ready",
    )

    assert emitted == ["[SugarCubes] Base-Cubes sync and dependencies are ready."]
    assert log_calls == [
        (
            "[SugarCubes] Base-Cubes sync and dependencies are ready.",
            {
                "operation": "sugarcubes_maintenance",
                "diagnostic_code": "ready",
            },
        )
    ]


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
