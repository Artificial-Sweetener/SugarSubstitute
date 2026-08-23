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

"""Tests for shell generation request-building policy helpers."""

from __future__ import annotations

from pathlib import Path


from tests.presentation.shell.generation.request_builder.support import (
    FORBIDDEN_IMPORT_PREFIXES,
    WORKSPACE_CONTROLLER_SOURCE,
    _imported_module_names,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_workspace_generation_request_builder_imports_no_concrete_boundaries() -> None:
    """Request builder helpers should not import Qt or concrete controllers."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_workspace_controller_no_longer_owns_activation_delta_helpers() -> None:
    """Workspace controller should delegate request-building helper policy."""

    source = WORKSPACE_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    assert "def _activation_node_keys_by_alias(" not in source
    assert "def _workflow_buffer_nodes_for_alias(" not in source
    assert "def _node_payload_has_authored_bypass(" not in source
    assert "def _active_behavior_snapshot(" not in source
    assert "def _editor_panel_for_workflow(" not in source
    assert "def _active_global_override_scopes(" not in source
    assert "def _errored_cube_aliases(" not in source
    assert "def _workflow_issue_pruning_service(" not in source
    assert "def _pruned_workflow_for_generation(" not in source
    assert "def _preflight_live_node_definitions(" not in source
    assert "def _build_generation_request_profiled(" not in source
