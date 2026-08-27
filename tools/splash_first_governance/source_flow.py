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

"""Trace executable source that can run before a reviewed splash boundary."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Sequence


def find_function(
    module: ast.Module,
    function_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return one top-level protected function by exact name."""

    for statement in module.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            statement.name == function_name
        ):
            return statement
    return None


def calls_without_nested_functions(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterable[ast.Call]:
    """Yield calls owned directly by a function body."""

    for statement in function.body:
        yield from calls((statement,))


def calls(nodes: Iterable[ast.AST]) -> Iterable[ast.Call]:
    """Yield calls without descending into nested callable definitions."""

    stack = list(nodes)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Call):
            yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def imports(
    nodes: Iterable[ast.AST],
) -> Iterable[tuple[str, ast.Import | ast.ImportFrom]]:
    """Yield imported module names without entering nested callables."""

    stack = list(nodes)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module, node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def call_name(call: ast.Call) -> str:
    """Return the source-qualified name of one call target."""

    return _expression_name(call.func)


def nodes_on_boundary_path(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    boundary: ast.Call,
) -> tuple[ast.AST, ...]:
    """Return nodes that can execute before the boundary on its control-flow path."""

    selected: list[ast.AST] = []
    _collect_path_prefix(function.body, boundary=boundary, selected=selected)
    selected.extend(boundary.args)
    selected.extend(keyword.value for keyword in boundary.keywords)
    selected.append(boundary)
    return tuple(selected)


def _expression_name(expression: ast.expr) -> str:
    """Return a dotted name for a simple name or attribute expression."""

    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        owner = _expression_name(expression.value)
        return f"{owner}.{expression.attr}" if owner else expression.attr
    return ""


def _collect_path_prefix(
    statements: Sequence[ast.stmt],
    *,
    boundary: ast.Call,
    selected: list[ast.AST],
) -> bool:
    """Collect statements on the unique lexical path to a boundary call."""

    for statement in statements:
        if _contains_node(statement, boundary):
            return _collect_inside_statement(
                statement,
                boundary=boundary,
                selected=selected,
            )
        if isinstance(statement, ast.If) and _body_always_terminates(statement.body):
            selected.append(statement.test)
            selected.extend(statement.orelse)
            continue
        selected.append(statement)
    return False


def _collect_inside_statement(
    statement: ast.stmt,
    *,
    boundary: ast.Call,
    selected: list[ast.AST],
) -> bool:
    """Descend through the branch that contains the splash boundary."""

    if isinstance(statement, ast.If):
        selected.append(statement.test)
        branch: Sequence[ast.stmt] = (
            statement.body
            if any(_contains_node(child, boundary) for child in statement.body)
            else statement.orelse
        )
        return _collect_path_prefix(branch, boundary=boundary, selected=selected)
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        selected.append(
            statement.target
            if isinstance(statement, (ast.For, ast.AsyncFor))
            else statement.test
        )
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            selected.append(statement.iter)
        branch = (
            statement.body
            if any(_contains_node(child, boundary) for child in statement.body)
            else statement.orelse
        )
        return _collect_path_prefix(branch, boundary=boundary, selected=selected)
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        selected.extend(statement.items)
        return _collect_path_prefix(
            statement.body,
            boundary=boundary,
            selected=selected,
        )
    if isinstance(statement, ast.Try):
        branches: tuple[Sequence[ast.stmt], ...] = (
            statement.body,
            statement.orelse,
            statement.finalbody,
            *(handler.body for handler in statement.handlers),
        )
        for branch in branches:
            if any(_contains_node(child, boundary) for child in branch):
                return _collect_path_prefix(
                    branch,
                    boundary=boundary,
                    selected=selected,
                )
    selected.append(statement)
    return True


def _body_always_terminates(statements: Sequence[ast.stmt]) -> bool:
    """Return whether a branch cannot continue to a following splash boundary."""

    if not statements:
        return False
    terminal = statements[-1]
    if isinstance(terminal, (ast.Return, ast.Raise)):
        return True
    if isinstance(terminal, ast.If):
        return (
            bool(terminal.orelse)
            and _body_always_terminates(terminal.body)
            and _body_always_terminates(terminal.orelse)
        )
    return False


def _contains_node(root: ast.AST, target: ast.AST) -> bool:
    """Return whether one AST node contains another by identity."""

    return any(node is target for node in ast.walk(root))


__all__ = [
    "call_name",
    "calls",
    "calls_without_nested_functions",
    "find_function",
    "imports",
    "nodes_on_boundary_path",
]
