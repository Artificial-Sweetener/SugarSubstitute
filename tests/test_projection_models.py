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

"""Verify editor projection model boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel import projection_models


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_models.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_MODEL_IMPORT_PREFIXES = (
    "PySide6",
    "qpane",
    "qfluentwidgets",
    "qframelesswindow",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return all imported module names from one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_projected_cube_build_records_staged_widget_context() -> None:
    """Projected build records should carry the hidden-build reveal context."""

    build = projection_models.ProjectedCubeBuild(
        cube_alias="cube-a",
        final_widget=object(),
        build_session=object(),
        started_at=12.5,
        token=object(),
    )

    assert build.cube_alias == "cube-a"
    assert build.started_at == 12.5


def test_incremental_insert_completion_state_tracks_once_only_callbacks() -> None:
    """Incremental insert state should default to no reported callbacks."""

    state = projection_models.EditorIncrementalInsertCompletionState()

    assert state.first_usable_completed is False
    assert state.insert_completion_reported is False


def test_projection_models_do_not_import_qt_or_widget_libraries() -> None:
    """Projection models should remain portable across Qt bindings."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(MODELS_SOURCE)
            if imported_module.startswith(FORBIDDEN_MODEL_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_projection_coordinator_does_not_own_projection_model_definitions() -> None:
    """Projection coordinator should import shared models instead of owning them."""

    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    assert "class ProjectedCubeBuild" not in source
    assert "class EditorFullProjectionLoadRequest" not in source
    assert "class EditorFullProjectionLoadPlan" not in source
    assert "class EditorFullProjectionBusyState" not in source
    assert "class EditorIncrementalInsertRequest" not in source
    assert "class EditorIncrementalInsertPlan" not in source
    assert "class EditorIncrementalInsertCompletionState" not in source
