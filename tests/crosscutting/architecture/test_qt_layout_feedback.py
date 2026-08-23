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

"""Prevent widget-owned ``LayoutRequest`` event feedback across production."""

from __future__ import annotations

import ast
from pathlib import Path


_PROJECT_ROOT = Path(__file__).parents[3]
_PRODUCTION_ROOT = _PROJECT_ROOT / "substitute"


def _references_layout_request(node: ast.AST) -> bool:
    """Return whether an AST subtree names Qt's layout-request event."""

    return any(
        isinstance(candidate, ast.Attribute) and candidate.attr == "LayoutRequest"
        for candidate in ast.walk(node)
    )


def _assigned_layout_request_names(statements: list[ast.stmt]) -> set[str]:
    """Return constants whose assigned value contains ``LayoutRequest``."""

    names: set[str] = set()
    for statement in statements:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        value = statement.value
        if value is None or not _references_layout_request(value):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _references_named_layout_request(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    names: set[str],
) -> bool:
    """Return whether a method reads a known layout-request constant."""

    for candidate in ast.walk(function):
        if isinstance(candidate, ast.Name) and candidate.id in names:
            return True
        if isinstance(candidate, ast.Attribute) and candidate.attr in names:
            return True
    return False


def _self_layout_request_handlers(source_path: Path) -> list[str]:
    """Locate widget ``event`` overrides that consume their own layout request."""

    source = source_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(source_path))
    module_constants = _assigned_layout_request_names(module.body)
    violations: list[str] = []
    for class_node in (
        candidate
        for candidate in ast.walk(module)
        if isinstance(candidate, ast.ClassDef)
    ):
        class_constants = _assigned_layout_request_names(class_node.body)
        layout_request_names = module_constants | class_constants
        for statement in class_node.body:
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if statement.name != "event":
                continue
            if not (
                _references_layout_request(statement)
                or _references_named_layout_request(statement, layout_request_names)
            ):
                continue
            relative_path = source_path.relative_to(_PROJECT_ROOT).as_posix()
            violations.append(
                f"{relative_path}:{statement.lineno} ({class_node.name}.event)"
            )
    return violations


def test_production_widgets_do_not_handle_their_own_layout_request() -> None:
    """Forbid self-owned layout notifications from becoming geometry triggers."""

    violations = [
        violation
        for source_path in sorted(_PRODUCTION_ROOT.rglob("*.py"))
        for violation in _self_layout_request_handlers(source_path)
    ]

    assert not violations, (
        "A QWidget.event() override must not consume its own LayoutRequest. "
        "That event is a notification that the widget's owned layout is already dirty; "
        "using it to schedule or apply geometry can continuously requeue the same event. "
        "Observe an explicitly owned child with eventFilter(), or trigger geometry from "
        "the state-changing owner instead. Violations:\n- " + "\n- ".join(violations)
    )
