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

"""Source contracts for drag/reorder behavior in workflow tabs and cube stack."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    return ""


def test_workflow_tabbar_mouse_move_delegates_to_gesture_owner() -> None:
    """Workflow TabBar mouse move should not own reorder mutation directly."""
    source = _class_method_source(
        REPO_ROOT
        / "substitute"
        / "presentation"
        / "workflows"
        / "workflow_tabs_view.py",
        "TabBar",
        "mouseMoveEvent",
    )

    assert "self._handle_tab_mouse_event" in source
    assert "self._swapItem" not in source
    assert "self.isDraging" not in source


def test_cube_stack_release_keeps_finalize_and_signal_sequence() -> None:
    """CubeStack release logic should keep finalize and post-drag signal emissions."""
    source = _class_method_source(
        REPO_ROOT / "substitute" / "presentation" / "workflows" / "cube_stack_view.py",
        "CubeStack",
        "mouseReleaseEvent",
    )

    assert "self._adjustLayout()" in source
    assert "self.cubeMoveFinished.emit()" in source
    assert "self.tabMouseReleased.emit(current_index)" in source
