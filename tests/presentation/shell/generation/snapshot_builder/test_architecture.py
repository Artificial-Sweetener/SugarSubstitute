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

"""Tests for shell generation snapshot-building helpers."""

from __future__ import annotations

from pathlib import Path


from tests.presentation.shell.generation.snapshot_builder.support import (
    _imported_module_names,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_snapshot_builder.py"
)
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def test_workspace_generation_snapshot_builder_imports_no_concrete_boundaries() -> None:
    """Snapshot builder helpers should not import Qt or concrete controllers."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_workspace_controller_no_longer_owns_serialization_helpers() -> None:
    """Workspace controller should delegate moved serialization helper policy."""

    source = WORKSPACE_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    assert "def _serialize_generation_workflow(" not in source
    assert "def _create_recipe_serialization_context(" not in source
    assert "def _build_recipe_serialization_plan(" not in source
    assert "def _preprocess_generation_workflow(" not in source
