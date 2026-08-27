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

"""Resolve imported Python call identities without executing test source."""

from __future__ import annotations

import ast


def import_aliases(tree: ast.Module) -> dict[str, str]:
    """Return local import names mapped to their canonical dotted owners."""

    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for imported in node.names:
                local_name = imported.asname or imported.name.split(".", maxsplit=1)[0]
                aliases[local_name] = imported.name
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for imported in node.names:
                if imported.name == "*":
                    continue
                local_name = imported.asname or imported.name
                aliases[local_name] = f"{node.module}.{imported.name}"
    return aliases


def call_name(node: ast.expr, aliases: dict[str, str]) -> str:
    """Return one dotted call name without evaluating source."""

    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = call_name(node.value, aliases)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def configured_call_name(
    call_identity: str,
    configured_calls: frozenset[str],
) -> str | None:
    """Return the most specific configured name matching one canonical call."""

    matches = tuple(
        configured
        for configured in configured_calls
        if call_identity == configured or call_identity.endswith(f".{configured}")
    )
    return max(matches, key=len, default=None)


__all__ = ["call_name", "configured_call_name", "import_aliases"]
