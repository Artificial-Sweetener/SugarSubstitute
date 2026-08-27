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

"""Discover real Node commands that bypass bounded test execution ownership."""

from __future__ import annotations

import ast

from .ast_analysis import call_name
from .model import TestCandidate

NODE_PROCESS_RULE = "NODE001"

_NODE_PROCESS_CALLS = frozenset(
    {
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.run",
    }
)
_LEXICAL_SCOPES = (
    ast.Module,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ClassDef,
)


def node_process_pattern_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find real Node commands that bypass the bounded test execution owner."""

    parent_by_node = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    assignments = _unique_assignment_values_by_scope(tree, parent_by_node)
    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        identity = call_name(node.func, aliases)
        if identity not in _NODE_PROCESS_CALLS:
            continue
        command = _call_command_expression(node)
        if isinstance(command, ast.Name):
            scope = _lexical_scope(node, parent_by_node)
            command = assignments.get(scope, {}).get(command.id)
        if not _literal_command_starts_with_node(command):
            continue
        ordinal += 1
        candidates.append(
            TestCandidate(
                rule=NODE_PROCESS_RULE,
                path=path,
                locator=f"<module>:unowned-node-process:{ordinal}",
                evidence=(
                    f"calls real Node through {identity} instead of the bounded "
                    "shared test runtime owner"
                ),
                line=node.lineno,
            )
        )
    return candidates


def _unique_assignment_values_by_scope(
    tree: ast.Module,
    parent_by_node: dict[ast.AST, ast.AST],
) -> dict[ast.AST, dict[str, ast.expr]]:
    """Return unambiguous simple-name values within their lexical scopes."""

    bindings: dict[ast.AST, dict[str, list[ast.expr]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        scope = _lexical_scope(node, parent_by_node)
        scope_bindings = bindings.setdefault(scope, {})
        for target in targets:
            if isinstance(target, ast.Name):
                scope_bindings.setdefault(target.id, []).append(value)
    return {
        scope: {
            name: values[0]
            for name, values in scope_bindings.items()
            if len(values) == 1
        }
        for scope, scope_bindings in bindings.items()
    }


def _lexical_scope(
    node: ast.AST,
    parent_by_node: dict[ast.AST, ast.AST],
) -> ast.AST:
    """Return the nearest scope that owns one expression or assignment."""

    current = node
    while current in parent_by_node:
        current = parent_by_node[current]
        if isinstance(current, _LEXICAL_SCOPES):
            return current
    return current


def _call_command_expression(node: ast.Call) -> ast.expr | None:
    """Return the command expression from a subprocess call."""

    if node.args:
        return node.args[0]
    return next(
        (keyword.value for keyword in node.keywords if keyword.arg == "args"),
        None,
    )


def _literal_command_starts_with_node(node: ast.expr | None) -> bool:
    """Return whether one literal command invokes the Node executable."""

    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return False
    executable = node.elts[0]
    if not isinstance(executable, ast.Constant) or not isinstance(
        executable.value, str
    ):
        return False
    basename = executable.value.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return basename.casefold() in {"node", "node.exe"}


__all__ = ["NODE_PROCESS_RULE", "node_process_pattern_candidates"]
