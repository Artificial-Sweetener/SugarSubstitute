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

"""Tests for pure SugarCubes maintenance report parsing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.comfy_nodepacks.sugarcubes_maintenance_report_parser import (
    SugarCubesMaintenanceResult,
    diagnostic_detail_summary,
    parse_sugarcubes_maintenance_payload,
    sugarcubes_maintenance_result,
    sugarcubes_required_dependency_failure_message,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARSER_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "comfy_nodepacks"
    / "sugarcubes_maintenance_report_parser.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_sugarcubes_report_parser_imports_no_side_effect_boundaries() -> None:
    """Keep SugarCubes report parsing independent from UI and infrastructure."""

    imported_modules = _imported_module_names(
        ast.parse(PARSER_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_parse_sugarcubes_maintenance_payload_reads_first_json_object() -> None:
    """Maintenance parsing should tolerate non-JSON log text around the payload."""

    assert parse_sugarcubes_maintenance_payload(
        (
            "starting maintenance",
            "{",
            '  "ok": true,',
            '  "value": 3',
            "}",
            "finished maintenance",
        )
    ) == {"ok": True, "value": 3}


def test_sugarcubes_maintenance_result_prefers_explicit_diagnostics() -> None:
    """Explicit SugarCubes diagnostics should not be replaced by synthesis."""

    result = sugarcubes_maintenance_result(
        2,
        (
            "{",
            '  "diagnostics": [',
            "    {",
            '      "code": "base_cubes_sync_failed",',
            '      "severity": "warning",',
            '      "title": "Base-Cubes sync failed",',
            '      "message": "Using local checkout.",',
            '      "details": {"repoRef": "Artificial-Sweetener/Base-Cubes"}',
            "    }",
            "  ],",
            '  "dependencyReadiness": {"ready": false, "missingCustomNodes": ["SimpleSyrup"]}',
            "}",
        ),
    )

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "base_cubes_sync_failed"
    assert diagnostic.severity == "warning"
    assert diagnostic.title == "Base-Cubes sync failed"
    assert diagnostic.message == "Using local checkout."
    assert diagnostic.details == {"repoRef": "Artificial-Sweetener/Base-Cubes"}
    assert result.output_excerpt[-1] == "}"


def test_sugarcubes_maintenance_result_synthesizes_readiness_diagnostic() -> None:
    """Dependency readiness should produce a startup diagnostic when incomplete."""

    result = sugarcubes_maintenance_result(
        2,
        (
            "{",
            '  "restartRequired": true,',
            '  "dependencyReadiness": {',
            '    "ready": false,',
            '    "missingCustomNodes": ["SimpleSyrup"],',
            '    "installedCustomNodes": ["comfyui-vectorscope-cc"],',
            '    "installPlan": [',
            '      {"nodeId": "SimpleSyrup", "installable": true, "installed": false}',
            "    ]",
            "  }",
            "}",
        ),
    )

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "sugarcubes_dependency_maintenance_pending"
    assert diagnostic.severity == "error"
    assert diagnostic.details == {
        "restartRequired": True,
        "missingCustomNodes": ["SimpleSyrup"],
        "installedCustomNodes": ["comfyui-vectorscope-cc"],
        "installPlanNodeIds": ["SimpleSyrup"],
    }


def test_sugarcubes_maintenance_result_synthesizes_unparseable_diagnostic() -> None:
    """Nonzero maintenance without JSON should still produce actionable diagnostics."""

    result = sugarcubes_maintenance_result(1, ("starting", "not json", "failed"))

    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "sugarcubes_maintenance_output_unparseable"
    assert diagnostic.severity == "error"
    assert diagnostic.details == {"outputExcerpt": "starting\nnot json\nfailed"}


def test_required_dependency_failure_message_includes_node_groups() -> None:
    """Setup failure messages should name missing, failed, and skipped nodepacks."""

    result = SugarCubesMaintenanceResult(
        exit_code=2,
        payload={
            "dependencyReadiness": {
                "ready": False,
                "missingCustomNodes": ["SimpleSyrup"],
            },
            "repairResult": {
                "failedNodes": [{"nodeId": "BrokenNode"}],
                "skippedNodes": [{"nodeId": "SkippedNode"}],
            },
        },
        diagnostics=(),
        output_excerpt=(),
    )

    message = sugarcubes_required_dependency_failure_message(result)

    assert "Missing nodepacks: SimpleSyrup." in message
    assert "Failed installs: BrokenNode." in message
    assert "Skipped installs: SkippedNode." in message


def test_diagnostic_detail_summary_extracts_nested_diagnostic_fields() -> None:
    """Diagnostic log summaries should include direct and nested detail fields."""

    assert (
        diagnostic_detail_summary(
            {
                "error": "boom",
                "details": {
                    "nodeId": "SimpleSyrup",
                    "status": "missing",
                },
            }
        )
        == "nodeId=SimpleSyrup; error=boom; status=missing"
    )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
