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

"""SugarCubes maintenance readiness contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy import sugarcubes_dependency_installer
from substitute.infrastructure.comfy import sugarcubes_maintenance_runner
from tests.infrastructure.comfy.nodepacks.sugarcubes.support import (
    _workspace_python_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "sugarcubes_maintenance_runner.py"
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


def test_sugarcubes_installable_missing_node_ids_filters_readiness_plan() -> None:
    """Install planning should only return missing, installable, uninstalled nodes."""

    assert sugarcubes_dependency_installer.sugarcubes_installable_missing_node_ids(
        {
            "dependencyReadiness": {
                "ready": False,
                "missingCustomNodes": ["SimpleSyrup", "uninstallable"],
                "installPlan": [
                    {
                        "nodeId": "SimpleSyrup",
                        "installable": True,
                        "installed": False,
                    },
                    {
                        "nodeId": "already-installed",
                        "installable": True,
                        "installed": True,
                    },
                    {
                        "nodeId": "uninstallable",
                        "installable": False,
                        "installed": False,
                    },
                    {
                        "nodeId": "not-missing",
                        "installable": True,
                        "installed": False,
                    },
                ],
            }
        }
    ) == ("SimpleSyrup",)


def test_sugarcubes_installable_missing_node_ids_falls_back_to_failed_nodes() -> None:
    """Legacy repair payloads should still identify failed missing node installs."""

    assert sugarcubes_dependency_installer.sugarcubes_installable_missing_node_ids(
        {
            "dependencyReadiness": {
                "ready": False,
                "missingCustomNodes": ["SimpleSyrup"],
            },
            "repairResult": {
                "failedNodes": [
                    {"nodeId": "SimpleSyrup"},
                    {"nodeId": "not-missing"},
                ]
            },
        }
    ) == ("SimpleSyrup",)


def test_run_sugarcubes_baseline_maintenance_requires_entrypoint(
    tmp_path: Path,
) -> None:
    """A missing SugarCubes maintenance module should remain a structural failure."""

    python_path = _workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="entrypoint is missing"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)
