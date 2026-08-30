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

"""Discover network-resource lifetime risks in test and CI support."""

from __future__ import annotations

import ast

from .model import TestCandidate

PORT_HANDOFF_RULE = "PORT001"


def closed_ephemeral_port_candidates(
    *,
    path: str,
    tree: ast.Module,
) -> list[TestCandidate]:
    """Find port helpers that close their reservation before returning its number."""

    candidates: list[TestCandidate] = []
    ordinal = 0
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        for context in (
            node for node in ast.walk(function) if isinstance(node, ast.With)
        ):
            for item in context.items:
                if not isinstance(item.optional_vars, ast.Name):
                    continue
                socket_name = item.optional_vars.id
                if not _binds_os_assigned_port(context, socket_name):
                    continue
                derived_names = _port_names_derived_from_socket(context, socket_name)
                if not any(
                    _returns_socket_port(statement, socket_name, derived_names)
                    for statement in function.body
                ):
                    continue
                ordinal += 1
                candidates.append(
                    TestCandidate(
                        rule=PORT_HANDOFF_RULE,
                        path=path,
                        locator=f"{function.name}:closed-port-handoff:{ordinal}",
                        evidence=(
                            "returns an OS-assigned port after its reservation socket "
                            "closes"
                        ),
                        line=context.lineno,
                    )
                )
    return candidates


def _binds_os_assigned_port(context: ast.With, socket_name: str) -> bool:
    """Return whether one context asks the OS for a port on its owned socket."""

    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == socket_name
        and node.func.attr == "bind"
        and any(
            isinstance(value, ast.Constant) and value.value == 0
            for argument in node.args
            for value in ast.walk(argument)
        )
        for statement in context.body
        for node in ast.walk(statement)
    )


def _port_names_derived_from_socket(
    context: ast.With,
    socket_name: str,
) -> frozenset[str]:
    """Return local names assigned from the owned socket's address."""

    return frozenset(
        target.id
        for statement in context.body
        for node in ast.walk(statement)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            (*node.targets,) if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
        and node.value is not None
        and _calls_socket_getsockname(node.value, socket_name)
    )


def _returns_socket_port(
    statement: ast.stmt,
    socket_name: str,
    derived_names: frozenset[str],
) -> bool:
    """Return whether a statement publishes a closed socket's derived port."""

    return any(
        isinstance(node, ast.Return)
        and node.value is not None
        and (
            _calls_socket_getsockname(node.value, socket_name)
            or any(
                isinstance(value, ast.Name) and value.id in derived_names
                for value in ast.walk(node.value)
            )
        )
        for node in ast.walk(statement)
    )


def _calls_socket_getsockname(expression: ast.expr, socket_name: str) -> bool:
    """Return whether an expression reads the owned socket address."""

    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == socket_name
        and node.func.attr == "getsockname"
        for node in ast.walk(expression)
    )


__all__ = ["PORT_HANDOFF_RULE", "closed_ephemeral_port_candidates"]
