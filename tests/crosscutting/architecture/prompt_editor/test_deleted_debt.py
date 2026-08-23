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

"""Prevent deleted prompt-editor architecture debt from returning."""

from __future__ import annotations

import ast

from .inventory import (
    PROJECT_ROOT,
    PROMPT_PRESENTATION_ROOT,
)


def test_deleted_editing_graph_cannot_return() -> None:
    """Keep the obsolete mutation graph and package-root barrel deleted."""

    deleted_files = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "command_adapter.py",
        PROMPT_PRESENTATION_ROOT / "interactions" / "edit_command_router.py",
    )
    assert all(not path.exists() for path in deleted_files)
    editing_session_root = PROMPT_PRESENTATION_ROOT / "editing_session"
    assert not tuple(editing_session_root.glob("*.py"))
    assert not tuple(editing_session_root.glob("*.pyi"))

    forbidden_fragments = (
        "PromptEditController",
        "PromptEditCommandRouter",
        "PromptEditorCommandAdapter",
        "PromptProjectionSourceChangeApplication",
        "PromptProjectionRestoreApplication",
        "PromptEditingSessionSourceChange",
        "apply_source_change_application",
        "apply_restore_application",
        "attach_runtime_mutation_actions",
    )
    source_paths = (
        *(PROMPT_PRESENTATION_ROOT.rglob("*.py")),
        *(PROMPT_PRESENTATION_ROOT.rglob("*.pyi")),
    )
    violations = {
        fragment: tuple(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in source_paths
            if fragment in path.read_text(encoding="utf-8")
        )
        for fragment in forbidden_fragments
    }
    assert {fragment: paths for fragment, paths in violations.items() if paths} == {}

    command_root = PROMPT_PRESENTATION_ROOT / "commands" / "__init__.py"
    tree = ast.parse(command_root.read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def test_deleted_layout_transition_host_cannot_return() -> None:
    """Keep the replaced layout-host module out of the projection graph."""

    deleted_files = (
        PROMPT_PRESENTATION_ROOT / "projection" / "layout_engine.py",
        PROMPT_PRESENTATION_ROOT / "layout" / "edit_algorithms.py",
        PROMPT_PRESENTATION_ROOT / "layout" / "incremental_engine.py",
    )

    assert all(not path.exists() for path in deleted_files)


def test_deleted_geometry_graph_cannot_return() -> None:
    """Keep replaced geometry modules and the forwarding facade deleted."""

    deleted_files = (
        PROMPT_PRESENTATION_ROOT / "projection" / "hit_testing.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "selection_geometry.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "snapshot.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "source_line_geometry.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "visible_line_range.py",
        PROMPT_PRESENTATION_ROOT / "geometry.py",
    )
    deleted_source_roots = (
        PROMPT_PRESENTATION_ROOT / "core" / "geometry",
        PROMPT_PRESENTATION_ROOT / "core" / "layout",
    )

    assert all(not path.exists() for path in deleted_files)
    assert all(
        not tuple(path.glob("*.py")) and not tuple(path.glob("*.pyi"))
        for path in deleted_source_roots
    )
