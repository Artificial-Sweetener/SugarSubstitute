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

"""Guard context-menu construction behind the shared menu renderer."""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRESENTATION_ROOT = _REPO_ROOT / "substitute" / "presentation"
_DIRECT_ROW_ALLOWLIST = {
    Path("widgets/qfluent_menu_renderer.py"),
    Path("widgets/seed_box.py"),
}
_DIRECT_MENU_ALLOWLIST = {
    Path("widgets/qfluent_menu_renderer.py"),
    Path("widgets/seed_box.py"),
}


def test_production_context_menus_use_shared_renderer() -> None:
    """Reject direct production menu row construction outside approved adapters."""

    row_violations: list[str] = []
    menu_violations: list[str] = []
    for path in _python_files(_PRESENTATION_ROOT):
        relative_path = path.relative_to(_PRESENTATION_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _is_menu_row_call(node) and relative_path not in _DIRECT_ROW_ALLOWLIST:
                row_violations.append(_location(relative_path, node))
            if (
                _is_direct_menu_call(node)
                and relative_path not in _DIRECT_MENU_ALLOWLIST
            ):
                menu_violations.append(_location(relative_path, node))

    assert row_violations == []
    assert menu_violations == []


def test_popup_dismissal_defers_modal_entry_beyond_menu_callbacks() -> None:
    """Forbid nested modal loops while a transient menu signal is unwinding."""

    source_path = _PRESENTATION_ROOT / "widgets" / "model_metadata_context_menu.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    action_factory = _function_definition(
        tree,
        "thumbnail_library_action_for_target",
    )
    menu_action = next(
        node
        for node in ast.walk(action_factory)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ModelMetadataMenuAction"
    )
    callback_reference = menu_action.args[1]
    assert isinstance(callback_reference, ast.Name)
    callback = _function_definition(action_factory, callback_reference.id)
    callback_calls = _direct_call_names(callback)

    assert "_thumbnail_library_opening" in callback_calls
    assert "_schedule_modal_action" in callback_calls
    assert "choose_ultralytics_thumbnail" not in callback_calls

    schedule_call = next(
        node
        for node in ast.walk(callback)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_schedule_modal_action"
    )
    deferred_reference = schedule_call.args[0]
    assert isinstance(deferred_reference, ast.Name)
    deferred_action = _function_definition(action_factory, deferred_reference.id)
    assert "choose_ultralytics_thumbnail" in _direct_call_names(deferred_action)


def _python_files(root: Path) -> tuple[Path, ...]:
    """Return production Python files under one root."""

    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _function_definition(root: ast.AST, name: str) -> ast.FunctionDef:
    """Return one named function nested anywhere under an AST owner."""

    matches = [
        node
        for node in ast.walk(root)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def _direct_call_names(function: ast.FunctionDef) -> set[str]:
    """Return calls made by one function without descending into nested functions."""

    visitor = _DirectCallVisitor()
    for statement in function.body:
        visitor.visit(statement)
    return visitor.calls


class _DirectCallVisitor(ast.NodeVisitor):
    """Collect calls while treating nested callable bodies as separate scopes."""

    def __init__(self) -> None:
        """Initialize the direct-call set."""

        self.calls: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Skip nested synchronous function bodies."""

        _ = node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Skip nested asynchronous function bodies."""

        _ = node

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Skip nested lambda bodies."""

        _ = node

    def visit_Call(self, node: ast.Call) -> None:
        """Record one direct call and inspect its evaluated arguments."""

        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
        self.generic_visit(node)


def _is_menu_row_call(node: ast.Call) -> bool:
    """Return whether a call directly mutates menu rows."""

    return isinstance(node.func, ast.Attribute) and node.func.attr in {
        "addAction",
        "addMenu",
    }


def _is_direct_menu_call(node: ast.Call) -> bool:
    """Return whether a call constructs a Qt/QFluent menu directly."""

    return isinstance(node.func, ast.Name) and node.func.id in {"RoundMenu", "QMenu"}


def _location(path: Path, node: ast.AST) -> str:
    """Return a stable source location for one architecture violation."""

    return f"{path.as_posix()}:{getattr(node, 'lineno', 0)}"
